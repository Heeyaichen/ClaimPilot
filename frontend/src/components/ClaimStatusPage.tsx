"use client";

import { useEffect, useState, useCallback } from "react";
import { getClaimStatus, ClaimStatusResponse } from "@/lib/api";
import { useSignalR } from "@/lib/signalr";
import PipelineTracker from "./PipelineTracker";

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
    return <div className="text-red-600 text-center p-8">{error}</div>;
  }

  if (!data) {
    return <div className="text-center p-8 text-gray-500">Loading...</div>;
  }

  const statusColor: Record<string, string> = {
    APPROVED: "text-green-600",
    REJECTED: "text-red-600",
    FAILED: "text-red-600",
    ESCALATED: "text-yellow-600",
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-xl font-bold">Claim {claimId}</h1>
        <span className={`text-sm font-semibold ${statusColor[data.status] || "text-blue-600"}`}>
          {data.status}
        </span>
      </div>

      <div className="bg-white rounded-lg border p-4">
        <h2 className="text-sm font-semibold text-gray-500 mb-3">Pipeline Progress</h2>
        <PipelineTracker steps={data.steps} />
      </div>

      {Object.keys(data.partial_results).length > 0 && (
        <div className="bg-white rounded-lg border p-4">
          <h2 className="text-sm font-semibold text-gray-500 mb-3">Results</h2>
          <pre className="text-xs text-gray-700 overflow-auto max-h-64">
            {JSON.stringify(data.partial_results, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
