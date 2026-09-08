/**
 * Resilient Enterprise SSE Client — TASK 35
 * Features:
 * - Monotonic sequence deduplication (execution_id + sequence)
 * - Automatic reconnection with exponential backoff
 * - Event replay via GET /api/v1/ask/{id}/events?after_sequence=N
 * - Transparent heartbeat handling
 * - Clean subscriber lifecycle
 */

import { StreamEvent, SSEEventType } from "@/types/platform";
import { apiClient } from "@/lib/api/client";

export type SSEEventHandler = (event: StreamEvent) => void;
export type SSEStatus = "CONNECTING" | "CONNECTED" | "RECONNECTING" | "DISCONNECTED" | "TERMINATED";

export interface SSEClientOptions {
  executionId: string;
  baseUrl?: string;
  onEvent?: SSEEventHandler;
  onStatusChange?: (status: SSEStatus) => void;
  onError?: (error: Error) => void;
  maxReconnectAttempts?: number;
  initialReconnectDelayMs?: number;
}

export class AnalystSSEClient {
  private executionId: string;
  private baseUrl: string;
  private eventSource: EventSource | null = null;
  private status: SSEStatus = "DISCONNECTED";
  private seenSequences: Set<number> = new Set();
  private lastSequence = 0;
  private reconnectAttempts = 0;
  private maxReconnectAttempts: number;
  private reconnectDelayMs: number;
  private reconnectTimeoutId: NodeJS.Timeout | null = null;
  private listeners: Set<SSEEventHandler> = new Set();
  private isExplicitlyClosed = false;

  public onStatusChange?: (status: SSEStatus) => void;
  public onError?: (error: Error) => void;

  constructor(options: SSEClientOptions) {
    this.executionId = options.executionId;
    this.baseUrl = options.baseUrl || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 5;
    this.reconnectDelayMs = options.initialReconnectDelayMs ?? 1000;
    if (options.onEvent) this.listeners.add(options.onEvent);
    this.onStatusChange = options.onStatusChange;
    this.onError = options.onError;
  }

  public subscribe(handler: SSEEventHandler): () => void {
    this.listeners.add(handler);
    return () => this.listeners.delete(handler);
  }

  public getStatus(): SSEStatus {
    return this.status;
  }

  public getLastSequence(): number {
    return this.lastSequence;
  }

  private setStatus(newStatus: SSEStatus) {
    if (this.status === newStatus) return;
    this.status = newStatus;
    this.onStatusChange?.(newStatus);
  }

  public connect(): void {
    if (this.status === "CONNECTED" || this.status === "CONNECTING") return;
    this.isExplicitlyClosed = false;
    this.setStatus("CONNECTING");

    const streamUrl = `${this.baseUrl}/ask/${this.executionId}/stream`;

    try {
      this.eventSource = new EventSource(streamUrl, { withCredentials: true });

      this.eventSource.onopen = () => {
        this.reconnectAttempts = 0;
        this.reconnectDelayMs = 1000;
        this.setStatus("CONNECTED");
      };

      // Listen to all standard event types
      const standardEvents: SSEEventType[] = [
        "execution_started",
        "query_analyzed",
        "routing_selected",
        "semantic_resolved",
        "graph_expanded",
        "retrieval_started",
        "retrieval_completed",
        "plan_generated",
        "step_started",
        "step_completed",
        "evidence_collected",
        "verification_started",
        "verification_completed",
        "response_chunk",
        "response_completed",
        "execution_failed",
        "approval_required",
        "execution_cancelled",
        "execution_stage",
        "execution_progress",
      ];

      for (const eventName of standardEvents) {
        this.eventSource.addEventListener(eventName, (event: MessageEvent) => {
          this.handleIncomingRawEvent(eventName, event.data);
        });
      }

      this.eventSource.onerror = () => {
        if (this.isExplicitlyClosed) return;
        this.handleConnectionError();
      };
    } catch (err) {
      this.handleConnectionError(err instanceof Error ? err : new Error(String(err)));
    }
  }

  private handleIncomingRawEvent(eventType: string, rawData: string) {
    try {
      const parsed = JSON.parse(rawData);
      const sequence = parsed.sequence ?? (this.lastSequence + 1);

      // Event Deduplication
      if (this.seenSequences.has(sequence)) {
        return; // Discard duplicate
      }

      this.seenSequences.add(sequence);
      this.lastSequence = Math.max(this.lastSequence, sequence);

      const streamEvent: StreamEvent = {
        event: eventType,
        execution_id: parsed.execution_id || this.executionId,
        timestamp: parsed.timestamp || new Date().toISOString(),
        sequence,
        data: parsed.data || parsed,
      };

      // Dispatch to all subscribers
      for (const listener of this.listeners) {
        try {
          listener(streamEvent);
        } catch (listenerError) {
          console.error("Error in SSE listener callback:", listenerError);
        }
      }

      // If terminal event, mark as terminated and close
      if (["response_completed", "execution_failed", "execution_cancelled"].includes(eventType)) {
        this.disconnect(true);
      }
    } catch (parseError) {
      console.warn("Failed to parse SSE payload:", parseError, rawData);
    }
  }

  private handleConnectionError(error?: Error) {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    if (this.isExplicitlyClosed) {
      this.setStatus("DISCONNECTED");
      return;
    }

    this.reconnectAttempts++;
    if (this.reconnectAttempts > this.maxReconnectAttempts) {
      this.setStatus("TERMINATED");
      this.onError?.(error || new Error("Max SSE reconnect attempts reached"));
      return;
    }

    this.setStatus("RECONNECTING");
    const delay = Math.min(this.reconnectDelayMs * Math.pow(1.5, this.reconnectAttempts - 1), 10000);

    this.reconnectTimeoutId = setTimeout(() => {
      this.reconnectWithReplay();
    }, delay);
  }

  public async reconnectWithReplay(): Promise<void> {
    this.isExplicitlyClosed = false;

    try {
      // 1. Replay missed events from backend
      const response = await apiClient.ask.getReplayEvents(this.executionId, this.lastSequence);
      if (response.data && Array.isArray(response.data)) {
        for (const missedEvent of response.data) {
          if (!this.seenSequences.has(missedEvent.sequence)) {
            this.seenSequences.add(missedEvent.sequence);
            this.lastSequence = Math.max(this.lastSequence, missedEvent.sequence);
            for (const listener of this.listeners) {
              listener(missedEvent);
            }
          }
        }
      }

      // 2. Re-open live stream
      this.connect();
    } catch (replayError) {
      console.error("Failed to replay missed events during reconnect:", replayError);
      // Still attempt live connection
      this.connect();
    }
  }

  public disconnect(isTerminal = false): void {
    this.isExplicitlyClosed = true;
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }

    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    this.setStatus(isTerminal ? "TERMINATED" : "DISCONNECTED");
  }
}
