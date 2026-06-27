import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.models import EmailSignal, CalendarEvent, RescheduleProposal
from app.services.gemini_service import GeminiService

class CalendarDiplomatAgent:
    def __init__(self, gemini_service: GeminiService):
        self.gemini_service = gemini_service

    def detect_conflict(self, email: EmailSignal, events: List[CalendarEvent]) -> Optional[CalendarEvent]:
        if not email.implied_deadline:
            return None
            
        # 4-hour window before the implied deadline
        window_start = email.implied_deadline - timedelta(hours=4)
        window_end = email.implied_deadline
        
        for event in events:
            if event.is_work_block:
                continue
                
            # Check for overlap with the 4-hour window
            if event.start_time < window_end and event.end_time > window_start:
                return event
                
        return None

    def propose(self, email: EmailSignal, event_to_move: CalendarEvent, all_events: List[CalendarEvent]) -> RescheduleProposal:
        proposed_start = event_to_move.start_time + timedelta(hours=24)
        proposed_end = event_to_move.end_time + timedelta(hours=24)
        
        system_prompt = (
            "You are the Calendar Diplomat. Draft a concise, polite one-sentence reason "
            "explaining why moving the conflicting event serves the user's priorities. "
            "NEVER execute a move. NEVER suggest moving untouchable events (flights, medical). "
            "Output only the reason text."
        )
        
        prompt = (
            f"Email subject: '{email.subject}'\n"
            f"Conflicting event title: '{event_to_move.title}'\n"
            "Please provide the one-sentence reason."
        )
        
        reason_text = self.gemini_service.generate_text(prompt=prompt, system_prompt=system_prompt)
        
        proposal = RescheduleProposal(
            id=str(uuid.uuid4()),
            email_id=email.id,
            event_to_move=event_to_move,
            proposed_new_start=proposed_start,
            proposed_new_end=proposed_end,
            reason=reason_text.strip(),
            status="pending",
            created_at=datetime.now(timezone.utc)
        )
        
        return proposal
