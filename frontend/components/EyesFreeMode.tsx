"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { MicOff, Focus, ArrowLeft, ArrowRight } from "lucide-react";
import { playVoidTone } from "@/lib/spatialAudio";
import { useUser } from "@clerk/nextjs";

interface EyesFreeModeProps {
    isActive: boolean;
    onExit: () => void;
    briefingData?: any;
}

export function EyesFreeMode({ isActive, onExit }: EyesFreeModeProps) {
    const { user } = useUser();
    const [mode, setMode] = useState<'idle' | 'briefing' | 'listening' | 'focus'>('idle');

    const wsRef = useRef<WebSocket | null>(null);
    const audioCtxRef = useRef<AudioContext | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const processorRef = useRef<ScriptProcessorNode | null>(null);
    const nextPlayTimeRef = useRef<number>(0);

    const targetPanRef = useRef<number>(0);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const animationRef = useRef<number>(0);

    // ── 1. The Neon Void Canvas Animation ──────────────────────────────────────────
    useEffect(() => {
        if (!isActive || !canvasRef.current) return;
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d')!;
        let time = 0;

        const resize = () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        };
        resize();
        window.addEventListener('resize', resize);

        const animate = () => {
            ctx.fillStyle = '#050505';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;
            const baseRadius = mode === 'focus' ? 20 : 60;

            let strokeColor = '#39FF14'; // Green
            if (mode === 'listening') strokeColor = '#F59E0B'; // Amber
            else if (targetPanRef.current < -0.5) strokeColor = '#06B6D4'; // Cyan
            else if (targetPanRef.current > 0.5) strokeColor = '#F59E0B'; // Amber

            ctx.beginPath();
            ctx.strokeStyle = strokeColor;
            ctx.lineWidth = 2;
            ctx.shadowBlur = 20;
            ctx.shadowColor = ctx.strokeStyle;

            for (let i = 0; i < 360; i += 2) {
                const rad = (i * Math.PI) / 180;
                const noise = Math.sin(i * 0.1 + time) * Math.cos(i * 0.05 + time * 0.5);
                const radius = baseRadius + noise * (mode === 'briefing' ? 50 : 20) + (mode === 'listening' ? 30 : 0);
                const x = centerX + Math.cos(rad) * radius;
                const y = centerY + Math.sin(rad) * radius;
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.closePath();
            ctx.stroke();

            if (mode !== 'focus') {
                const arrowOpacity = 0.3 + Math.sin(time * 2) * 0.2;
                ctx.globalAlpha = arrowOpacity;
                ctx.fillStyle = '#06B6D4'; ctx.fillRect(centerX - 120, centerY - 2, 40, 4);
                ctx.fillStyle = '#F59E0B'; ctx.fillRect(centerX + 80, centerY - 2, 40, 4);
                ctx.fillStyle = '#10B981'; ctx.beginPath(); ctx.arc(centerX, centerY, 4, 0, Math.PI * 2); ctx.fill();
                ctx.globalAlpha = 1.0;
            }

            time += 0.05;
            animationRef.current = requestAnimationFrame(animate);
        };

        animate();
        return () => {
            cancelAnimationFrame(animationRef.current);
            window.removeEventListener('resize', resize);
        };
    }, [isActive, mode]);

    // ── 2. Real-Time Gemini WebSocket Engine ─────────────────────────────────────
    const startLiveAudio = useCallback(async () => {
        if (!user?.id) return;

        try {
            const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const wsUrl = API_BASE.replace(/^http/, "ws") + `/api/v1/assistant/voice?user_id=${user.id}`;
            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
            const audioCtx = new AudioContext({ sampleRate: 16000 });
            audioCtxRef.current = audioCtx;
            nextPlayTimeRef.current = audioCtx.currentTime;

            ws.binaryType = "arraybuffer";
            ws.onmessage = (event) => {
                if (typeof event.data === "string") {
                    try {
                        const msg = JSON.parse(event.data);
                        if (msg.type === "void_command") {
                            executeAgenticUICommand(msg.command);
                        }
                    } catch (e) { console.error(e); }
                } else if (event.data instanceof ArrayBuffer) {
                    playGeminiAudioChunk(event.data);
                }
            };

            ws.onopen = async () => {
                setMode('listening');
                playVoidTone('center', 'enter');

                // CRITICAL FIX: Add aggressive Echo Cancellation so Iris doesn't hear herself and stop talking
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    }
                });
                streamRef.current = stream;

                const source = audioCtx.createMediaStreamSource(stream);
                const processor = audioCtx.createScriptProcessor(4096, 1, 1);
                processorRef.current = processor;

                processor.onaudioprocess = (e) => {
                    if (ws.readyState !== WebSocket.OPEN) return;
                    const float32Array = e.inputBuffer.getChannelData(0);
                    const int16Array = new Int16Array(float32Array.length);
                    for (let i = 0; i < float32Array.length; i++) {
                        const s = Math.max(-1, Math.min(1, float32Array[i]));
                        int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                    }
                    ws.send(int16Array.buffer);
                };

                source.connect(processor);
                processor.connect(audioCtx.destination);
            };

            ws.onclose = () => handleExit();
        } catch (err) {
            console.error("Failed to start live audio in Void", err);
            handleExit();
        }
    }, [user?.id]);

    const playGeminiAudioChunk = (arrayBuffer: ArrayBuffer) => {
        const audioCtx = audioCtxRef.current;
        if (!audioCtx) return;

        const int16Array = new Int16Array(arrayBuffer);
        const float32Array = new Float32Array(int16Array.length);
        for (let i = 0; i < int16Array.length; i++) {
            float32Array[i] = int16Array[i] / 0x8000;
        }

        const audioBuffer = audioCtx.createBuffer(1, float32Array.length, 24000);
        audioBuffer.copyToChannel(float32Array, 0);

        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;

        const panner = audioCtx.createStereoPanner();
        panner.pan.value = targetPanRef.current;

        source.connect(panner);
        panner.connect(audioCtx.destination);

        // CRITICAL FIX: Add a tiny 50ms buffer pad to ensure audio doesn't stutter mid-sentence
        const currentTime = audioCtx.currentTime;
        if (currentTime < nextPlayTimeRef.current) {
            source.start(nextPlayTimeRef.current);
            nextPlayTimeRef.current += audioBuffer.duration;
        } else {
            source.start(currentTime + 0.05);
            nextPlayTimeRef.current = currentTime + 0.05 + audioBuffer.duration;
        }

        if (mode !== 'focus') setMode('briefing');
    };

    // ── 3. Agentic UI Executor ───────────────────────────────────────────────────
    const executeAgenticUICommand = (cmd: string) => {
        if (cmd === 'left') {
            targetPanRef.current = -0.8;
            playVoidTone('left', 'pulse');
        } else if (cmd === 'right') {
            targetPanRef.current = 0.8;
            playVoidTone('right', 'pulse');
        } else if (cmd === 'center') {
            targetPanRef.current = 0;
            playVoidTone('center', 'pulse');
        } else if (cmd === 'focus') {
            targetPanRef.current = 0;
            setMode('focus');
            playVoidTone('center', 'enter');
        } else if (cmd === 'exit') {
            handleExit(); // Let the UI formally shut down the connection
        }
    };

    useEffect(() => {
        if (isActive) {
            targetPanRef.current = 0;
            startLiveAudio();
        }
    }, [isActive, startLiveAudio]);

    const handleExit = useCallback(() => {
        setMode('idle');
        playVoidTone('center', 'exit');
        if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
        if (processorRef.current) { processorRef.current.disconnect(); processorRef.current = null; }
        if (streamRef.current) { streamRef.current.getTracks().forEach((t) => t.stop()); streamRef.current = null; }
        if (audioCtxRef.current) { audioCtxRef.current.close(); audioCtxRef.current = null; }
        onExit();
    }, [onExit]);

    const triggerManualNav = (cmd: string) => {
        executeAgenticUICommand(cmd);
    };

    if (!isActive) return null;

    return (
        <div className="fixed inset-0 z-[200] bg-[#050505]">
            <canvas ref={canvasRef} className="absolute inset-0" />

            <div className="absolute bottom-8 left-0 right-0 flex justify-center items-center gap-8">
                <button onClick={() => triggerManualNav('left')} className="p-3 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/20 z-10">
                    <ArrowLeft size={20} />
                </button>

                <button onClick={handleExit} className="p-4 rounded-full border bg-red-500/20 border-red-500/50 text-red-400 hover:bg-red-500/30 animate-pulse z-10">
                    <MicOff size={24} />
                </button>

                <button onClick={() => triggerManualNav('focus')} className="p-3 rounded-full bg-slate-500/10 border border-slate-500/30 text-slate-400 hover:bg-slate-500/20 z-10">
                    <Focus size={20} />
                </button>

                <button onClick={() => triggerManualNav('right')} className="p-3 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 hover:bg-amber-500/20 z-10">
                    <ArrowRight size={20} />
                </button>
            </div>

            <div className="absolute top-8 left-0 right-0 text-center">
                <p className="text-emerald-400/60 text-xs tracking-[0.3em] uppercase font-mono">
                    {mode === 'focus' ? 'Deep Focus — Iris Silent' : 'Live Voice Active. Say "Left", "Right", or "Exit"'}
                </p>
            </div>
        </div>
    );
}