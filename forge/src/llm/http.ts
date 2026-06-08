/** Minimal HTTP helper with exponential-backoff retries for transient errors. */

export interface PostJsonOptions {
  url: string;
  headers?: Record<string, string>;
  body: unknown;
  /** Max attempts including the first. Default 4. */
  retries?: number;
  timeoutMs?: number;
}

const TRANSIENT_STATUS = new Set([408, 409, 429, 500, 502, 503, 504]);

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function postJson<T = unknown>(opts: PostJsonOptions): Promise<T> {
  const retries = opts.retries ?? 4;
  const timeoutMs = opts.timeoutMs ?? 300_000;
  let lastErr: unknown;

  for (let attempt = 0; attempt < retries; attempt++) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const res = await fetch(opts.url, {
        method: "POST",
        headers: { "content-type": "application/json", ...opts.headers },
        body: JSON.stringify(opts.body),
        signal: ctrl.signal,
      });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        if (TRANSIENT_STATUS.has(res.status) && attempt < retries - 1) {
          await sleep(backoff(attempt));
          continue;
        }
        throw new Error(
          `HTTP ${res.status} from ${opts.url}: ${truncate(text, 600)}`,
        );
      }
      return (await res.json()) as T;
    } catch (err) {
      lastErr = err;
      const retriable = isNetworkError(err) && attempt < retries - 1;
      if (!retriable) break;
      await sleep(backoff(attempt));
    } finally {
      clearTimeout(timer);
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
}

/** POST and stream a response body line-by-line (for NDJSON / SSE backends). */
export async function postStream(
  opts: PostJsonOptions,
  onLine: (line: string) => void,
): Promise<void> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 600_000);
  try {
    const res = await fetch(opts.url, {
      method: "POST",
      headers: { "content-type": "application/json", ...opts.headers },
      body: JSON.stringify(opts.body),
      signal: ctrl.signal,
    });
    if (!res.ok || !res.body) {
      const text = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status} from ${opts.url}: ${truncate(text, 600)}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let nl: number;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (line) onLine(line);
      }
    }
    if (buf.trim()) onLine(buf.trim());
  } finally {
    clearTimeout(timer);
  }
}

function backoff(attempt: number): number {
  return Math.min(16_000, 1000 * 2 ** attempt) + Math.floor(Math.random() * 250);
}

function isNetworkError(err: unknown): boolean {
  if (err instanceof Error) {
    return (
      err.name === "AbortError" ||
      err.name === "TypeError" ||
      /fetch failed|ECONNRESET|ETIMEDOUT|ENOTFOUND|socket hang up/i.test(err.message)
    );
  }
  return false;
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + "…" : s;
}
