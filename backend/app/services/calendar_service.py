from datetime import datetime
from typing import List, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.models import CalendarEvent

class CalendarService:
    def _get_service(self, token: str):
        # We create a fresh service object on the fly using the Clerk token
        creds = Credentials(token=token)
        return build('calendar', 'v3', credentials=creds)

    def get_events(self, token: str, time_min: datetime, time_max: datetime) -> List[CalendarEvent]:
        service = self._get_service(token)
        
        t_min_str = time_min.isoformat()
        if not time_min.tzinfo: t_min_str += 'Z'
            
        t_max_str = time_max.isoformat()
        if not time_max.tzinfo: t_max_str += 'Z'
            
        events_result = service.events().list(
            calendarId='primary',
            timeMin=t_min_str,
            timeMax=t_max_str,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        items = events_result.get('items', [])
        calendar_events = []
        
        for item in items:
            start_info = item.get('start', {})
            end_info = item.get('end', {})
            if 'dateTime' not in start_info or 'dateTime' not in end_info: continue
                
            start_dt = datetime.fromisoformat(start_info.get('dateTime').replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_info.get('dateTime').replace('Z', '+00:00'))
            
            calendar_events.append(CalendarEvent(
                id=item.get('id'),
                title=item.get('summary', 'Untitled Event'),
                start_time=start_dt,
                end_time=end_dt
            ))
            
        return calendar_events

    def move_event(self, token: str, event_id: str, new_start: datetime, new_end: datetime):
        service = self._get_service(token)
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
        event['start']['dateTime'] = new_start.isoformat()
        event['end']['dateTime'] = new_end.isoformat()
        
        return service.events().update(calendarId='primary', eventId=event_id, body=event).execute()

    def create_event(self, token: str, title: str, start: datetime, end: datetime):
        service = self._get_service(token)
        event = {
            'summary': title,
            'start': {'dateTime': start.isoformat()},
            'end': {'dateTime': end.isoformat()},
        }
        return service.events().insert(calendarId='primary', body=event).execute()