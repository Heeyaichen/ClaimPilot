import ClaimUploadForm from "@/components/ClaimUploadForm";

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">ClaimPilot</h1>
          <nav className="flex gap-4 text-sm">
            <a href="/" className="text-blue-600 font-medium">Submit</a>
            <a href="/adjuster/queue" className="text-gray-600 hover:text-gray-900">Adjuster Queue</a>
          </nav>
        </div>
      </header>
      <main className="max-w-lg mx-auto py-10 px-4">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-800">Submit a Claim</h2>
          <p className="text-sm text-gray-500 mt-1">
            Upload the claim form, damage photos, and optional voice recording.
          </p>
        </div>
        <ClaimUploadForm />
      </main>
    </div>
  );
}
