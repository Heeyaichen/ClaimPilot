"use client";

import { use } from "react";
import VoiceAdjuster from "@/components/voice-adjuster";

export default function AdjusterPage({
  params,
}: {
  params: Promise<{ claimId: string }>;
}) {
  const { claimId } = use(params);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 px-6 py-4">
        <h1 className="text-xl font-bold">ClaimPilot Adjuster Copilot</h1>
        <p className="text-sm text-slate-400">Claim: {claimId}</p>
      </header>
      <VoiceAdjuster claimId={claimId} />
    </main>
  );
}
