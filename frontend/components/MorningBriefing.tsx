"use client";

import { useEffect, useState } from "react";
import { getBriefing, approveProposal, rejectProposal, createWarmStart } from "../lib/api";
import { useUser } from "@clerk/nextjs";

type EmailSignal = {
  id: string;
  sender: string;
  subject: string;
  summary: string;
  urgency_score: number;
  implied_deadline?: string;
};

type CalendarEvent = {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
};

type RescheduleProposal = {
  id: string;
  email_id: string;
  event_to_move: CalendarEvent;
  proposed_new_start: string;
  proposed_new_end: string;
  reason: string;
  status: string;
};

type SubtaskProfile = {
  id: string;
  title: string;
  description: string;
  estimated_minutes: number;
  friction_score: number;
  historical_stall: boolean;
  preloaded_content: string;
};

type WarmStartDoc = {
  id: string;
  title: string;
  google_doc_id: string;
  doc_url: string;
  research_summary: string;
  outline: string;
  opening_draft: string;
  is_big_task?: boolean;
  primary_friction_subtask_id?: string;
  subtasks?: SubtaskProfile[];
};

type Briefing = {
  new_urgent_emails: EmailSignal[];
  pending_proposals: RescheduleProposal[];
  completed_warm_starts: WarmStartDoc[];
  upcoming_events: CalendarEvent[];
};

export default function MorningBriefing({ refreshKey = 0 }: { refreshKey?: number }) {
  const { user } = useUser();
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [loading, setLoading] = useState(true);
  const [generatingId, setGeneratingId] = useState<string | null>(null);

  const fetchBriefing = async () => {
    if (!user?.id) return;
    try {
      const res = await getBriefing(user.id);
      setBriefing(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.id) {
      fetchBriefing();
    }
  }, [refreshKey, user?.id]);

  if (loading) {
    return <div className="flex h-full items-center justify-center text-slate-400">Loading briefing...</div>;
  }

  const emails = briefing?.new_urgent_emails || [];
  const proposals = briefing?.pending_proposals || [];
  const warmStarts = briefing?.completed_warm_starts || [];
  const upcomingEvents = briefing?.upcoming_events || [];

  const total = emails.length + proposals.length + warmStarts.length;

  const handleApprove = async (id: string) => {
    if (!user?.id) return;
    await approveProposal(id, user.id);
    fetchBriefing();
  };

  const handleReject = async (id: string) => {
    if (!user?.id) return;
    await rejectProposal(id, user.id);
    fetchBriefing();
  };

  const handleWarmStart = async (emailId: string) => {
    if (!user?.id || generatingId) return;

    setGeneratingId(emailId);
    try {
      await createWarmStart(emailId, user.id);
      await fetchBriefing();
    } catch (err) {
      console.error("Failed to generate warm start:", err);
    } finally {
      setGeneratingId(null);
    }
  };

  // Helper function to group events by Date for the timeline view
  const groupedEvents = upcomingEvents.reduce((acc, event) => {
    const date = new Date(event.start_time).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    if (!acc[date]) acc[date] = [];
    acc[date].push(event);
    return acc;
  }, {} as Record<string, CalendarEvent[]>);

  return (
    <div className="bg-[#050505] text-on-surface min-h-screen overflow-hidden antialiased relative w-full">
      {/* Background Animation Shader & Overlays */}
      <div className="fixed inset-0 w-full h-full z-0 pointer-events-none bg-[radial-gradient(ellipse_at_left,rgba(47,248,1,0.06),transparent_60%)]"></div>
      <div className="fixed inset-0 w-full h-full z-0 pointer-events-none bg-[radial-gradient(ellipse_at_right,rgba(0,221,221,0.1),transparent_50%)]"></div>

      {/* TopAppBar */}
      <nav className="bg-background/80 backdrop-blur-xl border-b border-white/5 shadow-none fixed top-0 w-full flex justify-between items-center px-gutter py-sm z-50">
        <div className="flex flex-col items-start gap-1">
          <div className="flex items-center gap-4">
            <h1 className="font-headline-lg text-headline-lg font-bold text-on-surface">Morning Briefing</h1>

            {/* NEW: Sync Emails Button & Tooltip */}
            <a
              href="https://email-digest-app-dusky.vercel.app/"
              target="_blank"
              rel="noopener noreferrer"
              className="group relative flex items-center gap-2 px-3 py-1.5 rounded-md border border-[#2ff801]/40 bg-[#2ff801]/10 text-[#2ff801] text-xs font-bold tracking-wider uppercase hover:bg-[#2ff801]/20 hover:border-[#2ff801] transition-all shadow-[0_0_10px_rgba(47,248,1,0.15)] hover:shadow-[0_0_20px_rgba(47,248,1,0.3)] cursor-pointer"
            >
              <span className="material-symbols-outlined text-[16px]">sync</span>
              Sync Emails

              {/* Custom Cyberpunk Tooltip */}
              <span className="absolute top-full left-0 mt-3 w-56 p-2.5 bg-[#050505] border border-[#2ff801]/30 rounded-lg text-white/80 text-[11px] leading-relaxed normal-case tracking-normal opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-200 z-[100] shadow-xl">
                Login here, press <strong className="text-[#2ff801]">F12</strong> to get your session token, and paste it in settings (gear).
              </span>
            </a>
          </div>
          <p className="text-sm font-medium text-slate-400 tracking-wide mt-2">
            {total === 0
              ? "All caught up."
              : `${total} things happened overnight. Here's what I already did about them.`}
          </p>
        </div>
      </nav>

      {/* Main Content Grid */}
      <main className="relative z-10 pt-[100px] h-screen max-w-[1200px] mx-auto px-gutter pb-lg grid grid-cols-1 gap-lg">
        {/* Left Column: Signals Feed */}
        <section className="flex flex-col gap-md overflow-y-auto pr-sm pb-xl" style={{ height: "calc(100vh - 120px)" }}>

          <div className="flex items-center justify-between mb-sm">
            <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface">
              {total === 0 ? "All caught up." : "Urgent Signals"}
            </h2>
            <div className="flex items-center gap-xs text-secondary-container bg-secondary-container/10 px-sm py-xs rounded-full border border-secondary-container/20">
              <span className="w-2 h-2 rounded-full bg-secondary-container animate-pulse"></span>
              <span className="font-label-caps text-label-caps">LIVE</span>
            </div>
          </div>

          {/* Urgent Emails */}
          {emails.length > 0 && (
            <div className="space-y-4 mb-10 h-auto">
              {emails.map((email) => (
                <article key={email.id} className="relative p-5 h-auto rounded-xl bg-surface-container-low/40 backdrop-blur-2xl border border-white/10 group hover:border-secondary-container/30 transition-all duration-300 overflow-hidden shadow-[0_0_20px_rgba(47,248,1,0.05)]">
                  <div className="absolute top-0 left-0 w-full h-[2px] bg-secondary-container"></div>
                  <div className="absolute -top-10 -right-10 w-32 h-32 bg-secondary-container/20 blur-[40px] rounded-full pointer-events-none"></div>

                  <div className="flex justify-between items-start mb-4 relative z-10">
                    <div className="flex items-center gap-sm">
                      <div className="w-10 h-10 rounded-full bg-surface-bright/50 border border-white/5 flex items-center justify-center text-primary">
                        <span className="material-symbols-outlined">mail</span>
                      </div>
                      <div>
                        <h3 className="font-body-md text-body-md font-bold text-on-surface truncate pr-4">{email.subject}</h3>
                        <p className="font-body-sm text-body-sm text-on-surface-variant">{email.sender}</p>
                      </div>
                    </div>
                    <div className="flex flex-col items-end">
                      <span className="font-label-caps text-label-caps text-secondary-container mb-xs">URGENCY</span>
                      <span className="font-headline-lg text-headline-lg text-secondary-container">{email.urgency_score.toFixed(1)}</span>
                    </div>
                  </div>

                  <div className="mb-4 relative z-10">
                    <p className="font-body-md text-body-md text-on-surface-variant line-clamp-2">{email.summary}</p>
                  </div>

                  <div className="flex justify-between items-center relative z-10 border-t border-white/5 pt-4">
                    <span className="font-body-sm text-body-sm text-outline">
                      {email.implied_deadline ? `Deadline: ${new Date(email.implied_deadline).toLocaleString()}` : 'Just now'}
                    </span>
                    <button
                      onClick={() => handleWarmStart(email.id)}
                      disabled={generatingId !== null}
                      className={`bg-secondary-container text-tertiary-container hover:bg-secondary-fixed active:scale-95 transition-all duration-200 px-md py-sm rounded-lg font-body-md text-body-md font-semibold flex items-center gap-xs ${generatingId === email.id ? "animate-pulse cursor-wait opacity-80" : "disabled:opacity-50 disabled:cursor-not-allowed"}`}
                    >
                      <span className="material-symbols-outlined text-[20px]">bolt</span>
                      {generatingId === email.id ? "Analyzing Email..." : "Generate Warm Start \u2192"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}

          {/* Calendar Proposals */}
          {proposals.length > 0 && (
            <div className="mb-10">
              <div className="flex items-center gap-2 mb-4">
                <span className="w-2.5 h-2.5 rounded-full bg-tertiary"></span>
                <h2 className="text-xl font-semibold text-on-surface">Calendar Proposals</h2>
              </div>
              <div className="space-y-4">
                {proposals.map((proposal) => (
                  <article key={proposal.id} className="relative p-5 h-auto rounded-xl bg-surface-container-low/40 backdrop-blur-2xl border border-white/10 group hover:border-tertiary/30 transition-all duration-300 overflow-hidden shadow-[0_0_20px_rgba(0,221,221,0.05)]">
                    <div className="absolute top-0 left-0 w-full h-[2px] bg-tertiary"></div>
                    <div className="absolute -top-10 -right-10 w-32 h-32 bg-tertiary/20 blur-[40px] rounded-full pointer-events-none"></div>

                    <div className="mb-4 relative z-10">
                      <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">{proposal.reason}</p>
                    </div>

                    <div className="flex items-center gap-3 mb-3 relative z-10 border-t border-white/5 pt-4">
                      <button
                        onClick={() => handleApprove(proposal.id)}
                        className="bg-tertiary text-black px-4 py-2 rounded font-medium hover:bg-tertiary-fixed transition-colors"
                      >
                        Approve & Reschedule
                      </button>
                      <button
                        onClick={() => handleReject(proposal.id)}
                        className="bg-transparent border border-white/10 text-on-surface px-4 py-2 rounded font-medium hover:bg-white/5 transition-colors"
                      >
                        Reject
                      </button>
                    </div>
                    <p className="text-outline text-xs relative z-10">
                      Hard rule: The agent never moves a calendar event without your explicit tap.
                    </p>
                  </article>
                ))}
              </div>
            </div>
          )}

          {/* Warm Starts */}
          {warmStarts.length > 0 && (
            <div className="mb-10 pb-10 w-full max-w-4xl space-y-md relative">
              <style>{`
                @keyframes pulse-pip {
                  0% { box-shadow: 0 0 0 0 rgba(47, 248, 1, 0.4); }
                  70% { box-shadow: 0 0 0 10px rgba(47, 248, 1, 0); }
                  100% { box-shadow: 0 0 0 0 rgba(47, 248, 1, 0); }
                }
                .pip-urgent {
                  animation: pulse-pip 2s infinite;
                }
              `}</style>
              <div className="absolute -top-10 -left-10 w-64 h-64 bg-secondary-container/10 rounded-full blur-[100px] pointer-events-none"></div>
              <div className="flex items-center space-x-sm mb-sm relative z-10">
                <div className="w-3 h-3 rounded-full bg-secondary-container pip-urgent"></div>
                <h2 className="font-headline-lg text-headline-lg text-on-surface">Warm Starts Ready</h2>
              </div>
              <div className="space-y-4 relative z-10">
                {warmStarts.map((ws) => (
                  <a
                    key={ws.id}
                    href={ws.doc_url}
                    target="_blank"
                    rel="noreferrer"
                    className="block bg-[#201f1f]/40 backdrop-blur-[20px] border border-white/10 rounded-xl p-md shadow-[0_0_20px_rgba(47,248,1,0.15)] relative overflow-hidden group cursor-pointer transition-all duration-300 hover:border-secondary-container/30 hover:bg-surface-container/60"
                  >
                    <div className="absolute top-0 left-0 w-full h-[2px] bg-secondary-container"></div>

                    {ws.is_big_task && (
                      <div className="absolute top-0 right-0 px-3 py-1 bg-amber-500/10 border-b border-l border-amber-500/30 rounded-bl-lg z-20">
                        <span className="text-[10px] text-amber-400 font-mono tracking-wider flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                          IRIS FORENSICS
                        </span>
                      </div>
                    )}

                    <div className="flex flex-col space-y-xs relative z-10">
                      <h3 className="font-headline-lg-mobile text-headline-lg-mobile text-secondary-container transition-colors duration-300 group-hover:text-secondary-fixed pr-24">
                        {ws.title}
                      </h3>
                      <p className="font-body-md text-body-md text-on-surface-variant">
                        Research, outline, and opening draft completed
                      </p>

                      {ws.is_big_task && ws.primary_friction_subtask_id && (
                        <div className="mt-4 p-3 bg-red-950/40 border border-red-500/30 rounded-lg">
                          <p className="text-xs text-red-400 font-mono mb-1 flex items-center gap-2">
                            ⚠️ PREDICTED STALL ZONE
                          </p>
                          <p className="text-sm text-slate-200 font-medium">
                            {ws.subtasks?.find((s) => s.id === ws.primary_friction_subtask_id)?.title}
                          </p>
                          <p className="text-xs text-slate-400 mt-1">
                            Iris pre-loaded content to break the friction.
                          </p>
                        </div>
                      )}

                      {ws.is_big_task && ws.subtasks && (
                        <div className="mt-3 grid grid-cols-2 gap-2">
                          {ws.subtasks.map((sub) => (
                            <div
                              key={sub.id}
                              className={`px-2 py-2 rounded text-xs border ${sub.historical_stall
                                ? 'bg-red-950/20 border-red-500/30 text-red-300'
                                : 'bg-white/5 border-white/10 text-slate-400'
                                }`}
                            >
                              <span className="block truncate font-medium">{sub.title}</span>
                              <span className="text-[10px] opacity-60">{sub.estimated_minutes}m</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="absolute inset-0 bg-white/0 group-hover:bg-white/5 transition-colors pointer-events-none rounded-xl"></div>
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* NEW: Upcoming 7 Days Schedule */}
          {upcomingEvents.length > 0 && (
            <div className="mb-10 w-full max-w-4xl relative">
              <div className="flex items-center gap-2 mb-6">
                <span className="material-symbols-outlined text-tertiary">calendar_month</span>
                <h2 className="text-xl font-semibold text-on-surface">Upcoming 7 Days</h2>
              </div>

              <div className="space-y-6 relative z-10 ml-2">
                {Object.entries(groupedEvents).map(([date, dayEvents]) => (
                  <div key={date} className="relative pl-6 border-l border-white/10">
                    <div className="absolute -left-[5px] top-1.5 w-2 h-2 rounded-full bg-tertiary shadow-[0_0_10px_rgba(0,221,221,0.8)]"></div>
                    <h3 className="text-xs font-bold text-tertiary mb-3 uppercase tracking-wider font-mono">{date}</h3>

                    <div className="space-y-2">
                      {dayEvents.map((event, idx) => (
                        <div key={`${event.id}-${idx}`} className="p-3 rounded-lg bg-surface-container-low/30 border border-white/5 hover:border-tertiary/30 transition-colors flex items-center justify-between group">
                          <span className="font-medium text-on-surface text-sm truncate pr-4 group-hover:text-tertiary transition-colors">{event.title}</span>
                          <span className="text-xs text-on-surface-variant whitespace-nowrap font-mono">
                            {new Date(event.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} - {new Date(event.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </section>
      </main>
    </div>
  );
}