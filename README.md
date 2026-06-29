# Omniscient Primer 👁️
### A Pre-Cognitive Productivity Companion

## Project Overview
Most productivity tools follow a reactive model: you input a task, the AI schedules it, and reminds you[cite: 1]. **Omniscient Primer** replaces this with a pre-cognitive model[cite: 1]. The system watches real signals from your life—specifically your inbox and calendar—and when urgent, time-sensitive items appear, it autonomously begins the work *before* you even open the app[cite: 1]. 

The one-line pitch: *"The world changes while you sleep. So does your plan — and your work has already started."*[cite: 1]

## The Four-Stage Pipeline
The architecture is built on a seamless, four-stage automated pipeline[cite: 1, 7]:

* **Stage 1: World-State Signal (Email Urgency):** Integrates directly with an external Node.js email digest app using Just-In-Time (JIT) polling and Clerk authentication to ingest urgent emails[cite: 3, 6, 8].
* **Stage 2: Calendar Diplomat (Reactive Scheduling):** Reads your live Google Calendar to detect conflicts created by urgent emails and proposes intelligent reschedules for historically movable meetings[cite: 1, 3, 7]. **Hard Safety Constraint:** The agent proposes reschedules but *never* executes a calendar move without explicit human approval[cite: 1, 7].
* **Stage 3: Execution Agent (Warm Start):** Pre-completes preparatory work (research summaries, structured outlines, and opening drafts) via the Google Docs API and Gemini to eliminate the "blank page" barrier[cite: 1, 7].
* **Stage 4: Conversational Command Center:** A split-screen Next.js dashboard featuring a voice-enabled AI assistant that utilizes Gemini Function Calling to dispatch tasks, query the system audit log, and schedule work blocks[cite: 1, 7].

## ✨ Key Features
* **Bidirectional Voice Interface:** Uses `gemini-live-2.5-flash-native-audio` over WebSockets for a sub-second, real-time streaming voice interface ("Iris") capable of reading your calendar and creating events[cite: 3].
* **Eyes-Free Spatial Audio Mode:** A hands-free "Void" state using the Web Audio API's `StereoPannerNode` to deliver spatial audio, panning urgent emails to the left ear, proposals to the right, and the AI to the center[cite: 3].
* **Procrastination Forensics:** The Execution Agent decomposes large tasks, calculates friction scores against historical data, and pre-loads starter content specifically for predicted "stall zones"[cite: 3].
* **Neon Void Glassmorphism UI:** A cyberpunk-inspired dark aesthetic featuring a reactive mouse-tracking flashlight effect, dynamic JIT polling loaders, and a 7-day live calendar timeline[cite: 3, 6].
* **Multi-Tenant Architecture:** Fully secured with Clerk OAuth and a relational SQLAlchemy/SQLite database to ensure strict user data isolation and dynamic token management[cite: 3].

## 🛠️ Tech Stack
* **Frontend:** Next.js 14 (App Router), React, Tailwind CSS, Clerk (Authentication), Web Speech API, Web Audio API.
* **Backend:** Python 3.11, FastAPI, Uvicorn, SQLAlchemy, SQLite[cite: 3, 7].
* **AI Engine:** Google AI Studio utilizing `gemini-3.1-flash-lite` (Text/Tooling) and `gemini-live-2.5-flash-native-audio` (Live Voice WebSocket Bridge)[cite: 3].
* **Integrations:** Google Calendar API, Google Docs API, Google Drive API[cite: 4, 7].

## ⚙️ Prerequisites & Environment Setup
To run this project locally, configure the following environment variables.

**Backend (`backend/.env`):**
```env
GEMINI_API_KEY=your_google_ai_studio_key
CLERK_SECRET_KEY=your_clerk_secret_key
GOOGLE_CREDENTIALS_JSON={"token":"...","refresh_token":"...","client_id":"...","client_secret":"..."}
Frontend (frontend/.env.local):


Code snippet
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key


Installation & Quick Start
1. Backend Startup
Bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000 --env-file .env

2. Frontend Startup
Bash
cd frontend
npm install
npm run dev
  
The application will be available at http://localhost:3000. 

🎬 Live Demo Script (Verification Flow)
Initialize: Open the app to view the "Synchronizing with the Void" loader as it executes JIT polling for urgent emails.  

Review: Observe the Morning Briefing (left pane) showing urgent signals and pending calendar proposals.  

Approve: Tap "Approve & Reschedule" to trigger the hard-gated Google Calendar API move.  

Generate: Tap "Generate Warm Start" to trigger Gemini search grounding and Google Doc creation.  

Interact: Long-press the microphone to activate the Eyes-Free Spatial Audio mode and converse with the Gemini Live API to schedule a new task