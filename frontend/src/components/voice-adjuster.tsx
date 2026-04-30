"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getAdjusterClaimContext,
  getVoiceWebSocketUrl,
  type ClaimLookupResult,
} from "@/lib/api";

interface TranscriptEntry {
  role: "user" | "assistant" | "system";
  text: string;
  timestamp: Date;
}

type ConnectionState = "disconnected" | "connecting" | "connected" | "error";

export default function VoiceAdjuster({ claimId }: { claimId: string }) {
  const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected");
  const [claimContext, setClaimContext] = useState<ClaimLookupResult | null>(null);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [textInput, setTextInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [micPermission, setMicPermission] = useState<PermissionState | "unknown">("unknown");

  const wsRef = useRef<WebSocket | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);

  // Load claim context on mount
  useEffect(() => {
    getAdjusterClaimContext(claimId)
      .then(setClaimContext)
      .catch((err) => setError(`Failed to load claim: ${err.message}`));
  }, [claimId]);

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  // Check microphone permission
  const checkMicPermission = useCallback(async (): Promise<boolean> => {
    try {
      const result = await navigator.permissions.query({ name: "microphone" as PermissionName });
      setMicPermission(result.state);
      if (result.state === "denied") {
        setError("Microphone permission denied. Please allow microphone access.");
        return false;
      }
      return true;
    } catch {
      // permissions.query may not support microphone in all browsers
      setMicPermission("unknown");
      return true;
    }
  }, []);

  const addTranscript = useCallback((role: TranscriptEntry["role"], text: string) => {
    setTranscript((prev) => [...prev, { role, text, timestamp: new Date() }]);
  }, []);

  // Start microphone capture and send audio to WebSocket
  const startMicrophone = useCallback(async () => {
    const permitted = await checkMicPermission();
    if (!permitted) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 24000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      mediaStreamRef.current = stream;

      const audioCtx = new AudioContext({ sampleRate: 24000 });
      audioContextRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) return;

        const inputData = e.inputBuffer.getChannelData(0);
        // Convert float32 to int16 PCM
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        ws.send(pcm16.buffer);
      };

      source.connect(processor);
      processor.connect(audioCtx.destination);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Microphone access failed";
      setError(`Microphone error: ${msg}`);
      setMicPermission("denied");
    }
  }, [checkMicPermission]);

  const stopMicrophone = useCallback(() => {
    processorRef.current?.disconnect();
    audioContextRef.current?.close();
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    processorRef.current = null;
    audioContextRef.current = null;
    mediaStreamRef.current = null;
  }, []);

  // Connect to WebSocket
  const connect = useCallback(async () => {
    setError(null);
    setConnectionState("connecting");

    const wsUrl = getVoiceWebSocketUrl(claimId);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionState("connected");
      addTranscript("system", "Connected to voice session");
      startMicrophone();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "session.config") {
          addTranscript("system", `Session configured: ${data.session_id}`);
          return;
        }

        if (data.type === "status") {
          addTranscript("system", data.message || `Status: ${data.status}`);
          return;
        }

        if (data.type === "error") {
          setError(data.message || "Voice Live error");
          return;
        }

        // Handle transcript events
        if (data.type === "transcript" || data.role) {
          const role = data.role === "user" ? "user" : "assistant";
          const text = data.text || data.transcript || JSON.stringify(data);
          addTranscript(role, text);
          return;
        }

        // Handle audio output (would need audio playback)
        if (data.type === "audio.output" || data.audio) {
          // Audio playback would go here for Phase 4
          return;
        }

        // Tool results — show in transcript
        if (data.type === "tool_result") {
          addTranscript("system", `Tool result: ${JSON.stringify(data.output).slice(0, 200)}`);
        }
      } catch {
        // Non-JSON message (binary audio data)
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection error");
      setConnectionState("error");
      stopMicrophone();
    };

    ws.onclose = (event) => {
      setConnectionState("disconnected");
      stopMicrophone();
      if (event.code !== 1000) {
        addTranscript("system", `Disconnected (code: ${event.code})`);
      }
    };
  }, [claimId, addTranscript, startMicrophone, stopMicrophone]);

  const disconnect = useCallback(() => {
    wsRef.current?.close(1000, "User disconnected");
    wsRef.current = null;
    setConnectionState("disconnected");
    stopMicrophone();
    addTranscript("system", "Session ended");
  }, [stopMicrophone, addTranscript]);

  const sendTextMessage = useCallback(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN || !textInput.trim()) return;

    ws.send(
      JSON.stringify({
        type: "text.input",
        text: textInput.trim(),
      }),
    );
    addTranscript("user", textInput.trim());
    setTextInput("");
  }, [textInput, addTranscript]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close(1000);
      stopMicrophone();
    };
  }, [stopMicrophone]);

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Claim Context Banner */}
      {claimContext && (
        <div className="bg-slate-800 text-white p-4 rounded-lg">
          <h3 className="text-sm font-medium text-slate-400">Claim Context</h3>
          <p className="mt-1">{claimContext.summary}</p>
          {claimContext.fraud_score !== null && (
            <p className="text-sm text-slate-400 mt-1">
              Fraud Score: {claimContext.fraud_score}
            </p>
          )}
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-red-900/50 text-red-200 p-3 rounded-lg text-sm">{error}</div>
      )}

      {/* Connection Controls */}
      <div className="flex items-center gap-4">
        {connectionState === "disconnected" || connectionState === "error" ? (
          <button
            onClick={connect}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium"
          >
            Connect Voice Session
          </button>
        ) : (
          <button
            onClick={disconnect}
            disabled={connectionState === "connecting"}
            className="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-lg font-medium disabled:opacity-50"
          >
            {connectionState === "connecting" ? "Connecting..." : "Disconnect"}
          </button>
        )}

        <div className="flex items-center gap-2 text-sm">
          <div
            className={`w-3 h-3 rounded-full ${
              connectionState === "connected"
                ? "bg-green-500"
                : connectionState === "connecting"
                  ? "bg-yellow-500 animate-pulse"
                  : connectionState === "error"
                    ? "bg-red-500"
                    : "bg-slate-500"
            }`}
          />
          <span className="text-slate-400 capitalize">{connectionState}</span>
        </div>

        {micPermission === "denied" && (
          <span className="text-red-400 text-sm">Microphone access denied</span>
        )}
      </div>

      {/* Transcript Panel */}
      <div className="bg-slate-900 rounded-lg border border-slate-700 h-96 overflow-y-auto p-4 space-y-3">
        {transcript.length === 0 ? (
          <p className="text-slate-500 text-center mt-20">
            Connect to start the voice session. Speak or type questions about the claim.
          </p>
        ) : (
          transcript.map((entry, i) => (
            <div
              key={i}
              className={`flex ${
                entry.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[80%] px-4 py-2 rounded-lg text-sm ${
                  entry.role === "user"
                    ? "bg-blue-600 text-white"
                    : entry.role === "system"
                      ? "bg-slate-700 text-slate-300"
                      : "bg-slate-800 text-slate-200"
                }`}
              >
                <p>{entry.text}</p>
                <p className="text-xs text-slate-500 mt-1">
                  {entry.timestamp.toLocaleTimeString()}
                </p>
              </div>
            </div>
          ))
        )}
        <div ref={transcriptEndRef} />
      </div>

      {/* Text Fallback Input */}
      <div className="flex gap-3">
        <input
          type="text"
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendTextMessage()}
          placeholder='Type a question, e.g. "What is the fraud score?"'
          disabled={connectionState !== "connected"}
          className="flex-1 bg-slate-800 text-white px-4 py-2 rounded-lg border border-slate-600 focus:border-blue-500 focus:outline-none disabled:opacity-50"
        />
        <button
          onClick={sendTextMessage}
          disabled={connectionState !== "connected" || !textInput.trim()}
          className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
