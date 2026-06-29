const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function getBriefing(userId: string) {
  const res = await fetch(`${API_BASE}/api/v1/briefing?user_id=${encodeURIComponent(userId)}`);
  if (!res.ok) throw new Error("Failed to fetch briefing");
  return res.json();
}

export async function approveProposal(proposalId: string, userId: string) {
  const res = await fetch(`${API_BASE}/api/v1/stage2/proposals/${proposalId}/approve?user_id=${encodeURIComponent(userId)}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to approve proposal");
  return res.json();
}

export async function rejectProposal(proposalId: string, userId: string) {
  const res = await fetch(`${API_BASE}/api/v1/stage2/proposals/${proposalId}/reject?user_id=${encodeURIComponent(userId)}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to reject proposal");
  return res.json();
}

export async function createWarmStart(emailId: string, userId: string, taskType: string = "writing") {
  const res = await fetch(`${API_BASE}/api/v1/stage3/warm-start?email_id=${encodeURIComponent(emailId)}&task_type=${encodeURIComponent(taskType)}&user_id=${encodeURIComponent(userId)}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to create warm start");
  return res.json();
}

export async function sendChatMessage(message: string, history: { role: string; content: string }[], userId: string) {
  const res = await fetch(`${API_BASE}/api/v1/assistant/chat?user_id=${encodeURIComponent(userId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!res.ok) throw new Error("Failed to send chat message");
  return res.json();
}

export async function getChangelog(userId: string) {
  const res = await fetch(`${API_BASE}/api/v1/assistant/changelog?user_id=${encodeURIComponent(userId)}`);
  if (!res.ok) throw new Error("Failed to fetch changelog");
  return res.json();
}