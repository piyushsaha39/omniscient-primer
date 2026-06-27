import uuid
from datetime import datetime
from typing import List

import google.generativeai as genai
from google.generativeai.protos import Tool, FunctionDeclaration

from app.models import SystemChangeLog, ChatMessage, ChatResponse, WarmStartDoc
from app.services.gemini_service import GeminiService
from app.agents.execution_agent import ExecutionAgent

create_warm_start_func = FunctionDeclaration(
    name="create_warm_start",
    description="Trigger Stage 3 to generate a Warm Start prep document for a topic.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "topic": {"type": "STRING", "description": "The topic to prepare for"},
            "task_type": {"type": "STRING", "enum": ["writing", "research"], "description": "The type of task"}
        },
        "required": ["topic"]
    }
)

query_change_log_func = FunctionDeclaration(
    name="query_change_log",
    description="Return all autonomous system changes logged on a given date.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "date": {"type": "STRING", "description": "YYYY-MM-DD"}
        },
        "required": ["date"]
    }
)

ASSISTANT_TOOLS = [
    Tool(function_declarations=[create_warm_start_func, query_change_log_func])
]

class AssistantAgent:
    def __init__(self, gemini_service: GeminiService, execution_agent: ExecutionAgent, changelog_db: List[SystemChangeLog]):
        self.gemini_service = gemini_service
        self.execution_agent = execution_agent
        self.changelog_db = changelog_db  # kept for compatibility; DB is source of truth via main.py

    def chat(self, message: str, history: List[ChatMessage], token: str = "") -> ChatResponse:
        current_date = datetime.utcnow().strftime("%Y-%m-%d")

        system_prompt = (
            f"You are the Omniscient Primer AI Assistant. You have two tools: create_warm_start and query_change_log. "
            f"Call create_warm_start when the user wants to schedule or start work on any topic. "
            f"Call query_change_log when the user asks what the system changed on a date. "
            f"Keep replies ≤2 sentences — they may be read aloud. NEVER trigger calendar moves — direct users to the Approve button. "
            f"Do not hallucinate capabilities beyond your two tools. "
            f"IMPORTANT: The current date is {current_date}. When calling query_change_log without a specific date mentioned by the user, you MUST use {current_date}."
        )

        response = self.gemini_service.generate_with_tools(
            prompt=message,
            tools=ASSISTANT_TOOLS,
            system_prompt=system_prompt
        )

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    func_call = part.function_call

                    if func_call.name == "create_warm_start":
                        args = dict(func_call.args)
                        topic = args.get("topic", "Untitled Task")
                        task_type = args.get("task_type", "writing")

                        # token is now threaded through so docs_service can authenticate
                        doc = self.execution_agent.run(topic=topic, task_type=task_type, token=token)

                        log_entry = SystemChangeLog(
                            id=str(uuid.uuid4()),
                            action_type="WARM_START_CREATED",
                            description=f"Created warm start document for topic '{topic}'",
                            target_date=datetime.utcnow(),
                            created_at=datetime.utcnow()
                        )
                        self.changelog_db.append(log_entry)

                        reply = f"Done — I've created a Warm Start doc for '{topic}'. It's ready on the left."
                        return ChatResponse(reply=reply, action_taken="warm_start_created", warm_start=doc)

                    elif func_call.name == "query_change_log":
                        args = dict(func_call.args)
                        date_str = args.get("date", current_date)

                        try:
                            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                            entries = [entry for entry in self.changelog_db if entry.created_at.date() == target_date]

                            if not entries:
                                reply = f"There were no autonomous system changes logged on {date_str}."
                            else:
                                changes_list = "; ".join([e.description for e in entries])
                                reply = f"On {date_str}, I did the following: {changes_list}."
                        except ValueError:
                            reply = "I couldn't parse the date. Please provide it in YYYY-MM-DD format."

                        return ChatResponse(reply=reply, action_taken="changelog_queried")

        reply_text = response.text.strip() if hasattr(response, 'text') else "I couldn't process that request."
        return ChatResponse(reply=reply_text)