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

describe("SSE E2E Stream Protocol & Replay Lifecycle", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    // @ts-expect-error Mocking global EventSource with mock class
    global.EventSource = MockEventSource;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("SSE E2E: connect -> receive events -> dedup -> terminal completion", () => {
    const events: StreamEvent[] = [];
    const client = new AnalystSSEClient({
      executionId: "exec-e2e-999",
      onEvent: (evt) => events.push(evt),
    });

    // 1. Connect
    client.connect();
    expect(client.getStatus()).toBe("CONNECTING");

    const es = MockEventSource.instances[0];
    if (es.onopen) es.onopen();
    expect(client.getStatus()).toBe("CONNECTED");

    // 2. Progressive events
    es.emit("plan_generated", { sequence: 1, plan: "hybrid_search" });
    es.emit("evidence_collected", { sequence: 2, count: 3 });
    expect(events.length).toBe(2);

    // 3. Receive duplicate (sequence 2)
    es.emit("evidence_collected", { sequence: 2, count: 3 });
    expect(events.length).toBe(2); // deduplicated

    // 4. Terminal completion event
    es.emit("response_completed", { sequence: 3, answer: "Done" });
    expect(events.length).toBe(3);
    expect(events[2].sequence).toBe(3);
    expect(client.getStatus()).toBe("TERMINATED");
  });
});
