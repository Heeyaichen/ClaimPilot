import ClaimUploadForm from "@/components/ClaimUploadForm";

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center py-12 px-4">
      <h1 className="text-2xl font-bold mb-8">ClaimPilot</h1>
      <div className="w-full max-w-lg">
        <ClaimUploadForm />
      </div>
    </div>
  );
}
