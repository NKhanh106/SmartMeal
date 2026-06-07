import type { UpdateProposal, ProposalConfirmResult } from "@/types/update-proposal";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export async function confirmProposal(
  sessionId: string,
  proposalId: string,
  token: string
): Promise<ProposalConfirmResult> {
  const res = await fetch(
    `${API_BASE}/ai/chat/sessions/${sessionId}/proposals/${proposalId}/confirm`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    }
  );

  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || "Lưu dữ liệu thất bại");
  }

  return res.json();
}

export async function rejectProposal(
  sessionId: string,
  proposalId: string,
  token: string
): Promise<void> {
  await fetch(
    `${API_BASE}/ai/chat/sessions/${sessionId}/proposals/${proposalId}/reject`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}
