import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AnalystSSEClient } from "@/lib/sse/sse-client";
import { apiClient } from "@/lib/api/client";
import { StreamEvent } from "@/types/platform";

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    ask: {
      getReplayEvents: vi.fn(),
    },
  },
}));

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  listeners: Record<string, ((event: { data: string }) => void)[]> = {};
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(event: string, callback: (event: { data: string }) => void) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(callback);
  }

  emit(event: string, data: unknown) {
    const list = this.listeners[event] || [];
    for (const cb of list) {
      cb({ data: JSON.stringify(data) });
    }
  }
}

describe("Mandatory SSE E2E Reconnect & Replay Scenario — Section 56", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    // @ts-expect-error Mocking global EventSource
    global.EventSource = MockEventSource;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("handles full lifecycle: connect -> events 1..3 -> disconnect -> reconnect -> replay 4..5 -> complete", async () => {
    const receivedEvents: StreamEvent[] = [];
    const client = new AnalystSSEClient({
      executionId: "exec-scenario-56",
      onEvent: (evt) => receivedEvents.push(evt),
    });

    // 1. Connect SSE
    client.connect();
    expect(MockEventSource.instances.length).toBe(1);
    const firstConnection = MockEventSource.instances[0];

    // 2. Receive ordered events (sequence 1, 2, 3)
    firstConnection.emit("execution_started", { sequence: 1, data: { status: "START" } });
    firstConnection.emit("execution_stage", { sequence: 2, data: { stage: "SEMANTIC" } });
    firstConnection.emit("execution_stage", { sequence: 3, data: { stage: "GRAPH" } });

    expect(receivedEvents.length).toBe(3);
    expect(client.getLastSequence()).toBe(3);

    // 3. Disconnect (simulate connection drop or network switch)
    client.disconnect();
    expect(firstConnection.close).toHaveBeenCalled();
    expect(client.getStatus()).toBe("DISCONNECTED");

    // 4. Mock backend replay response for missing events 4 and 5
    const missedEvents: StreamEvent[] = [
      {
        event: "execution_stage",
        execution_id: "exec-scenario-56",
        sequence: 4,
        timestamp: new Date().toISOString(),
        data: { stage: "PLANNING" },
      },
      {
        event: "evidence_collected",
        execution_id: "exec-scenario-56",
        sequence: 5,
        timestamp: new Date().toISOString(),
        data: { count: 2 },
      },
    ];

    (apiClient.ask.getReplayEvents as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: missedEvents,
    });

    // 5. Reconnect with Replay
    await client.reconnectWithReplay();

    // Verify replay API called with lastSequence=3
    expect(apiClient.ask.getReplayEvents).toHaveBeenCalledWith("exec-scenario-56", 3);

    // Verify missed events replayed into event stream
    expect(receivedEvents.length).toBe(5);
    expect(receivedEvents[3].sequence).toBe(4);
    expect(receivedEvents[4].sequence).toBe(5);
    expect(client.getLastSequence()).toBe(5);

    // 6. Resume live stream on new connection and receive final response_completed (sequence 6)
    expect(MockEventSource.instances.length).toBe(2);
    const secondConnection = MockEventSource.instances[1];

    secondConnection.emit("response_completed", {
      sequence: 6,
      data: { answer: "All analysis completed reliably." },
    });

    expect(receivedEvents.length).toBe(6);
    expect(receivedEvents[5].sequence).toBe(6);
    expect(client.getStatus()).toBe("TERMINATED");
  });
});
