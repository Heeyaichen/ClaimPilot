"use client";

import { StepState } from "@/lib/api";

const STEP_LABELS: Record<string, string> = {
  CLAIM_RECEIVED: "Claim Received",
  INGEST_DOCUMENT: "Document Ingestion",
  INGEST_IMAGES: "Image Ingestion",
  INGEST_VOICE: "Voice Transcription",
  CLASSIFY_STUB: "Classification",
  EXTRACT_VALIDATE_STUB: "Extraction & Validation",
  DECIDE_STUB: "Decision",
};

function StepIcon({ status }: { status: string }) {
  switch (status) {
    case "COMPLETED":
      return <span className="inline-block w-6 h-6 rounded-full bg-green-500 text-white text-center text-sm leading-6">✓</span>;
    case "RUNNING":
      return <span className="inline-block w-6 h-6 rounded-full bg-blue-500 text-white text-center text-sm leading-6 animate-pulse">●</span>;
    case "FAILED":
      return <span className="inline-block w-6 h-6 rounded-full bg-red-500 text-white text-center text-sm leading-6">✗</span>;
    case "SKIPPED":
      return <span className="inline-block w-6 h-6 rounded-full bg-gray-400 text-white text-center text-sm leading-6">—</span>;
    default:
      return <span className="inline-block w-6 h-6 rounded-full bg-gray-200 text-gray-500 text-center text-sm leading-6">○</span>;
  }
}

export default function PipelineTracker({ steps }: { steps: StepState[] }) {
  return (
    <div className="space-y-3">
      {steps.map((s) => (
        <div key={s.step} className="flex items-center gap-3">
          <StepIcon status={s.status} />
          <span className="text-sm font-medium text-gray-700">
            {STEP_LABELS[s.step] || s.step}
          </span>
          {s.status === "COMPLETED" && s.started_at && s.completed_at && (
            <span className="text-xs text-gray-400 ml-auto">
              {Math.round(new Date(s.completed_at).getTime() - new Date(s.started_at).getTime())}ms
            </span>
          )}
          {s.error && <span className="text-xs text-red-500 ml-auto">{s.error}</span>}
        </div>
      ))}
    </div>
  );
}
