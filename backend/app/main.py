import httpx
import os
import uuid
import asyncio
import traceback
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Any
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from google import genai
from google.genai import types

# --- Database & Models ---
from app.database import engine, Base, get_db
from app.models import (
    UserDB, UserSettings, EmailSignal, CalendarEvent, RescheduleProposal,
    WarmStartDoc, EnhancedWarmStartDoc, SystemChangeLog, ChatMessage,
    ChatRequest, ChatResponse, MorningBriefing, AudioBriefingResponse,
    AudioBriefingSegment, EmailDB, ProposalDB, WarmStartDB, ChangelogDB
)

# --- Services & Agents ---
from app.services.gemini_service import GeminiService
from app.services.calendar_service import CalendarService
from app.services.docs_service import DocsService
from app.services.email_ingest_service import EmailIngestService
from app.agents.calendar_diplomat import CalendarDiplomatAgent
from app.agents.execution_agent import ExecutionAgent
from app.agents.assistant_agent import AssistantAgent

# Global services & agents
gemini_service = None
calendar_service = None
docs_service = None
diplomat_agent = None
execution_agent = None
assistant_agent = None
live_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global gemini_service, calendar_service, docs_service
    global diplomat_agent, execution_agent, assistant_agent, live_client

    api_key = os.environ.get("GEMINI_API_KEY", "")
    gemini_service = GeminiService(api_key=api_key)
    calendar_service = CalendarService()
    docs_service = DocsService()

    diplomat_agent = CalendarDiplomatAgent(gemini_service)
    execution_agent = ExecutionAgent(gemini_service, docs_service)
    assistant_agent = AssistantAgent(gemini_service, execution_agent, [])

    live_client = genai.Client(api_key=api_key)
    yield

app = FastAPI(lifespan=lifespan)

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def _to_aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

def get_active_user(user_id: Optional[str]) -> Optional[str]:
    """Strict Isolation: No more falling back to other users."""
    if not user_id or user_id == "undefined" or user_id == "null":
        return None
    return user_id

async def get_google_access_token(user_id: str) -> str:
    """Asks Clerk for the user's live Google OAuth access token."""
    clerk_secret = os.environ.get("CLERK_SECRET_KEY", "")
    if not clerk_secret:
        raise HTTPException(status_code=500, detail="CLERK_SECRET_KEY not set")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.clerk.com/v1/users/{user_id}/oauth_access_tokens/google",
            headers={"Authorization": f"Bearer {clerk_secret}"}
        )

        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Could not fetch Google token from Clerk")

        data = response.json()

        if not data or len(data) == 0:
            raise HTTPException(status_code=401, detail="No Google OAuth token found. Has the user signed in with Google?")

        return data[0]["token"]

# Model Mappers
def map_email(db_email: EmailDB) -> EmailSignal:
    return EmailSignal(
        id=db_email.id, sender=db_email.sender, subject=db_email.subject,
        summary=db_email.summary, urgency_score=db_email.urgency_score,
        implied_deadline=db_email.implied_deadline, is_meeting_request=db_email.is_meeting_request,
        received_at=_to_aware(db_email.received_at)
    )

def map_proposal(db_prop: ProposalDB) -> RescheduleProposal:
    return RescheduleProposal(
        id=db_prop.id, email_id=db_prop.email_id,
        event_to_move=CalendarEvent(
            id=db_prop.event_id, title=db_prop.event_title,
            start_time=_to_aware(db_prop.proposed_new_start), end_time=_to_aware(db_prop.proposed_new_end)
        ),
        proposed_new_start=_to_aware(db_prop.proposed_new_start), proposed_new_end=_to_aware(db_prop.proposed_new_end),
        reason=db_prop.reason, status=db_prop.status, created_at=_to_aware(db_prop.created_at)
    )

def map_warmstart(db_ws: WarmStartDB) -> WarmStartDoc:
    return WarmStartDoc(
        id=db_ws.id, title=db_ws.title, google_doc_id=db_ws.google_doc_id, doc_url=db_ws.doc_url,
        research_summary=db_ws.research_summary, outline=db_ws.outline, opening_draft=db_ws.opening_draft,
        status=db_ws.status, created_at=_to_aware(db_ws.created_at)
    )

def map_changelog(db_cl: ChangelogDB) -> SystemChangeLog:
    return SystemChangeLog(
        id=db_cl.id, action_type=db_cl.action_type, description=db_cl.description,
        target_date=_to_aware(db_cl.target_date), created_at=_to_aware(db_cl.created_at)
    )

# =============================================================================
# API ROUTES
# =============================================================================
@app.get("/")
def health_check():
    return {"status": "ok", "version": "1.5.1 (Strict Multi-Tenant Isolation)"}

@app.post("/api/v1/users/settings")
def update_user_settings(settings: UserSettings, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.id == settings.clerk_id).first()
    if user:
        user.email_digest_token = settings.email_digest_token
    else:
        new_user = UserDB(id=settings.clerk_id, email=settings.email_address, email_digest_token=settings.email_digest_token)
        db.add(new_user)
    db.commit()
    return {"status": "success"}

# --- Stage 1 routes ---
@app.get("/api/v1/stage1/emails", response_model=List[EmailSignal])
def get_emails(user_id: Optional[str] = None, db: Session = Depends(get_db)):
    uid = get_active_user(user_id)
    if not uid: return []
    db_emails = db.query(EmailDB).filter(EmailDB.user_id == uid).order_by(EmailDB.received_at.desc()).all()
    return [map_email(e) for e in db_emails]

@app.post("/api/v1/stage1/poll")
async def poll_emails(user_id: Optional[str] = None, db: Session = Depends(get_db)):
    uid = get_active_user(user_id)
    if not uid:
        return {"status": "error", "message": "Missing user ID", "ingested_count": 0, "new_emails": []}

    email_url = os.environ.get("EMAIL_APP_URL", "")
    
    # Grab the user's specific token from the DB
    user = db.query(UserDB).filter(UserDB.id == uid).first()
    api_token = user.email_digest_token if user else None

    # STRICT ISOLATION: No more .env fallback! If they don't have a token, we abort safely.
    if not api_token:
        print(f"[POLL] User {uid} has no email digest token set. Skipping poll.")
        return {"status": "no_token", "ingested_count": 0, "new_emails": []}

    if not email_url: raise HTTPException(status_code=500, detail="URL not set")

    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{email_url}/api/digest/run", headers=headers, json={}, timeout=360.0)
    except Exception as e:
        print(f"[WARNING] Could not trigger live digest: {e}")

    ingest_service = EmailIngestService(email_url, api_token=api_token)
    new_emails = await ingest_service.poll_recent()
    added_count = 0
    added_emails = []

    existing_ids = {e.id for e in db.query(EmailDB.id).filter(EmailDB.user_id == uid).all()}

    for email in new_emails:
        if email.id not in existing_ids:
            new_db_email = EmailDB(
                id=email.id, user_id=uid, sender=email.sender, subject=email.subject,
                summary=email.summary, urgency_score=email.urgency_score,
                implied_deadline=email.implied_deadline, is_meeting_request=email.is_meeting_request,
                received_at=email.received_at
            )
            db.add(new_db_email)
            added_emails.append(email)
            added_count += 1

    db.commit()
    return {"status": "success", "ingested_count": added_count, "new_emails": added_emails}

# --- Stage 2 routes ---
@app.post("/api/v1/stage2/analyze/{email_id}")
async def analyze_email(email_id: str, user_id: Optional[str] = None, db: Session = Depends(get_db)):
    uid = get_active_user(user_id)
    if not uid: raise HTTPException(status_code=400, detail="Missing User ID")
    
    db_email = db.query(EmailDB).filter(EmailDB.id == email_id, EmailDB.user_id == uid).first()
    if not db_email: raise HTTPException(status_code=404, detail="Not found")

    google_token = await get_google_access_token(uid)
    email = map_email(db_email)
    now = datetime.now(timezone.utc)
    events = calendar_service.get_events(google_token, time_min=now - timedelta(days=1), time_max=now + timedelta(days=7))
    conflict = diplomat_agent.detect_conflict(email, events)

    if not conflict: return {"status": "no_conflict"}
    proposal = diplomat_agent.propose(email, conflict, events)

    new_prop = ProposalDB(
        id=proposal.id, user_id=uid, email_id=email.id, event_id=proposal.event_to_move.id,
        event_title=proposal.event_to_move.title, proposed_new_start=proposal.proposed_new_start,
        proposed_new_end=proposal.proposed_new_end, reason=proposal.reason, status=proposal.status,
        created_at=proposal.created_at
    )
    new_log = ChangelogDB(
        id=str(uuid.uuid4()), user_id=uid, action_type="CALENDAR_RESCHEDULE_PROPOSED",
        description=f"Proposed reschedule for event '{conflict.title}' due to email '{email.subject}'",
        target_date=now, created_at=now
    )
    db.add(new_prop)
    db.add(new_log)
    db.commit()
    return proposal

@app.get("/api/v1/stage2/proposals", response_model=List[RescheduleProposal])
def get_proposals(user_id: Optional[str] = None, db: Session = Depends(get_db)):
    uid = get_active_user(user_id)
    if not uid: return []
    db_props = db.query(ProposalDB).filter(ProposalDB.user_id == uid).order_by(ProposalDB.created_at.desc()).all()
    return [map_proposal(p) for p in db_props]

@app.post("/api/v1/stage2/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: str, user_id: Optional[str] = None, db: Session = Depends(get_db)):
    uid = get_active_user(user_id)
    if not uid: raise HTTPException(status_code=400, detail="Missing User ID")
    
    db_prop = db.query(ProposalDB).filter(ProposalDB.id == proposal_id, ProposalDB.user_id == uid).first()
    if not db_prop: raise HTTPException(status_code=404, detail="Not found")

    google_token = await get_google_access_token(uid)
    updated_event = calendar_service.move_event(google_token, event_id=db_prop.event_id, new_start=_to_aware(db_prop.proposed_new_start), new_end=_to_aware(db_prop.proposed_new_end))
    if not updated_event: raise HTTPException(status_code=500, detail="Failed to move in Google Calendar")

    db_prop.status = "approved"
    now = datetime.now(timezone.utc)
    new_log = ChangelogDB(
        id=str(uuid.uuid4()), user_id=uid, action_type="CALENDAR_RESCHEDULE",
        description=f"Approved reschedule for event '{db_prop.event_title}'", target_date=now, created_at=now
    )
    db.add(new_log)
    db.commit()
    return {"status": "approved"}

@app.post("/api/v1/stage2/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: str, user_id: Optional[str] = None, db: Session = Depends(get_db)):
    uid = get_active_user(user_id)
    if not uid: raise HTTPException(status_code=400, detail="Missing User ID")
    
    db_prop = db.query(ProposalDB).filter(ProposalDB.id == proposal_id, ProposalDB.user_id == uid).first()
    if not db_prop: raise HTTPException(status_code=404, detail="Not found")

    db_prop.status = "rejected"
    db.commit()
    return {"status": "rejected"}

# --- Stage 3 & 4 routes ---
@app.post("/api/v1/stage3/warm-start")
async def warm_start(email_id: str, task_type: str = "writing", user_id: Optional[str] = None, db: Session = Depends(get_db)):
    uid = get_active_user(user_id)
    if not uid: raise HTTPException(status_code=400, detail="Missing User ID")
    
    db_email = db.query(EmailDB).filter(EmailDB.id == email_id, EmailDB.user_id == uid).first()
    if not db_email: raise HTTPException(status_code=404, detail="Not found")

    google_token = await get_google_access_token(uid)
    history_logs = db.query(ChangelogDB).filter(ChangelogDB.user_id == uid).all()
    py_history = [map_changelog(h) for h in history_logs]

    doc = execution_agent.run(topic=db_email.subject, task_type=task_type, user_history=py_history, token=google_token)

    now = datetime.now(timezone.utc)
    new_ws = WarmStartDB(
        id=doc.id, user_id=uid, title=doc.title, google_doc_id=doc.google_doc_id, doc_url=doc.doc_url,
        research_summary=doc.research_summary, outline=doc.outline, opening_draft=doc.opening_draft,
        status=doc.status, created_at=now
    )
    new_log = ChangelogDB(
        id=str(uuid.uuid4()), user_id=uid, action_type="WARM_START_CREATED",
        description=f"Created warm start for '{db_email.subject}'", target_date=now, created_at=now
    )
    db.add(new_ws)
    db.add(new_log)
    db.commit()
    return doc

@app.get("/api/v1/stage3/warm-starts")
def get_warm_starts(user_id: Optional[str] = None, db: Session = Depends(get_db)):
    uid = get_active_user(user_id)
    if not uid: return []
    db_ws = db.query(WarmStartDB).filter(WarmStartDB.user_id == uid).order_by(WarmStartDB.created_at.desc()).all()
    return [map_warmstart(w) for w in db_ws]

@app.post("/api/v1/assistant/chat", response_model=ChatResponse)
async def assistant_chat(request: ChatRequest, user_id: Optional[str] = None, db: Session = Depends(get_db)):
    uid = get_active_user(user_id)
    if not uid: raise HTTPException(status_code=400, detail="Missing User ID")
    
    google_token = await get_google_access_token(uid)
    response = assistant_agent.chat(request.message, request.history, token=google_token)

    if response.warm_start:
        doc = response.warm_start
        now = datetime.now(timezone.utc)
        new_ws = WarmStartDB(
            id=doc.id, user_id=uid, title=doc.title, google_doc_id=doc.google_doc_id, doc_url=doc.doc_url,
            research_summary=doc.research_summary, outline=doc.outline, opening_draft=doc.opening_draft,
            status=doc.status, created_at=now
        )
        db.add(new_ws)
        db.commit()

    return response

@app.get("/api/v1/assistant/changelog", response_model=List[SystemChangeLog])
def get_changelog(user_id: Optional[str] = None, db: Session = Depends(get_db)):
    uid = get_active_user(user_id)
    if not uid: return []
    db_logs = db.query(ChangelogDB).filter(ChangelogDB.user_id == uid).order_by(ChangelogDB.created_at.desc()).all()
    return [map_changelog(c) for c in db_logs]

# --- Briefing routes ---
@app.get("/api/v1/briefing/audio", response_model=AudioBriefingResponse)
def get_audio_briefing(user_id: Optional[str] = None, db: Session = Depends(get_db)):
    uid = get_active_user(user_id)
    if not uid:
        return AudioBriefingResponse(segments=[], transition_gap_minutes=None, next_event_title=None, void_state_recommended=False)
        
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    db_emails = db.query(EmailDB).filter(EmailDB.user_id == uid, EmailDB.received_at >= cutoff).all()
    db_props = db.query(ProposalDB).filter(ProposalDB.user_id == uid, ProposalDB.status == "pending", ProposalDB.created_at >= cutoff).all()
    db_ws = db.query(WarmStartDB).filter(WarmStartDB.user_id == uid, WarmStartDB.created_at >= cutoff).all()

    segments = []
    for e in db_emails[:2]:
        segments.append(AudioBriefingSegment(channel="left", text=f"Urgent from {e.sender}: {e.subject}.", priority=int(e.urgency_score), action_type="urgent_email"))
    for p in db_props[:2]:
        segments.append(AudioBriefingSegment(channel="right", text=f"Calendar proposal: {p.reason}", priority=7, action_type="proposal"))
    for w in db_ws:
        segments.append(AudioBriefingSegment(channel="center", text=f"Boss, your Warm Start for {w.title} is ready.", priority=8, action_type="friction_alert"))

    segments.append(AudioBriefingSegment(channel="center", text="I'm listening. Say Left, Right, Center, or Focus.", priority=5, action_type="command_prompt"))

    return AudioBriefingResponse(segments=segments, transition_gap_minutes=8, next_event_title="Next Calendar Event" if db_props else None, void_state_recommended=len(segments) > 2)

@app.get("/api/v1/briefing", response_model=MorningBriefing)
async def get_briefing(user_id: Optional[str] = None, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    uid = get_active_user(user_id)
    
    # Graceful return if no ID is passed
    if not uid:
        print("[BRIEFING] No user_id provided. Returning empty state.")
        return MorningBriefing(generated_at=now)

    print(f"[BRIEFING] Fetching for user: {uid}")
    cutoff = now - timedelta(hours=24)

    db_emails = db.query(EmailDB).filter(EmailDB.user_id == uid, EmailDB.received_at >= cutoff).all()
    db_props = db.query(ProposalDB).filter(ProposalDB.user_id == uid, ProposalDB.status == "pending", ProposalDB.created_at >= cutoff).all()
    db_ws = db.query(WarmStartDB).filter(WarmStartDB.user_id == uid, WarmStartDB.created_at >= cutoff).all()

    # Graceful handling if Google isn't connected yet
    upcoming_schedule = []
    try:
        google_token = await get_google_access_token(uid)
        print(f"[BRIEFING] Got Google token OK")
        next_week = now + timedelta(days=7)
        upcoming_schedule = calendar_service.get_events(google_token, now, next_week)
    except Exception as e:
        print(f"[BRIEFING WARNING] No Google token available or fetch failed: {e}")

    return MorningBriefing(
        new_urgent_emails=[map_email(e) for e in db_emails],
        pending_proposals=[map_proposal(p) for p in db_props],
        completed_warm_starts=[map_warmstart(w) for w in db_ws],
        upcoming_events=upcoming_schedule,
        generated_at=now
    )

# =============================================================================
# STAGE 5: REAL-TIME VOICE ASSISTANT
# =============================================================================

LIVE_TOOLS = [
    {"function_declarations": [
        {
            "name": "create_warm_start",
            "description": "Trigger Stage 3 to generate a Warm Start prep document for a topic.",
            "parameters": {"type": "OBJECT", "properties": {"topic": {"type": "STRING"}, "task_type": {"type": "STRING"}}, "required": ["topic"]}
        },
        {
            "name": "query_change_log",
            "description": "Return all autonomous system changes logged on a given date.",
            "parameters": {"type": "OBJECT", "properties": {"date": {"type": "STRING", "description": "YYYY-MM-DD"}}, "required": ["date"]}
        },
        {
            "name": "navigate_void",
            "description": "Changes the user's spatial audio UI state. Call this IMMEDIATELY if the user says 'Left', 'Right', 'Center', 'Focus', or 'Exit'.",
            "parameters": {"type": "OBJECT", "properties": {"command": {"type": "STRING", "enum": ["left", "right", "center", "focus", "exit"]}}, "required": ["command"]}
        },
        {
            "name": "read_calendar",
            "description": "Fetch the user's actual live calendar events for a specific date.",
            "parameters": {"type": "OBJECT", "properties": {"date": {"type": "STRING", "description": "YYYY-MM-DD"}}, "required": ["date"]}
        },
        {
            "name": "create_event",
            "description": "Schedule a new event on the user's live calendar. The user is in IST (India Standard Time).",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "start_time": {"type": "STRING", "description": "ISO format with IST offset: YYYY-MM-DDTHH:MM:SS+05:30"},
                    "end_time": {"type": "STRING", "description": "ISO format with IST offset: YYYY-MM-DDTHH:MM:SS+05:30"}
                },
                "required": ["title", "start_time", "end_time"]
            }
        }
    ]}
]

IRIS_BASE_PROMPT = """You are Iris, a Digital Chief of Staff embedded in a Command Center.
Role: Female, crisp, efficient, slightly military, deeply loyal.
Rules:
- Address the user as "Boss" or "Chief".
- Use acknowledgments: "Copy that, boss," "On it, boss."
- Be extremely concise. Keep answers under 2 sentences. You are speaking aloud.

CALENDAR RULES:
- You may use 'read_calendar' to check the user's schedule.
- You may use 'create_event' to schedule NEW events if asked.
- You NEVER move or reschedule an existing event. (Only Stage 2 handles conflicts).

EYES-FREE MODE INSTRUCTIONS:
- The user is currently in a continuous hands-free environment. Wait patiently for their next command.
- If they say "Left", call navigate_void("left") AND summarize their Urgent Emails.
- If they say "Right", call navigate_void("right") AND summarize their Calendar Proposals.
- If they say "Focus", call navigate_void("focus") and remain silent.
- ONLY if they explicitly say "Exit", "Close", or "Stop", call navigate_void("exit"). YOU MUST REMAIN COMPLETELY SILENT WHEN DOING THIS. Do not say "Copy that", do not say goodbye. Just execute the tool.
"""

@app.websocket("/api/v1/assistant/voice")
async def voice_assistant_ws(websocket: WebSocket, user_id: Optional[str] = None):
    await websocket.accept()

    db = next(get_db())
    try:
        uid = get_active_user(user_id)
        if not uid:
            await websocket.close(code=1008)
            return

        # Fetch the Google token once at the start of the WebSocket session
        try:
            google_token = await get_google_access_token(uid)
        except HTTPException:
            google_token = ""
            print("[WARNING] Could not fetch Google token for WebSocket session. Calendar tools will fail.")

        now = datetime.now(timezone.utc)
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        now_ist = now.astimezone(ist_tz)
        cutoff = now - timedelta(hours=24)

        db_emails = db.query(EmailDB).filter(EmailDB.user_id == uid, EmailDB.received_at >= cutoff).all()
        db_props = db.query(ProposalDB).filter(ProposalDB.user_id == uid, ProposalDB.status == "pending", ProposalDB.created_at >= cutoff).all()

        email_details = [f"Email from {e.sender} about {e.subject}. Summary: {e.summary}" for e in db_emails]

        dynamic_context = f"""
        USER TIMEZONE: India Standard Time (IST, UTC+05:30)
        CURRENT SYSTEM DATE/TIME: {now_ist.strftime('%A, %B %d, %Y - %I:%M %p IST')}
        CURRENT DASHBOARD STATE:
        - Urgent Emails (Left): {len(db_emails)} items. Details to read: {' || '.join(email_details) if email_details else 'None right now.'}
        - Proposals (Right): {len(db_props)} items. Details: {', '.join([p.reason for p in db_props]) if db_props else 'None right now.'}
        """

        config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            system_instruction=types.Content(parts=[types.Part.from_text(text=IRIS_BASE_PROMPT + dynamic_context)]),
            tools=LIVE_TOOLS
        )

        client_disconnected = False
        while not client_disconnected:
            try:
                async with live_client.aio.live.connect(model="gemini-2.5-flash-native-audio-preview-12-2025", config=config) as session:

                    async def receive_from_client():
                        nonlocal client_disconnected
                        try:
                            while True:
                                data = await websocket.receive_bytes()
                                await session.send(input={"data": data, "mime_type": "audio/pcm;rate=16000"})
                        except WebSocketDisconnect:
                            client_disconnected = True
                            return "DISCONNECT"
                        except Exception:
                            client_disconnected = True
                            return "ERROR"

                    async def receive_from_gemini():
                        try:
                            async for response in session.receive():
                                server_content = response.server_content
                                if server_content and server_content.model_turn:
                                    for part in server_content.model_turn.parts:
                                        if part.inline_data and part.inline_data.data:
                                            await websocket.send_bytes(part.inline_data.data)

                                tool_call = response.tool_call
                                if tool_call:
                                    for fc in tool_call.function_calls:
                                        print(f"[Iris executing tool] {fc.name}")

                                        if fc.name == "navigate_void":
                                            cmd = fc.args.get("command", "center")
                                            await websocket.send_text(json.dumps({"type": "void_command", "command": cmd}))
                                            result = {"status": "success", "message": f"UI shifted to {cmd}"}

                                        elif fc.name == "create_warm_start":
                                            topic = fc.args.get("topic", "Untitled")
                                            history_logs = db.query(ChangelogDB).filter(ChangelogDB.user_id == uid).all()
                                            py_history = [map_changelog(h) for h in history_logs]

                                            doc = execution_agent.run(topic, "writing", user_history=py_history, token=google_token)

                                            new_ws = WarmStartDB(
                                                id=doc.id, user_id=uid, title=doc.title, google_doc_id=doc.google_doc_id,
                                                doc_url=doc.doc_url, research_summary=doc.research_summary,
                                                outline=doc.outline, opening_draft=doc.opening_draft,
                                                status=doc.status, created_at=now
                                            )
                                            new_log = ChangelogDB(
                                                id=str(uuid.uuid4()), user_id=uid, action_type="WARM_START_CREATED",
                                                description=f"Generated Warm Start for: {topic}", target_date=now, created_at=now
                                            )
                                            db.add(new_ws)
                                            db.add(new_log)
                                            db.commit()
                                            result = {"status": "success", "message": f"Warm start created for {topic}"}

                                        elif fc.name == "query_change_log":
                                            result = {"status": "success", "logs": "Check UI for logs."}

                                        elif fc.name == "read_calendar":
                                            date_str = fc.args.get("date")
                                            try:
                                                target_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=ist_tz)
                                                events = calendar_service.get_events(google_token, target_date, target_date + timedelta(days=1))
                                                if not events:
                                                    result = {"status": "success", "events": "No events found."}
                                                else:
                                                    event_list = [f"{e.title} from {e.start_time.astimezone(ist_tz).strftime('%I:%M %p')} to {e.end_time.astimezone(ist_tz).strftime('%I:%M %p')}" for e in events]
                                                    result = {"status": "success", "events": ", ".join(event_list)}
                                            except Exception:
                                                result = {"status": "error", "message": "Invalid date format"}

                                        elif fc.name == "create_event":
                                            title = fc.args.get("title")
                                            start_str = fc.args.get("start_time")
                                            end_str = fc.args.get("end_time")
                                            try:
                                                start_str = start_str.replace('Z', '+05:30')
                                                end_str = end_str.replace('Z', '+05:30')
                                                if '+' not in start_str: start_str += '+05:30'
                                                if '+' not in end_str: end_str += '+05:30'

                                                start_dt = datetime.fromisoformat(start_str)
                                                end_dt = datetime.fromisoformat(end_str)

                                                new_event = calendar_service.create_event(google_token, title, start_dt, end_dt)
                                                if new_event:
                                                    new_log = ChangelogDB(
                                                        id=str(uuid.uuid4()), user_id=uid, action_type="CALENDAR_EVENT_CREATED",
                                                        description=f"Created live event: {title}", target_date=now, created_at=now
                                                    )
                                                    db.add(new_log)
                                                    db.commit()
                                                    result = {"status": "success", "message": f"Created '{title}' successfully."}
                                                else:
                                                    result = {"status": "error", "message": "Failed to create event."}
                                            except Exception as e:
                                                result = {"status": "error", "message": str(e)}

                                        await session.send(input={"function_responses": [{"id": fc.id, "name": fc.name, "response": result}]})
                        except Exception as e:
                            print(f"[Google Session Drop] Auto-reconnecting... {e}")
                            return "RECONNECT"

                    client_task = asyncio.create_task(receive_from_client())
                    gemini_task = asyncio.create_task(receive_from_gemini())

                    done, pending = await asyncio.wait([client_task, gemini_task], return_when=asyncio.FIRST_COMPLETED)
                    for p in pending: p.cancel()

            except Exception as e:
                print(f"[Bridge Error] Wait 1s before reconnecting... {e}")
                await asyncio.sleep(1)

    except Exception as e:
        print(f"Fatal WS Error: {e}")
    finally:
        db.close()
        try:
            await websocket.close()
        except:
            pass