# OMNISCIENT PRIMER
> The world changes while you sleep. So does your plan — and your work has already started.

### Architecture
A four-stage autonomous pipeline:
Email Digest (Render) -> Calendar Diplomat (Stage 2) -> Execution Agent (Stage 3) -> AI Command Center (Stage 4)

### Google Technologies Used
| Technology | Stage | Purpose |
|---|---|---|
| Gemini API + Search Grounding | Stage 3 | Research grounding for Warm Start docs |
| Gemini Function Calling | Stage 4 | Agent dispatches actions from chat |
| Google Calendar API | Stage 2 | Conflict detection and reschedule proposals |
| Google Docs API | Stage 3 | Auto-generated Warm Start documents |
| Google Drive API | Stage 3 | Document sharing |

### Explicitly Out of Scope
Weather signals, market data, competitor tracking: no genuine connection to personal task/time management. 
Silent calendar mutations: the agent proposes; it never acts without explicit human approval. 
Percentage task completion: replaced by a fixed, verifiable checklist (research summary + outline + opening draft).