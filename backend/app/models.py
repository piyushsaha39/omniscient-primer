from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

# --- SQLAlchemy Imports ---
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from app.database import Base

# ==========================================
# SQLALCHEMY MODELS (Database Tables)
# ==========================================
class UserDB(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True) # Maps to Clerk Auth ID
    email = Column(String, unique=True, index=True)
    name = Column(String)
    
    # Securely store user-specific tokens here!
    email_digest_token = Column(String, nullable=True)
    google_credentials_json = Column(String, nullable=True)

class EmailDB(Base):
    __tablename__ = "emails"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    sender = Column(String)
    subject = Column(String)
    summary = Column(String)
    urgency_score = Column(Float)
    implied_deadline = Column(DateTime, nullable=True)
    is_meeting_request = Column(Boolean, default=False)
    received_at = Column(DateTime)

class ProposalDB(Base):
    __tablename__ = "proposals"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    email_id = Column(String)
    event_id = Column(String)
    event_title = Column(String)
    proposed_new_start = Column(DateTime)
    proposed_new_end = Column(DateTime)
    reason = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime)

class WarmStartDB(Base):
    __tablename__ = "warm_starts"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    title = Column(String)
    google_doc_id = Column(String)
    doc_url = Column(String)
    research_summary = Column(String)
    outline = Column(String)
    opening_draft = Column(String)
    status = Column(String, default="completed")
    created_at = Column(DateTime)

class ChangelogDB(Base):
    __tablename__ = "changelogs"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    action_type = Column(String)
    description = Column(String)
    target_date = Column(DateTime)
    created_at = Column(DateTime)


# ==========================================
# PYDANTIC MODELS (API & Data Validation)
# ==========================================
class EmailSignal(BaseModel):
    id: str
    sender: str
    subject: str
    summary: str
    urgency_score: float = Field(..., ge=0, le=10)
    implied_deadline: Optional[datetime] = None
    is_meeting_request: bool = False
    received_at: datetime

class UserSettings(BaseModel):
    clerk_id: str
    email_address: str
    email_digest_token: str

class CalendarEvent(BaseModel):
    id: str
    title: str
    start_time: datetime
    end_time: datetime
    is_work_block: bool = False
    historical_move_rate: Optional[float] = None

class RescheduleProposal(BaseModel):
    id: str
    email_id: str
    event_to_move: CalendarEvent
    proposed_new_start: datetime
    proposed_new_end: datetime
    reason: str
    status: str = "pending"
    created_at: datetime

class WarmStartDoc(BaseModel):
    id: str
    title: str
    google_doc_id: str
    doc_url: str
    research_summary: str
    outline: str
    opening_draft: str
    status: str = "completed"
    created_at: datetime

class SystemChangeLog(BaseModel):
    id: str
    action_type: str
    description: str
    target_date: datetime
    created_at: datetime

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []

class ChatResponse(BaseModel):
    reply: str
    action_taken: Optional[str] = None
    warm_start: Optional[WarmStartDoc] = None

class MorningBriefing(BaseModel):
    new_urgent_emails: List[EmailSignal] = []
    pending_proposals: List[RescheduleProposal] = []
    completed_warm_starts: List[Any] = []
    generated_at: datetime
    upcoming_events: List[CalendarEvent] = []  # Added for 7-day calendar view

class SubtaskProfile(BaseModel):
    id: str
    title: str
    description: str
    estimated_minutes: int
    friction_score: float = 0.0  
    historical_stall: bool = False
    preloaded_content: str = ""

class EnhancedWarmStartDoc(WarmStartDoc):
    subtasks: List[SubtaskProfile] = []
    primary_friction_subtask_id: Optional[str] = None
    is_big_task: bool = False

class AudioBriefingSegment(BaseModel):
    channel: str
    text: str
    priority: int
    action_type: str

class AudioBriefingResponse(BaseModel):
    segments: List[AudioBriefingSegment]
    transition_gap_minutes: Optional[int]
    next_event_title: Optional[str]
    void_state_recommended: bool