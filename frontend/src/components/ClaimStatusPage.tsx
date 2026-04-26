"use client";

import { useEffect, useState, useCallback } from "react";
import { getClaimStatus, ClaimStatusResponse } from "@/lib/api";
import { useSignalR } from "@/lib/signalr";
import PipelineTracker from "./PipelineTracker";
import DecisionViewer from "./decision-viewer";

export default function ClaimStatusPage({ claimId }: { claimId: string }) {
  const [data, setData] = useState<ClaimStatusResponse | null>(null);
  const [error, setError] = useState("");

  const fetchStatus = useCallback(async () => {
    try {
      const res = await getClaimStatus(claimId);
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load status");
    }
  }, [claimId]);

  const handleSignalREvent = useCallback(() => {
    fetchStatus();
  }, [fetchStatus]);

  useSignalR({ claimId, onEvent: handleSignalREvent });

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  if (error) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="bg-red-50 border border-red-200 text-red-700 p-6 rounded-lg text-center">
          <p className="font-medium">Error loading claim</p>
          <p className="text-sm mt-1">{error}</p>
          <button onClick={fetchStatus} className="mt-3 text-sm underline">Retry</button>
        </div>
      </div>
    );
  }

  if (!data) {
    return <div className="text-center p-12 text-gray-500">Loading claim...</div>;
  }

  const statusColor: Record<string, string> = {
    APPROVED: "text-emerald-600",
    REJECTED: "text-red-600",
    FAILED: "text-red-600",
    ESCALATED: "text-amber-600",
  };

  const results = data.partial_results;
  const decision = results.decision_result as Record<string, unknown> | undefined;
  const fraud = results.fraud_result as Record<string, unknown> | undefined;
  const extraction = results.extraction_result as Record<string, unknown> | undefined;
  const classification = results.classification_result as Record<string, unknown> | undefined;
  const docExtraction = results.doc_extraction as Record<string, unknown> | undefined;
  const imageAnalysis = results.image_analysis as Record<string, unknown> | undefined;
  const voiceTranscript = results.voice_transcript as Record<string, unknown> | undefined;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Claim {claimId}</h1>
          <p className="text-xs text-gray-500 mt-1">
            Submitted {data.submitted_at ? new Date(data.submitted_at).toLocaleString() : ""}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-sm font-semibold ${statusColor[data.status] || "text-blue-600"}`}>
            {data.status}
          </span>
          {(data.status === "APPROVED" || data.status === "ESCALATED" || data.status === "REJECTED") && (
            <a
              href={`/adjuster/${claimId}`}
              className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700"
            >
              Voice Session
            </a>
          )}
        </div>
      </div>

      {/* Pipeline Progress */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h2 className="text-sm font-semibold text-gray-500 mb-3">Pipeline Progress ({data.steps.filter(s => s.status === "COMPLETED").length}/{data.total_steps})</h2>
        <PipelineTracker steps={data.steps} />
      </div>

      {/* Classification */}
      {classification && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-sm font-semibold text-gray-500 mb-2">Classification</h2>
          <div className="flex items-center gap-4">
            <span className="text-sm font-medium text-gray-800">
              {(classification as Record<string, unknown>).claim_type as string || "N/A"}
            </span>
            <span className="text-xs text-gray-500">
              Confidence: {Math.round(((classification as Record<string, unknown>).confidence as number || 0) * 100)}%
            </span>
            {(classification as Record<string, unknown>).routing_rationale ? (
              <span className="text-xs text-gray-500">
                {String((classification as Record<string, unknown>).routing_rationale)}
              </span>
            ) : null}
          </div>
        </div>
      )}

      {/* Extracted Fields */}
      {(extraction || docExtraction) && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-sm font-semibold text-gray-500 mb-3">Extracted Fields</h2>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            {Object.entries((extraction || docExtraction) as Record<string, unknown>).map(([key, value]) => {
              if (value == null || typeof value === "object") return null;
              return (
                <div key={key} className="flex justify-between">
                  <span className="text-gray-500">{key.replace(/_/g, " ")}</span>
                  <span className="text-gray-800 font-medium">{String(value)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Image Analysis */}
      {imageAnalysis && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-sm font-semibold text-gray-500 mb-2">Damage Assessment</h2>
          <p className="text-sm text-gray-700">
            {(imageAnalysis as Record<string, unknown>).summary as string || JSON.stringify(imageAnalysis)}
          </p>
        </div>
      )}

      {/* Voice Transcript */}
      {voiceTranscript && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-sm font-semibold text-gray-500 mb-2">Voice Transcript</h2>
          <p className="text-sm text-gray-700 italic">
            &ldquo;{(voiceTranscript as Record<string, unknown>).original_text as string || "No transcript"}&rdquo;
          </p>
          {(voiceTranscript as Record<string, unknown>).detected_language ? (
            <p className="text-xs text-gray-500 mt-1">
              Language: {String((voiceTranscript as Record<string, unknown>).detected_language)}
            </p>
          ) : null}
        </div>
      )}

      {/* Fraud Score */}
      {fraud && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-sm font-semibold text-gray-500 mb-3">Fraud Screening</h2>
          <div className="flex items-center gap-4">
            <div className="text-2xl font-bold">
              <span className={
                (fraud as Record<string, unknown>).score as number >= 0.7 ? "text-red-600" :
                (fraud as Record<string, unknown>).score as number >= 0.4 ? "text-amber-600" : "text-emerald-600"
              }>
                {(fraud as Record<string, unknown>).score as number}
              </span>
            </div>
            <div>
              <p className="text-sm text-gray-600">
                Recommendation: <span className="font-medium">{(fraud as Record<string, unknown>).recommendation as string}</span>
              </p>
              {((fraud as Record<string, unknown>).flags as string[])?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {((fraud as Record<string, unknown>).flags as string[]).map((f: string, i: number) => (
                    <span key={i} className="text-xs bg-red-50 text-red-600 px-1.5 py-0.5 rounded">{f}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Decision */}
      {decision && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-sm font-semibold text-gray-500 mb-3">Adjudication Decision</h2>
          <DecisionViewer data={decision as unknown as Parameters<typeof DecisionViewer>[0]["data"]} />
        </div>
      )}
    </div>
  );
}
