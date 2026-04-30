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
type SessionMode = "unknown" | "text_fallback" | "voice_live";

export default function VoiceAdjuster({ claimId }: { claimId: string }) {
  const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected");
  const [sessionMode, setSessionMode] = useState<SessionMode>("unknown");
  const [audioEnabled, setAudioEnabled] = useState(false);
  const [claimContext, setClaimContext] = useState<ClaimLookupResult | null>(null);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [textInput, setTextInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

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

  const addTranscript = useCallback((role: TranscriptEntry["role"], text: string) => {
    setTranscript((prev) => [...prev, { role, text, timestamp: new Date() }]);
  }, []);

  // Connect to WebSocket
  const connect = useCallback(async () => {
    setError(null);
    setConnectionState("connecting");
    setSessionMode("unknown");
    setAudioEnabled(false);

    const wsUrl = getVoiceWebSocketUrl(claimId);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionState("connected");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "session.config") {
          const mode = data.mode === "voice_live" ? "voice_live" : "text_fallback";
          setSessionMode(mode);
          setAudioEnabled(data.audio_enabled === true);

          if (data.warning) {
            addTranscript("system", data.warning);
          }

          const modeLabel = mode === "voice_live" ? "Voice Live" : "Text Mode";
          addTranscript("system", `Session connected (${modeLabel})`);
          return;
        }

        if (data.type === "warning") {
          addTranscript("system", data.message || "Warning");
          return;
        }

        if (data.type === "error") {
          setError(data.message || "Session error");
          return;
        }

        // Handle transcript / response events
        if (data.type === "transcript" || data.role) {
          const role = data.role === "user" ? "user" : "assistant";
          const text = data.text || data.transcript || JSON.stringify(data);
          addTranscript(role, text);
          return;
        }

        if (data.type === "audio.output" || data.audio) {
          return;
        }

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
    };

    ws.onclose = (event) => {
      setConnectionState("disconnected");
      setSessionMode("unknown");
      setAudioEnabled(false);
      if (event.code !== 1000) {
        addTranscript("system", `Disconnected (code: ${event.code})`);
      }
    };
  }, [claimId, addTranscript]);

  const disconnect = useCallback(() => {
    wsRef.current?.close(1000, "User disconnected");
    wsRef.current = null;
    setConnectionState("disconnected");
    setSessionMode("unknown");
    setAudioEnabled(false);
    addTranscript("system", "Session ended");
  }, [addTranscript]);

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
    };
  }, []);

  const isConnected = connectionState === "connected";
  const isTextMode = sessionMode === "text_fallback" || sessionMode === "unknown";

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-4">
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

      {/* Connection Controls & Mode Badge */}
      <div className="flex items-center gap-4 flex-wrap">
        {connectionState === "disconnected" || connectionState === "error" ? (
          <button
            onClick={connect}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium"
          >
            Connect Session
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

        {/* Connection state indicator */}
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

        {/* Mode badge */}
        {isConnected && (
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${
              sessionMode === "voice_live"
                ? "bg-green-900 text-green-300"
                : "bg-amber-900 text-amber-300"
            }`}
          >
            {sessionMode === "voice_live" ? "Voice Live" : "Text Mode"}
          </span>
        )}

        {/* Microphone control — only active in voice_live mode */}
        {isConnected && (
          <button
            disabled={!audioEnabled}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
              audioEnabled
                ? "bg-green-700 hover:bg-green-600 text-white"
                : "bg-slate-700 text-slate-500 cursor-not-allowed"
            }`}
            title={
              audioEnabled
                ? "Microphone active"
                : "Voice Live not configured — microphone unavailable"
            }
          >
            {audioEnabled ? "Mic On" : "Mic Off"}
          </button>
        )}

        {/* Microphone unavailable notice */}
        {isConnected && isTextMode && (
          <span className="text-amber-400 text-xs">
            Microphone unavailable — Voice Live not configured. Use text input below.
          </span>
        )}
      </div>

      {/* Transcript Panel */}
      <div className="bg-slate-900 rounded-lg border border-slate-700 h-96 overflow-y-auto p-4 space-y-3">
        {transcript.length === 0 ? (
          <p className="text-slate-500 text-center mt-20">
            Connect to start a session. Type questions about the claim below.
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

      {/* Text Input — always enabled when connected */}
      <div className="flex gap-3">
        <input
          type="text"
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendTextMessage()}
          placeholder={
            isConnected
              ? 'Type a question, e.g. "What is the fraud score?"'
              : "Connect to start asking questions"
          }
          disabled={!isConnected}
          className="flex-1 bg-slate-800 text-white px-4 py-2 rounded-lg border border-slate-600 focus:border-blue-500 focus:outline-none disabled:opacity-50"
        />
        <button
          onClick={sendTextMessage}
          disabled={!isConnected || !textInput.trim()}
          className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
