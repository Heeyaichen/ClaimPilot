"use client";

import { use } from "react";
import ClaimStatusPage from "@/components/ClaimStatusPage";

export default function ClaimDetailPage({
  params,
}: {
  params: Promise<{ claimId: string }>;
}) {
  const { claimId } = use(params);
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-4">
          <a href="/" className="text-sm text-gray-500 hover:text-gray-800">Back</a>
          <span className="text-sm text-gray-400">|</span>
          <a href={`/adjuster/${claimId}`} className="text-sm text-blue-600 hover:text-blue-800">Voice Session</a>
        </div>
      </header>
      <main className="py-8 px-4">
        <ClaimStatusPage claimId={claimId} />
      </main>
    </div>
  );
}
