"use client";

import { useState } from "react";
import { useUser } from "@clerk/nextjs";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SettingsModal({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
    const { user } = useUser();
    const [token, setToken] = useState("");
    const [isSaving, setIsSaving] = useState(false);
    const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");

    if (!isOpen) return null;

    const handleSave = async () => {
        if (!token) return;
        setIsSaving(true);
        setSaveStatus("idle");
        try {
            // We will build this exact endpoint in the FastAPI backend next!
            const res = await fetch(`${API_URL}/api/v1/users/settings`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    clerk_id: user?.id,
                    email_address: user?.primaryEmailAddress?.emailAddress,
                    email_digest_token: token,
                }),
            });

            if (res.ok) {
                setSaveStatus("success");
                setTimeout(() => {
                    onClose();
                    setSaveStatus("idle");
                }, 1500);
            } else {
                setSaveStatus("error");
            }
        } catch (e) {
            console.error(e);
            setSaveStatus("error");
        }
        setIsSaving(false);
    };

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/80 backdrop-blur-sm">
            <div className="bg-[#0a0a0a] border border-white/10 rounded-xl p-8 w-full max-w-md shadow-2xl relative animate-fade-in-up">
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/10 text-white/50 hover:text-white transition-colors"
                >
                    <span className="material-symbols-outlined text-lg">close</span>
                </button>

                <h2 className="text-2xl font-semibold text-white mb-2 tracking-tight">Command Center Integration</h2>
                <p className="text-sm text-white/50 mb-8">
                    Securely link your external microservices to the central intelligence hub.
                </p>

                <div className="space-y-4">
                    <div>
                        <label className="block text-xs font-semibold text-[#2ff801] mb-2 uppercase tracking-widest">
                            Email Digest Identity Token
                        </label>
                        <input
                            type="password"
                            value={token}
                            onChange={(e) => setToken(e.target.value)}
                            placeholder="Paste your EMAIL_APP_TOKEN here..."
                            className="w-full bg-black border border-white/10 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-[#2ff801]/50 focus:ring-1 focus:ring-[#2ff801]/50 transition-all placeholder:text-white/20"
                        />
                        <p className="text-xs text-white/30 mt-3">
                            This token authorizes Iris to pull your stage 1 intelligence signals from your private Render backend.
                        </p>
                    </div>
                </div>

                <div className="mt-8 flex justify-end">
                    <button
                        onClick={handleSave}
                        disabled={isSaving || !token}
                        className="bg-[#2ff801]/10 text-[#2ff801] border border-[#2ff801]/20 px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-[#2ff801]/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                    >
                        {isSaving ? "Synchronizing..." : saveStatus === "success" ? "Link Established" : "Connect Integration"}
                    </button>
                </div>
            </div>
        </div>
    );
}