import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AnalystSSEClient } from "@/lib/sse/sse-client";
import { StreamEvent } from "@/types/platform";

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  options?: unknown;
  listeners: Record<string, ((event: { data: string }) => void)[]> = {};
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();

  constructor(url: string, options?: unknown) {
    this.url = url;
    this.options = options;
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

describe("AnalystSSEClient Unit Tests", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    // @ts-expect-error Mocking global EventSource with mock class
    global.EventSource = MockEventSource;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("initializes with DISCONNECTED status and connects to correct URL", () => {
    const client = new AnalystSSEClient({ executionId: "test-exec-123" });
    expect(client.getStatus()).toBe("DISCONNECTED");

    client.connect();
    expect(MockEventSource.instances.length).toBe(1);
    expect(MockEventSource.instances[0].url).toBe(
      "http://localhost:8000/api/v1/ask/test-exec-123/stream"
    );
  });

  it("deduplicates events with identical sequence numbers", () => {
    const receivedEvents: StreamEvent[] = [];
    const client = new AnalystSSEClient({
      executionId: "test-exec-123",
      onEvent: (evt) => receivedEvents.push(evt),
    });

    client.connect();
    const eventSourceInstance = MockEventSource.instances[0];
    expect(eventSourceInstance).toBeDefined();

    // 1. Emit sequence 1
    eventSourceInstance.emit("execution_stage", {
      sequence: 1,
      execution_id: "test-exec-123",
      data: { stage: "SEMANTIC" },
    });

    // 2. Emit duplicate sequence 1
    eventSourceInstance.emit("execution_stage", {
      sequence: 1,
      execution_id: "test-exec-123",
      data: { stage: "SEMANTIC" },
    });

    // 3. Emit sequence 2
    eventSourceInstance.emit("execution_stage", {
      sequence: 2,
      execution_id: "test-exec-123",
      data: { stage: "GRAPH" },
    });

    // Only sequence 1 and 2 must have been processed, duplicate sequence 1 ignored
    expect(receivedEvents.length).toBe(2);
    expect(receivedEvents[0].sequence).toBe(1);
    expect(receivedEvents[1].sequence).toBe(2);
    expect(client.getLastSequence()).toBe(2);
  });

  it("transitions to TERMINATED on terminal events and closes connection", () => {
    const client = new AnalystSSEClient({ executionId: "test-exec-123" });
    client.connect();

    const eventSourceInstance = MockEventSource.instances[0];
    expect(eventSourceInstance).toBeDefined();

    eventSourceInstance.emit("response_completed", {
      sequence: 5,
      execution_id: "test-exec-123",
      data: { answer: "Final answer" },
    });

    expect(eventSourceInstance.close).toHaveBeenCalled();
    expect(client.getStatus()).toBe("TERMINATED");
  });
});
