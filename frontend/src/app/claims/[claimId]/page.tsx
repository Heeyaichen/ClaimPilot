"use client";

import { useParams } from "next/navigation";
import ClaimStatusPage from "@/components/ClaimStatusPage";

export default function ClaimDetailPage() {
  const params = useParams();
  const claimId = params.claimId as string;
  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <ClaimStatusPage claimId={claimId} />
    </div>
  );
}
