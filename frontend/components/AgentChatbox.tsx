"use client";

import { useState, useRef, useEffect } from "react";
import { Mic, MicOff, Send } from "lucide-react";
import { sendChatMessage } from "@/lib/api";
import { useUser } from "@clerk/nextjs";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface AgentChatboxProps {
  onBriefingUpdate: () => void;
  onEyesFreeTrigger?: () => void;
  isEyesFreeActive?: boolean;
}

export default function AgentChatbox({ onBriefingUpdate, onEyesFreeTrigger, isEyesFreeActive }: AgentChatboxProps) {
  const { user } = useUser();
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Greetings, boss. I've processed your overnight signals. Ask me anything, or tell me what to start working on.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false); // STT State

  const bottomRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const [micPressTimer, setMicPressTimer] = useState<NodeJS.Timeout | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // ── 1. Native Browser Speech-to-Text (STT) Engine ───────────────────────────
  const startListening = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Speech Recognition is not supported in this browser. Please use Chrome or Edge.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onresult = (event: any) => {
      // Transcribe speech and populate the text input field
      const transcript = event.results[0][0].transcript;
      setInput(transcript);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.onerror = (event: any) => {
      console.error("Speech recognition error", event.error);
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    setIsListening(false);
  };

  // ── 2. Standard Text-Based Chat Engine ──────────────────────────────────────
  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading || !user?.id) return; // Guard clause for user ID

    const userMsg: Message = { role: "user", content: trimmed };
    const updatedHistory = [...messages, userMsg];
    setMessages(updatedHistory);
    setInput("");
    setIsLoading(true);

    try {
      // Hits the standard REST API text endpoint (gemini-3.1-flash)
      const data = await sendChatMessage(
        trimmed,
        messages.map((m) => ({ role: m.role, content: m.content })),
        user.id // Dynamically pass the active user ID
      );

      setMessages([...updatedHistory, { role: "assistant", content: data.reply }]);

      if (data.action_taken === "warm_start_created") {
        onBriefingUpdate();
      }
    } catch {
      setMessages([...updatedHistory, { role: "assistant", content: "System communication failure. Please try again." }]);
    } finally {
      setIsLoading(false);
    }
  };

  // ── 3. Long Press Handlers (Triggers Eyes-Free Mode) ────────────────────────
  const handleMicMouseDown = () => {
    const timer = setTimeout(() => {
      if (onEyesFreeTrigger) onEyesFreeTrigger();
    }, 800); // 800ms hold triggers the Void
    setMicPressTimer(timer);
  };

  const handleMicMouseUp = () => {
    if (micPressTimer) {
      clearTimeout(micPressTimer);
      setMicPressTimer(null);
    }
  };

  const irisify = (text: string) => {
    if (text.startsWith('Boss,') || text.startsWith('Greetings') || text.startsWith('System')) return text;
    return `Boss, ${text}`;
  };

  return (
    <div className="flex flex-col h-full bg-surface-container-lowest/60 backdrop-blur-3xl border border-white/10 rounded-2xl overflow-hidden shadow-[0_0_40px_rgba(0,221,221,0.08)] relative">
      {/* Header */}
      <div className="p-md border-b border-white/10 flex items-center gap-sm relative z-10 bg-black/20 shrink-0">
        <span className="material-symbols-outlined text-tertiary">psychology</span>
        <div>
          <h2 className="font-body-md text-body-md font-bold text-on-surface">AI Assistant</h2>
          <p className="font-body-sm text-body-sm text-tertiary">Online</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 p-md overflow-y-auto flex flex-col gap-md relative z-10">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === "user" ? "justify-end mt-sm" : "gap-sm"}`}>
            {msg.role === "assistant" && (
              <div className="w-8 h-8 rounded-full bg-tertiary/10 border border-tertiary/30 flex-shrink-0 flex items-center justify-center text-tertiary shadow-[0_0_10px_rgba(0,221,221,0.2)]">
                <span className="material-symbols-outlined text-[16px]">smart_toy</span>
              </div>
            )}
            <div className={`${msg.role === "user"
              ? "bg-tertiary/10 backdrop-blur-md border border-tertiary/20 rounded-2xl rounded-tr-sm p-md text-on-surface font-body-sm text-body-sm max-w-[85%] leading-relaxed shadow-lg"
              : "bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl rounded-tl-sm p-md text-on-surface font-body-sm text-body-sm max-w-[85%] leading-relaxed shadow-lg"
              }`}>
              {msg.role === 'assistant' ? (
                <div>
                  <p className="text-[10px] text-tertiary/80 tracking-widest uppercase mb-1 font-mono flex items-center gap-1">
                    <span className="w-1 h-1 rounded-full bg-tertiary animate-pulse"></span>
                    IRIS // ASSISTANT
                  </p>
                  <p>{irisify(msg.content)}</p>
                </div>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex gap-sm">
            <div className="w-8 h-8 rounded-full bg-tertiary/10 border border-tertiary/30 flex-shrink-0 flex items-center justify-center text-tertiary shadow-[0_0_10px_rgba(0,221,221,0.2)]">
              <span className="material-symbols-outlined text-[16px]">smart_toy</span>
            </div>
            <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl rounded-tl-sm p-md text-on-surface font-body-sm text-body-sm max-w-[85%] leading-relaxed shadow-lg animate-pulse">
              Thinking…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input Area */}
      <div className="p-md border-t border-white/10 relative z-10 bg-black/40 backdrop-blur-md shrink-0">
        <div className="relative group">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            disabled={isLoading}
            className="w-full bg-white/5 backdrop-blur-lg border border-white/10 rounded-xl px-md py-sm font-body-md text-body-md text-on-surface placeholder:text-outline/70 focus:outline-none focus:border-tertiary focus:bg-white/10 focus:ring-1 focus:ring-tertiary/50 transition-all shadow-inner pl-md pr-12 disabled:opacity-50"
            placeholder={isListening ? "Listening..." : "Command AI..."}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="absolute right-sm top-1/2 -translate-y-1/2 bg-tertiary/10 text-tertiary hover:bg-tertiary hover:text-black transition-colors p-sm rounded-lg flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <span className="material-symbols-outlined text-[18px]">send</span>
          </button>
        </div>
        <div className="flex justify-between items-center mt-sm px-xs">
          <span className="font-label-caps text-label-caps text-outline/70">
            {isListening ? 'Speech-to-Text active' : 'Press Enter to send'}
          </span>

          <button
            onMouseDown={handleMicMouseDown}
            onMouseUp={handleMicMouseUp}
            onMouseLeave={handleMicMouseUp}
            onTouchStart={handleMicMouseDown}
            onTouchEnd={handleMicMouseUp}
            onClick={() => {
              if (!isEyesFreeActive) {
                isListening ? stopListening() : startListening();
              }
            }}
            className={`transition-all rounded-full p-1.5 ${isListening ? "text-red-400 bg-red-400/10 shadow-[0_0_10px_rgba(248,113,113,0.3)] animate-pulse" : "text-tertiary/70 hover:text-tertiary hover:bg-tertiary/10"
              } ${isEyesFreeActive ? 'text-tertiary shadow-[0_0_15px_rgba(0,221,221,0.5)] animate-pulse' : ''}`}
            title="Click for Speech-to-Text, Hold for Eyes-Free Mode"
          >
            <span className="material-symbols-outlined text-[20px]">
              {isListening ? "mic" : "keyboard_voice"}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}