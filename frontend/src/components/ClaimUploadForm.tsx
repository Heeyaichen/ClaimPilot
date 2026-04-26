"use client";

import { useState } from "react";
import { submitClaim } from "@/lib/api";

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB
const MAX_IMAGE_COUNT = 10;
const ALLOWED_FORM_TYPES = ["application/pdf"];
const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const ALLOWED_AUDIO_TYPES = ["audio/wav", "audio/mpeg", "audio/mp4", "audio/webm"];

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ClaimUploadForm() {
  const [claimantName, setClaimantName] = useState("");
  const [policyNumber, setPolicyNumber] = useState("");
  const [formFile, setFormFile] = useState<File | null>(null);
  const [imageFiles, setImageFiles] = useState<File[]>([]);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ claim_id: string; status_url: string } | null>(null);

  const validateFiles = (): string | null => {
    if (formFile) {
      if (!ALLOWED_FORM_TYPES.includes(formFile.type) && !formFile.name.endsWith(".pdf")) {
        return `Form must be a PDF (got ${formFile.type || formFile.name.split(".").pop()})`;
      }
      if (formFile.size > MAX_FILE_SIZE) {
        return `Form file too large (${formatSize(formFile.size)}, max ${formatSize(MAX_FILE_SIZE)})`;
      }
    }
    for (const img of imageFiles) {
      if (!ALLOWED_IMAGE_TYPES.includes(img.type)) {
        return `Image ${img.name} is not a supported format (use JPEG, PNG, or WebP)`;
      }
      if (img.size > MAX_FILE_SIZE) {
        return `Image ${img.name} too large (${formatSize(img.size)})`;
      }
    }
    if (imageFiles.length > MAX_IMAGE_COUNT) {
      return `Too many images (${imageFiles.length}, max ${MAX_IMAGE_COUNT})`;
    }
    if (audioFile) {
      if (!ALLOWED_AUDIO_TYPES.includes(audioFile.type)) {
        return `Audio must be WAV, MP3, MP4, or WebM`;
      }
      if (audioFile.size > MAX_FILE_SIZE) {
        return `Audio file too large (${formatSize(audioFile.size)})`;
      }
    }
    return null;
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError("");

    const validationError = validateFiles();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    setResult(null);

    const formData = new FormData();
    formData.append("claimant_name", claimantName);
    formData.append("policy_number", policyNumber);
    if (formFile) formData.append("form", formFile);
    imageFiles.forEach((img) => formData.append("images", img));
    if (audioFile) formData.append("audio", audioFile);

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
      <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-6 text-center">
        <p className="text-emerald-800 font-semibold text-lg mb-2">Claim Submitted</p>
        <p className="text-sm text-gray-600 mb-1">Claim ID: {result.claim_id}</p>
        <p className="text-xs text-gray-500 mb-4">Processing started. Track the pipeline below.</p>
        <a
          href={`/claims/${result.claim_id}`}
          className="inline-block px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium transition-colors"
        >
          Track Claim Status
        </a>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Claimant Info */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Claimant Name</label>
          <input
            name="claimant_name"
            value={claimantName}
            onChange={(e) => setClaimantName(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="John Doe"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Policy Number</label>
          <input
            name="policy_number"
            value={policyNumber}
            onChange={(e) => setPolicyNumber(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="POL-12345"
          />
        </div>
      </div>

      {/* Upload Zones */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Claim Form (PDF)</label>
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-blue-400 transition-colors">
          <input
            name="form"
            type="file"
            accept=".pdf"
            onChange={(e) => setFormFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          />
          {formFile && (
            <p className="text-xs text-gray-500 mt-2">{formFile.name} ({formatSize(formFile.size)})</p>
          )}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Damage Photos (up to {MAX_IMAGE_COUNT})
        </label>
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-blue-400 transition-colors">
          <input
            name="images"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            onChange={(e) => setImageFiles(Array.from(e.target.files ?? []))}
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          />
          {imageFiles.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {imageFiles.map((f, i) => (
                <span key={i} className="text-xs bg-gray-100 px-2 py-1 rounded">
                  {f.name} ({formatSize(f.size)})
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Voice Recording (optional)</label>
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-blue-400 transition-colors">
          <input
            name="audio"
            type="file"
            accept="audio/wav,audio/mpeg,audio/mp4,audio/webm"
            onChange={(e) => setAudioFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          />
          {audioFile && (
            <p className="text-xs text-gray-500 mt-2">{audioFile.name} ({formatSize(audioFile.size)})</p>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium transition-colors"
      >
        {loading ? "Submitting..." : "Submit Claim"}
      </button>
    </form>
  );
}
