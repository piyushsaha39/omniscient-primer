"use client";

import { useState, useEffect } from "react";
import { SignIn, UserButton, useUser } from "@clerk/nextjs";
import MorningBriefing from "../components/MorningBriefing";
import AgentChatbox from "../components/AgentChatbox";
import { EyesFreeMode } from "../components/EyesFreeMode";
import SettingsModal from "../components/SettingsModal";
import { playVoidTone } from "../lib/spatialAudio";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  // CLERK AUTHENTICATION HOOK
  const { isLoaded, isSignedIn, user } = useUser();

  const [briefingVersion, setBriefingVersion] = useState(0);
  const [isInitializing, setIsInitializing] = useState(true);

  // Settings State
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Eyes-Free State
  const [eyesFreeActive, setEyesFreeActive] = useState(false);
  const [audioBriefing, setAudioBriefing] = useState(null);

  // We start the mouse off-screen so it doesn't blink in the corner
  const [mousePos, setMousePos] = useState({ x: -1000, y: -1000 });

  // 1. Universal Mouse Tracker
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  // 2. JIT Polling Logic
  useEffect(() => {
    // Only run if signed in AND the user object is fully loaded
    if (!isSignedIn || !user) return;

    async function runJITPoll() {
      try {
        console.log("Waiting 1 second for backend to initialize...");
        await new Promise((resolve) => setTimeout(resolve, 1000));

        console.log("Triggering Just-In-Time Email Digest...");
        // We pass the Clerk user.id to the backend here!
        if (user && user.id) {
          await fetch(`${API_URL}/api/v1/stage1/poll?user_id=${user.id}`, { method: "POST" });
        }
        console.log("Background digest complete!");
      } catch (err) {
        console.error("Initialization poll failed:", err);
      } finally {
        setIsInitializing(false);
      }
    }

    runJITPoll();
  }, [isSignedIn, user]);

  // 3. Eyes-Free Transition Gap Polling
  useEffect(() => {
    if (isInitializing || eyesFreeActive || !isSignedIn || !user) return;

    const checkTransitions = async () => {
      try {
        // We pass the Clerk user.id to the backend here!
        const res = await fetch(`${API_URL}/api/v1/briefing/audio?user_id=${user.id}`);
        if (!res.ok) return;
        const data = await res.json();

        if (data.void_state_recommended && data.transition_gap_minutes && data.transition_gap_minutes < 10) {
          setAudioBriefing(data);
          setEyesFreeActive(true);
          playVoidTone('center', 'enter');
        }
      } catch (e) {
        console.error('Transition check failed', e);
      }
    };

    //const interval = setInterval(checkTransitions, 60000);
    //return () => clearInterval(interval);
  }, [isInitializing, eyesFreeActive, isSignedIn, user]);

  // Manual trigger for Eyes-Free mode
  const handleEyesFreeToggle = async () => {
    if (eyesFreeActive) {
      setEyesFreeActive(false);
      playVoidTone('center', 'exit');
    } else {
      try {
        // We pass the Clerk user.id to the backend here!
        const res = await fetch(`${API_URL}/api/v1/briefing/audio?user_id=${user?.id}`);
        const data = await res.json();
        setAudioBriefing(data);
        setEyesFreeActive(true);
      } catch (e) {
        console.error("Failed to fetch audio briefing", e);
      }
    }
  };

  // --- RENDERING LOGIC ---

  if (!isLoaded) {
    return <div className="min-h-screen bg-[#050505]" />;
  }

  if (!isSignedIn) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#050505] relative w-full">
        <div className="fixed inset-0 w-full h-full z-0 pointer-events-none bg-[radial-gradient(ellipse_at_top,rgba(47,248,1,0.05),transparent_50%)]"></div>
        <div className="relative z-10">
          <SignIn routing="hash" />
        </div>
      </div>
    );
  }

  if (isInitializing) {
    return (
      <div className="bg-[#050505] text-on-surface min-h-screen overflow-hidden antialiased relative w-full flex items-center justify-center">
        <style>{`
          .film-grain {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            pointer-events: none;
            z-index: 10;
            opacity: 0.04;
            background-image: url('data:image/svg+xml,%3Csvg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg"%3E%3Cfilter id="noiseFilter"%3E%3CfeTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" stitchTiles="stitch"/%3E%3C/filter%3E%3Crect width="100%25" height="100%25" filter="url(%23noiseFilter)"/%3E%3C/svg%3E');
          }
          @keyframes custom-progress {
            0% { transform: translateX(-100%); width: 20%; }
            50% { width: 40%; }
            100% { transform: translateX(300%); width: 20%; }
          }
          .animate-custom-progress {
            animation: custom-progress 2s ease-in-out infinite;
          }
          @keyframes fade-in-up {
            0% { opacity: 0; transform: translateY(20px); }
            100% { opacity: 1; transform: translateY(0); }
          }
          .animate-fade-in-up {
            animation: fade-in-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
          }
        `}</style>
        <div className="film-grain"></div>

        <div className="fixed inset-0 w-full h-full z-0 pointer-events-none bg-[radial-gradient(ellipse_at_left,rgba(47,248,1,0.06),transparent_60%)]"></div>
        <div className="fixed inset-0 w-full h-full z-0 pointer-events-none bg-[radial-gradient(ellipse_at_right,rgba(0,221,221,0.1),transparent_50%)]"></div>

        <div
          className="fixed w-[400px] h-[400px] bg-secondary-container/15 rounded-full blur-[100px] z-0 pointer-events-none transition-transform duration-75 ease-out"
          style={{
            left: mousePos.x,
            top: mousePos.y,
            transform: 'translate(-50%, -50%)'
          }}
        ></div>

        <main className="relative z-20 flex flex-col items-center justify-center w-full max-w-md px-gutter">
          <div className="bg-[#131313]/40 backdrop-blur-[24px] border border-white/10 shadow-[0_25px_50px_-12px_rgba(0,0,0,0.5)] rounded-xl w-full p-lg flex flex-col items-center text-center transform transition-all duration-1000 scale-100 opacity-100 animate-fade-in-up">
            <div className="mb-margin relative">
              <div className="w-16 h-16 border-[3px] border-[#2ff801]/10 border-t-[#2ff801] rounded-full animate-spin shadow-[0_0_20px_rgba(47,248,1,0.3)]"></div>
              <div className="absolute inset-0 m-auto w-4 h-4 bg-secondary-container rounded-full animate-pulse blur-[2px]"></div>
            </div>

            <h1 className="font-headline-lg text-headline-lg text-on-surface mb-sm tracking-tight [text-shadow:0_0_10px_rgba(229,226,225,0.2)]">
              Synchronizing with <span className="text-secondary-fixed [text-shadow:0_0_15px_rgba(47,248,1,0.4)]">the Void</span>...
            </h1>

            <p className="font-body-md text-body-md text-on-surface-variant opacity-80 animate-pulse">
              Establishing secure connection sequence
            </p>

            <div className="w-full h-[2px] bg-white/10 rounded-full mt-margin overflow-hidden relative">
              <div className="absolute top-0 left-0 h-full bg-secondary-container w-1/3 rounded-full animate-custom-progress" style={{ boxShadow: '0 0 10px rgba(47, 248, 1, 0.5)' }}></div>
            </div>

            <div className="mt-xs flex justify-between w-full font-label-caps text-label-caps text-on-surface-variant/50">
              <span>TX: </span>
              <span>RX: <span className="text-secondary-container/70">AWAITING</span></span>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <>
      {/* Top Right Controls (Settings + Profile) */}
      <div className="absolute top-4 right-6 z-50 flex items-center gap-4">
        <button
          onClick={() => setIsSettingsOpen(true)}
          className="w-8 h-8 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-white/70 hover:text-white hover:bg-white/10 transition-all shadow-lg backdrop-blur-md"
          title="Settings"
        >
          <span className="material-symbols-outlined text-[18px]">settings</span>
        </button>
        <UserButton />
      </div>

      <div className="bg-[#050505] text-on-surface min-h-screen flex overflow-hidden antialiased w-full relative">
        <div
          className="fixed w-[600px] h-[600px] rounded-full blur-[100px] pointer-events-none transition-transform duration-75 ease-out z-[100] mix-blend-screen"
          style={{
            background: 'radial-gradient(circle, rgba(47, 248, 1, 0.15) 0%, rgba(47, 248, 1, 0) 70%)',
            left: mousePos.x,
            top: mousePos.y,
            transform: 'translate(-50%, -50%)'
          }}
        ></div>

        <div className="flex-1 overflow-y-auto z-10 relative">
          <MorningBriefing refreshKey={briefingVersion} />
        </div>
        <div className="w-[450px] flex-shrink-0 flex flex-col hidden lg:flex border-l border-white/10 z-20 py-4 pr-4 relative">
          <AgentChatbox
            onBriefingUpdate={() => setBriefingVersion(v => v + 1)}
            onEyesFreeTrigger={handleEyesFreeToggle}
            isEyesFreeActive={eyesFreeActive}
          />
        </div>
      </div>

      <EyesFreeMode
        isActive={eyesFreeActive}
        onExit={() => setEyesFreeActive(false)}
        briefingData={audioBriefing}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </>
  );
}