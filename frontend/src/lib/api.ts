const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ClaimSubmissionResponse {
  claim_id: string;
  status: string;
  status_url: string;
}

export interface StepState {
  step: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  output: Record<string, unknown>;
  error: string | null;
}

export interface ClaimStatusResponse {
  claim_id: string;
  status: string;
  current_step: string;
  total_steps: number;
  steps: StepState[];
  submitted_at: string;
  updated_at: string;
  partial_results: Record<string, unknown>;
}

export async function submitClaim(formData: FormData): Promise<ClaimSubmissionResponse> {
  const res = await fetch(`${API_BASE}/api/v1/claims`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`Submission failed: ${res.statusText}`);
  return res.json();
}

export async function getClaimStatus(claimId: string): Promise<ClaimStatusResponse> {
  const res = await fetch(`${API_BASE}/api/v1/claims/${claimId}/status`);
  if (!res.ok) throw new Error(`Status fetch failed: ${res.statusText}`);
  return res.json();
}
