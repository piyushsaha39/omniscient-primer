import json
import uuid
import re
from datetime import datetime
from typing import Dict, Any, List

from app.models import WarmStartDoc, EnhancedWarmStartDoc, SubtaskProfile
from app.services.gemini_service import GeminiService
from app.services.docs_service import DocsService

EXECUTION_AGENT_SYSTEM_PROMPT = """You are the Execution Agent, a preparatory research and drafting assistant. When a work block is scheduled, you pre-complete a fixed checklist to eliminate blank-page friction.

FIXED CHECKLIST (verifiable deliverables only — no percentages):

For writing/strategy tasks:
1. RESEARCH SUMMARY: Use Google Search grounding to find 3–5 key facts, trends, or data points relevant to the task topic. Include brief source citations.
2. STRUCTURED OUTLINE: Produce a document outline with sections. Each section must have a title and a one-line description.
3. OPENING DRAFT: Write 1–2 paragraphs that serve as the document's opening. This must be substantive enough to break the blank-page barrier. It is explicitly NOT the full document.

OUTPUT FORMAT:
Return ONLY a JSON object with this exact structure:
{
  "research_summary": "string with citations",
  "outline": [
    {"section": "Section Title", "description": "One-line description."}
  ],
  "opening_draft": "string containing 1–2 paragraphs"
}

RULES:
- Do not claim any percentage of task completion.
- Do not hallucinate sources. Ground every fact."""

class ExecutionAgent:
    def __init__(self, gemini_service: GeminiService, docs_service: DocsService):
        self.gemini = gemini_service
        self.docs = docs_service

    def _parse_gemini_json(self, raw_text: str) -> dict | list:
        clean_json_str = raw_text.strip()
        if clean_json_str.startswith("```"):
            clean_json_str = clean_json_str.strip("`").strip()
            if clean_json_str.startswith("json"):
                clean_json_str = clean_json_str[4:].strip()
        try:
            return json.loads(clean_json_str)
        except json.JSONDecodeError:
            return None

    def run(self, topic: str, task_type: str = "writing", user_history: List[Any] = [], token: str = "") -> EnhancedWarmStartDoc:
        # Step 1: Base Generation
        prompt = f"Topic: {topic}\nTask type: {task_type}\n\n{EXECUTION_AGENT_SYSTEM_PROMPT}"
        raw = self.gemini.generate_json(prompt)
        base_doc = self._parse_gemini_json(raw)

        if not base_doc:
            base_doc = {
                "research_summary": "Failed to parse JSON response.",
                "outline": [],
                "opening_draft": ""
            }

        # Step 2: Detect Big Task
        is_big = self._is_big_task(topic, base_doc.get("outline", []))

        if not is_big:
            content = self._format_doc_content(base_doc)
            title = f"Warm Start: {topic}"
            doc_id, doc_url = self.docs.create_document(token, title, content)

            return EnhancedWarmStartDoc(
                id=str(uuid.uuid4()),
                title=title,
                google_doc_id=doc_id,
                doc_url=doc_url,
                research_summary=base_doc.get("research_summary", ""),
                outline=json.dumps(base_doc.get("outline", [])),
                opening_draft=base_doc.get("opening_draft", ""),
                status="completed",
                created_at=datetime.utcnow()
            )

        # Step 3: Subtask decomposition
        subtasks = self._decompose_into_subtasks(topic, base_doc.get("outline", []))

        # Step 4: Procrastination forensics
        subtasks = self._apply_friction_scoring(subtasks, user_history)

        # Step 5: Identify primary friction point
        primary_friction = max(subtasks, key=lambda x: x.friction_score) if subtasks else None

        # Step 6: Preload content for friction
        if primary_friction:
            primary_friction.preloaded_content = self._generate_preload(
                topic, primary_friction.title, base_doc.get("research_summary", "")
            )

        # Step 7: Format enhanced doc
        enhanced_content = self._format_enhanced_doc(base_doc, subtasks, primary_friction)
        doc_id, doc_url = self.docs.create_document(
            token,
            f"Warm Start: {topic} [Big Task — Iris Forensics]",
            enhanced_content
        )

        return EnhancedWarmStartDoc(
            id=str(uuid.uuid4()),
            title=topic,
            google_doc_id=doc_id,
            doc_url=doc_url,
            research_summary=base_doc.get("research_summary", ""),
            outline=json.dumps(base_doc.get("outline", [])),
            opening_draft=base_doc.get("opening_draft", ""),
            subtasks=subtasks,
            primary_friction_subtask_id=primary_friction.id if primary_friction else None,
            is_big_task=True,
            status="completed",
            created_at=datetime.utcnow()
        )

    def _is_big_task(self, topic: str, outline: List[Dict]) -> bool:
        keywords = ["project", "thesis", "assignment", "review", "prep"]
        return len(outline) > 4 or any(k in topic.lower() for k in keywords)

    def _decompose_into_subtasks(self, topic: str, outline: List[Dict]) -> List[SubtaskProfile]:
        prompt = f"""Break this task into 4-7 atomic subtasks. Task: {topic}. Outline: {json.dumps(outline)}
        Return ONLY JSON array: [{{"title": "...", "description": "...", "estimated_minutes": number}}]"""

        raw = self.gemini.generate_json(prompt)
        data = self._parse_gemini_json(raw)

        if not data or not isinstance(data, list):
            return []

        return [
            SubtaskProfile(
                id=f"sub_{i}",
                title=item.get("title", "Untitled Subtask"),
                description=item.get("description", ""),
                estimated_minutes=item.get("estimated_minutes", 15)
            ) for i, item in enumerate(data) if isinstance(item, dict)
        ]

    def _apply_friction_scoring(self, subtasks: List[SubtaskProfile], user_history: List[Any]) -> List[SubtaskProfile]:
        stall_keywords = ["implementation", "testing", "drafting", "writing", "execution", "debugging", "edge case"]

        for subtask in subtasks:
            score = 0.0
            for kw in stall_keywords:
                if kw in subtask.title.lower() or kw in subtask.description.lower():
                    score += 0.25

            for entry in user_history:
                if getattr(entry, "action_type", "") == "WARM_START_ABANDONED":
                    desc = getattr(entry, "description", "").lower()
                    if any(kw in desc for kw in subtask.title.lower().split()):
                        score += 0.35
                        subtask.historical_stall = True

            subtask.friction_score = min(score, 1.0)

        return subtasks

    def _generate_preload(self, topic: str, subtask_title: str, research: str) -> str:
        prompt = f"""Generate 2-3 sentences of starter content for this subtask to eliminate blank-page friction.
        Task: {topic}
        Subtask: {subtask_title}
        Context: {research}
        Write in a direct, actionable tone. The user tends to procrastinate here, so make the first step trivial."""
        return self.gemini.generate_text(prompt)

    def _format_doc_content(self, data: dict) -> str:
        content = []
        content.append("RESEARCH SUMMARY\n")
        content.append("=" * 20 + "\n")
        content.append(str(data.get("research_summary", "")) + "\n\n")

        content.append("OUTLINE\n")
        content.append("=" * 20 + "\n")
        for item in data.get("outline", []):
            if isinstance(item, dict):
                content.append(f"• {item.get('section', 'Untitled')}: {item.get('description', '')}\n")
        content.append("\n")

        content.append("OPENING DRAFT\n")
        content.append("=" * 20 + "\n")
        content.append(str(data.get("opening_draft", "")) + "\n")

        return "".join(content)

    def _format_enhanced_doc(self, base_doc: Dict, subtasks: List[SubtaskProfile], friction: SubtaskProfile) -> str:
        lines = [
            "═══════════════════════════════════════",
            "IRIS FORENSICS WARNING",
            "═══════════════════════════════════════"
        ]

        if friction:
            lines.extend([
                f"Boss, I've analyzed your task history. You tend to stall at: '{friction.title}'.",
                f"Friction Score: {friction.friction_score:.0%}",
                f"I've pre-loaded the opening for this section below.",
                "",
                "PRE-LOADED STARTER:",
                friction.preloaded_content,
                ""
            ])

        lines.extend([
            "═══════════════════════════════════════",
            "SUBTASK BREAKDOWN",
            "═══════════════════════════════════════",
        ])

        for s in subtasks:
            marker = "⚠️ HISTORICAL STALL ZONE" if s.historical_stall else "✓ Standard"
            lines.extend([
                f"[{s.id}] {s.title} ({s.estimated_minutes} min) {marker}",
                f"    {s.description}",
                ""
            ])

        lines.extend([
            "═══════════════════════════════════════",
            "RESEARCH SUMMARY",
            "═══════════════════════════════════════",
            base_doc.get("research_summary", ""),
            "",
            "═══════════════════════════════════════",
            "OUTLINE",
            "═══════════════════════════════════════",
        ])

        for section in base_doc.get("outline", []):
            lines.append(f"• {section.get('section', 'Untitled')}\n  {section.get('description', '')}\n")

        lines.extend([
            "",
            "═══════════════════════════════════════",
            "OPENING DRAFT",
            "═══════════════════════════════════════",
            base_doc.get("opening_draft", "")
        ])
        return "\n".join(lines)