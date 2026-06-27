import httpx
import os
from datetime import datetime
from typing import List
from app.models import EmailSignal

class EmailIngestService:
    # 1. We added api_token as a parameter here so it can be injected dynamically!
    def __init__(self, email_app_url: str, api_token: str = ""):
        self.email_app_url = email_app_url.rstrip('/')
        self.api_token = api_token

    async def poll_recent(self, since_hours: int = 24) -> List[EmailSignal]:
        signals = []
        if not self.email_app_url:
            return signals

        headers = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.email_app_url}/api/emails/recent", 
                    headers=headers,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                print("\n--- DEBUG: RENDER API RESPONSE ---")
                print(f"Data type: {type(data)}")
                print(f"Raw data: {data[:2] if isinstance(data, list) else data}") # Print safe slice
                
                # If data is a dictionary (e.g., {"emails": [...]}), this will catch it
                items_to_process = data if isinstance(data, list) else data.get("emails", [])
                
                for item in items_to_process:
                    try:
                        signal = EmailSignal(
                            id=str(item.get("id") or item.get("gmailMessageId", "")),
                            sender=str(item.get("senderEmail") or item.get("sender", "Unknown")),
                            subject=str(item.get("subject", "No Subject")),
                            summary=str(item.get("aiSummary") or item.get("summary", "")),
                            urgency_score=float(item.get("urgencyScore", 0.0)),
                            implied_deadline=None,
                            is_meeting_request=False,
                            received_at=datetime.fromisoformat(
                                item.get("receivedAt", datetime.utcnow().isoformat()).replace("Z", "+00:00")
                            )
                        )
                        signals.append(signal)
                        print(f"[SUCCESS] Mapped email: {signal.subject}")
                    except Exception as e:
                        print(f"[FAILED] Could not map email: {item.get('subject', 'Unknown')}")
                        print(f"        Error details: {e}")

        except Exception as e:
            print(f"Error polling email app: {e}")
            
        return signals