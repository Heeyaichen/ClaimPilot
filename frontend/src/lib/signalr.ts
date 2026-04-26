"use client";

import { useEffect, useRef, useCallback } from "react";
import {
  HubConnectionBuilder,
  HubConnection,
  LogLevel,
} from "@microsoft/signalr";

const SIGNALR_URL =
  process.env.NEXT_PUBLIC_SIGNALR_URL || "http://localhost:8000/claims";

interface UseSignalROptions {
  claimId: string;
  onEvent?: (event: Record<string, unknown>) => void;
}

export function useSignalR({ claimId, onEvent }: UseSignalROptions) {
  const connectionRef = useRef<HubConnection | null>(null);

  const start = useCallback(async () => {
    const conn = new HubConnectionBuilder()
      .withUrl(SIGNALR_URL)
      .withAutomaticReconnect()
      .configureLogging(LogLevel.Warning)
      .build();

    conn.on("pipelineEvent", (msg: string) => {
      try {
        const event = JSON.parse(msg);
        if (event.claimId === claimId && onEvent) {
          onEvent(event);
        }
      } catch {
        // ignore malformed messages
      }
    });

    connectionRef.current = conn;

    try {
      await conn.start();
    } catch {
      // SignalR not available in dev — poll instead
    }
  }, [claimId, onEvent]);

  const stop = useCallback(async () => {
    if (connectionRef.current) {
      await connectionRef.current.stop();
      connectionRef.current = null;
    }
  }, []);

  useEffect(() => {
    start();
    return () => {
      stop();
    };
  }, [start, stop]);

  return { start, stop };
}
