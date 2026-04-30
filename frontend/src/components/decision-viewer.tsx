"use client";

interface ReasoningStep {
  step: string;
  conclusion: string;
  evidence_source: string;
  evidence_value: string | number | boolean;
}

interface DecisionData {
  decision: string;
  confidence: number;
  approved_amount: number | null;
  rejection_reason: string | null;
  escalation_reason: string | null;
  reasoning_chain: ReasoningStep[];
}

const DECISION_STYLES: Record<string, { bg: string; border: string; text: string; label: string }> = {
  APPROVE: { bg: "bg-emerald-50", border: "border-emerald-300", text: "text-emerald-800", label: "Approved" },
  REJECT: { bg: "bg-red-50", border: "border-red-300", text: "text-red-800", label: "Rejected" },
  ESCALATE: { bg: "bg-amber-50", border: "border-amber-300", text: "text-amber-800", label: "Escalated" },
};

export default function DecisionViewer({ data }: { data: DecisionData }) {
  const style = DECISION_STYLES[data.decision] || DECISION_STYLES.ESCALATE;
  const confidencePercent = Math.round(data.confidence * 100);

  return (
    <div className="space-y-4">
      {/* Decision Badge */}
      <div className={`${style.bg} ${style.border} border rounded-lg p-4`}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className={`text-lg font-bold ${style.text}`}>{style.label}</h3>
            {data.approved_amount != null && (
              <p className="text-sm text-gray-600 mt-1">
                Approved: ${data.approved_amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
              </p>
            )}
            {data.rejection_reason && (
              <p className="text-sm text-gray-600 mt-1">Reason: {data.rejection_reason}</p>
            )}
            {data.escalation_reason && (
              <p className="text-sm text-gray-600 mt-1">Reason: {data.escalation_reason}</p>
            )}
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-gray-700">{confidencePercent}%</div>
            <div className="text-xs text-gray-500">confidence</div>
          </div>
        </div>
        {/* Confidence bar */}
        <div className="mt-3 h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${
              confidencePercent >= 80 ? "bg-emerald-500" : confidencePercent >= 60 ? "bg-amber-500" : "bg-red-500"
            }`}
            style={{ width: `${confidencePercent}%` }}
          />
        </div>
      </div>

      {/* Reasoning Chain */}
      {data.reasoning_chain.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-3">Reasoning Chain</h4>
          <div className="space-y-3">
            {data.reasoning_chain.map((step, i) => (
              <div key={i} className="bg-white border border-gray-200 rounded-lg p-3">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center mt-0.5">
                    {i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800">{step.step}</p>
                    <p className="text-sm text-gray-600 mt-0.5">{step.conclusion}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <span className="inline-flex items-center text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                        Source: {step.evidence_source}
                      </span>
                      <span className="inline-flex items-center text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                        Value: {String(step.evidence_value)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.reasoning_chain.length === 0 && (
        <p className="text-sm text-gray-500 italic">No reasoning chain available yet.</p>
      )}
    </div>
  );
}
