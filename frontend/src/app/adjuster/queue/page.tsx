"use client";

import { useEffect, useState } from "react";
import { getAdjusterQueue, type QueueClaim } from "@/lib/api";

function FraudBadge({ score }: { score: number | undefined }) {
  if (score == null) return <span className="text-xs text-gray-400">N/A</span>;
  const color =
    score >= 0.7 ? "bg-red-100 text-red-700" : score >= 0.4 ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700";
  return <span className={`text-xs px-2 py-0.5 rounded font-medium ${color}`}>{score.toFixed(2)}</span>;
}

function DecisionBadge({ decision }: { decision: string | null }) {
  if (!decision) return <span className="text-xs text-gray-400">Pending</span>;
  const color =
    decision === "APPROVE" ? "text-emerald-700" : decision === "REJECT" ? "text-red-700" : "text-amber-700";
  return <span className={`text-xs font-medium ${color}`}>{decision}</span>;
}

export default function AdjusterQueuePage() {
  const [claims, setClaims] = useState<QueueClaim[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getAdjusterQueue("ESCALATED")
      .then((res) => setClaims(res.claims))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Adjuster Queue</h1>
            <p className="text-sm text-gray-500">Escalated claims requiring review</p>
          </div>
          <nav className="flex gap-4 text-sm">
            <a href="/" className="text-gray-600 hover:text-gray-900">Submit Claim</a>
          </nav>
        </div>
      </header>

      <main className="max-w-5xl mx-auto py-6 px-4">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg text-sm mb-4">{error}</div>
        )}

        {loading ? (
          <div className="text-center py-12 text-gray-500">Loading queue...</div>
        ) : claims.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500">No escalated claims in the queue.</p>
            <p className="text-sm text-gray-400 mt-1">Submit a claim to see it here after processing.</p>
          </div>
        ) : (
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b">
                  <th className="text-left px-4 py-3 text-gray-600 font-medium">Claim</th>
                  <th className="text-left px-4 py-3 text-gray-600 font-medium">Claimant</th>
                  <th className="text-left px-4 py-3 text-gray-600 font-medium">Fraud</th>
                  <th className="text-left px-4 py-3 text-gray-600 font-medium">Decision</th>
                  <th className="text-left px-4 py-3 text-gray-600 font-medium">Updated</th>
                  <th className="text-right px-4 py-3 text-gray-600 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {claims.map((claim) => (
                  <tr key={claim.claim_id} className="border-b last:border-b-0 hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-gray-800">{claim.claim_id}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{claim.claimant_name || "—"}</td>
                    <td className="px-4 py-3">
                      <FraudBadge score={claim.fraud_result?.score} />
                    </td>
                    <td className="px-4 py-3">
                      <DecisionBadge decision={claim.decision_result?.decision ?? null} />
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {claim.updated_at ? new Date(claim.updated_at).toLocaleDateString() : "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <a
                        href={`/claims/${claim.claim_id}`}
                        className="text-blue-600 hover:text-blue-800 text-xs mr-3"
                      >
                        Details
                      </a>
                      <a
                        href={`/adjuster/${claim.claim_id}`}
                        className="text-blue-600 hover:text-blue-800 text-xs"
                      >
                        Voice
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
