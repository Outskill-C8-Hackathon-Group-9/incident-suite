import type { AnalyzeCallbacks, AnalysisResult, NodeEvent } from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

interface SseFrame {
  evt: string | undefined;
  data: unknown;
}

function parseSseFrames(buffer: string): { events: SseFrame[]; rest: string } {
  // sse-starlette emits CRLF (\r\n); normalize so \n\n frame splits work.
  const normalized = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const frames = normalized.split("\n\n");
  const rest = frames.pop() ?? "";
  const events: SseFrame[] = [];
  for (const frame of frames) {
    if (!frame.trim()) continue;
    const evt = frame.match(/^event: (.*)$/m)?.[1]?.trim();
    const data = frame.match(/^data: (.*)$/m)?.[1];
    if (!data) continue;
    events.push({ evt, data: JSON.parse(data) as unknown });
  }
  return { events, rest };
}

export async function analyze(
  file: File,
  { onNode, onDone, onError }: AnalyzeCallbacks,
): Promise<void> {
  let sawDone = false;
  try {
    const form = new FormData();
    form.append("file", file);

    const res = await fetch(`${BASE}/api/analyze`, { method: "POST", body: form });
    if (!res.ok || !res.body) throw new Error(`Request failed: ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const dispatch = (events: SseFrame[]): void => {
      for (const { evt, data } of events) {
        if (evt === "node") onNode?.(data as NodeEvent);
        else if (evt === "done") {
          sawDone = true;
          onDone?.(data as AnalysisResult);
        }
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSseFrames(buffer);
      buffer = parsed.rest;
      dispatch(parsed.events);
    }

    // Flush any trailing frame left without a final blank line.
    buffer += decoder.decode();
    if (buffer.trim()) {
      const parsed = parseSseFrames(
        buffer.endsWith("\n\n") ? buffer : `${buffer}\n\n`,
      );
      dispatch(parsed.events);
    }

    if (!sawDone) {
      onError?.(new Error("Analysis stream ended before results were received."));
    }
  } catch (err) {
    if (!sawDone) onError?.(err instanceof Error ? err : new Error(String(err)));
  }
}

