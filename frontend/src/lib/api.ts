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

// Adjuster voice session types

export interface AdjusterSessionResponse {
  session_id: string;
  claim_id: string;
  ws_url: string;
  token: string;
  status: string;
}

export interface ClaimLookupResult {
  claim_id: string;
  found: boolean;
  summary: string;
  fraud_score: number | null;
  decision: string | null;
  approved_amount: number | null;
  damage_assessment: string | null;
  reasoning_summary: string | null;
  error: string | null;
}

export async function getAdjusterSessionUrl(
  claimId: string,
  adjusterId = "default-adjuster",
): Promise<AdjusterSessionResponse> {
  const params = new URLSearchParams({ claim_id: claimId, adjuster_id: adjusterId });
  const res = await fetch(`${API_BASE}/api/v1/adjuster/session-url?${params}`);
  if (!res.ok) throw new Error(`Session URL fetch failed: ${res.statusText}`);
  return res.json();
}

export async function getAdjusterClaimContext(claimId: string): Promise<ClaimLookupResult> {
  const res = await fetch(`${API_BASE}/api/v1/adjuster/claim/${claimId}`);
  if (!res.ok) throw new Error(`Claim context fetch failed: ${res.statusText}`);
  return res.json();
}

export function getVoiceWebSocketUrl(claimId: string): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/api/v1/adjuster/voice/${claimId}`;
}

// Adjuster queue types

export interface QueueClaim {
  claim_id: string;
  status: string;
  claimant_name: string;
  policy_number: string;
  submitted_at: string;
  updated_at: string;
  fraud_result: { score: number; flags: string[]; recommendation: string } | null;
  decision_result: { decision: string; confidence: number; escalation_reason?: string } | null;
}

export interface AdjusterQueueResponse {
  claims: QueueClaim[];
  total: number;
  page: number;
  page_size: number;
}

export async function getAdjusterQueue(
  status = "ESCALATED",
  page = 1,
  pageSize = 20,
): Promise<AdjusterQueueResponse> {
  const params = new URLSearchParams({
    status,
    page: String(page),
    page_size: String(pageSize),
  });
  const res = await fetch(`${API_BASE}/api/v1/adjuster/queue?${params}`);
  if (!res.ok) throw new Error(`Queue fetch failed: ${res.statusText}`);
  return res.json();
}
