"use client";

import { useState, useRef } from "react";
import { submitClaim } from "@/lib/api";

export default function ClaimUploadForm() {
  const [claimantName, setClaimantName] = useState("");
  const [policyNumber, setPolicyNumber] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ claim_id: string; status_url: string } | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    const formData = new FormData(e.currentTarget);
    try {
      const res = await submitClaim(formData);
      setResult({ claim_id: res.claim_id, status_url: res.status_url });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setLoading(false);
    }
  };

  if (result) {
    return (
      <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
        <p className="text-green-800 font-semibold mb-2">Claim Submitted</p>
        <p className="text-sm text-gray-600 mb-4">Claim ID: {result.claim_id}</p>
        <a
          href={`/claims/${result.claim_id}`}
          className="inline-block px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
        >
          Track Status
        </a>
      </div>
    );
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Claimant Name</label>
          <input
            name="claimant_name"
            value={claimantName}
            onChange={(e) => setClaimantName(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
            placeholder="John Doe"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Policy Number</label>
          <input
            name="policy_number"
            value={policyNumber}
            onChange={(e) => setPolicyNumber(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
            placeholder="POL-12345"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Claim Form (PDF)</label>
        <input name="form" type="file" accept=".pdf,.doc,.docx" className="block w-full text-sm text-gray-500" />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Damage Photos</label>
        <input name="images" type="file" accept="image/*" multiple className="block w-full text-sm text-gray-500" />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Voice Recording</label>
        <input name="audio" type="file" accept="audio/*" className="block w-full text-sm text-gray-500" />
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <button
        type="submit"
        disabled={loading}
        className="w-full py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
      >
        {loading ? "Submitting..." : "Submit Claim"}
      </button>
    </form>
  );
}
