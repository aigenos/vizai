import { postJson } from "./http.js";
import type {
  CompletionRequest,
  CompletionResult,
  Message,
  Provider,
  StopReason,
  ToolUseBlock,
} from "./types.js";

/**
 * OpenAI-compatible Chat Completions adapter.
 *
 * Works with any endpoint that implements `POST {baseUrl}/chat/completions`:
 * vLLM, LM Studio, LocalAI, llama.cpp server, OpenRouter, Together, Groq,
 * and OpenAI itself. Point `baseUrl` at the server's `/v1` root.
 */
export interface OpenAIConfig {
  apiKey?: string;
  model: string;
  baseUrl: string; // e.g. http://localhost:8000/v1
  maxTokens?: number;
  temperature?: number;
}

interface OAIToolCall {
  id?: string;
  function?: { name?: string; arguments?: string };
}

interface OAIResponse {
  choices?: Array<{
    message?: { content?: string | null; tool_calls?: OAIToolCall[] };
    finish_reason?: string;
  }>;
  usage?: { prompt_tokens?: number; completion_tokens?: number };
}

export class OpenAIProvider implements Provider {
  readonly kind = "openai";
  readonly model: string;
  private readonly cfg: OpenAIConfig;

  constructor(cfg: OpenAIConfig) {
    this.cfg = cfg;
    this.model = cfg.model;
  }

  async complete(req: CompletionRequest): Promise<CompletionResult> {
    const messages = toOpenAIMessages(req.system, req.messages);
    const body: Record<string, unknown> = {
      model: this.model,
      messages,
      max_tokens: req.maxTokens ?? this.cfg.maxTokens ?? 8192,
      temperature: req.temperature ?? this.cfg.temperature ?? 0.2,
      stream: false,
    };
    if (req.tools && req.tools.length > 0) {
      body.tools = req.tools.map((t) => ({
        type: "function",
        function: {
          name: t.name,
          description: t.description,
          parameters: t.parameters,
        },
      }));
    }

    const headers: Record<string, string> = {};
    if (this.cfg.apiKey) headers.authorization = `Bearer ${this.cfg.apiKey}`;

    const data = await postJson<OAIResponse>({
      url: `${this.cfg.baseUrl.replace(/\/$/, "")}/chat/completions`,
      headers,
      body,
    });

    const choice = data.choices?.[0];
    const text = choice?.message?.content ?? "";
    const toolCalls: ToolUseBlock[] = (choice?.message?.tool_calls ?? []).map(
      (tc, i) => ({
        type: "tool_use",
        id: tc.id ?? `call_${i}`,
        name: tc.function?.name ?? "",
        input: safeParse(tc.function?.arguments),
      }),
    );
    if (req.onText && text) req.onText(text);

    return {
      text,
      toolCalls,
      stopReason: mapStop(choice?.finish_reason, toolCalls.length > 0),
      usage: {
        inputTokens: data.usage?.prompt_tokens,
        outputTokens: data.usage?.completion_tokens,
      },
    };
  }
}

/** Shared conversion used by both the OpenAI and Ollama adapters. */
export function toOpenAIMessages(
  system: string | undefined,
  messages: Message[],
  argsAsObject = false,
): Array<Record<string, unknown>> {
  const out: Array<Record<string, unknown>> = [];
  if (system) out.push({ role: "system", content: system });

  for (const m of messages) {
    if (m.role === "assistant") {
      let text = "";
      const toolCalls: Array<Record<string, unknown>> = [];
      for (const b of m.content) {
        if (b.type === "text") text += b.text;
        else if (b.type === "tool_use") {
          toolCalls.push({
            id: b.id,
            type: "function",
            function: {
              name: b.name,
              arguments: argsAsObject ? b.input : JSON.stringify(b.input),
            },
          });
        }
      }
      const msg: Record<string, unknown> = { role: "assistant", content: text };
      if (toolCalls.length > 0) msg.tool_calls = toolCalls;
      out.push(msg);
    } else {
      // user: emit tool results first (must follow the assistant tool call),
      // then any free text.
      let text = "";
      for (const b of m.content) {
        if (b.type === "tool_result") {
          out.push({
            role: "tool",
            tool_call_id: b.toolUseId,
            content: b.content,
          });
        } else if (b.type === "text") {
          text += b.text;
        }
      }
      if (text) out.push({ role: "user", content: text });
    }
  }
  return out;
}

export function safeParse(s: string | undefined): Record<string, unknown> {
  if (!s) return {};
  try {
    const v = JSON.parse(s);
    return typeof v === "object" && v !== null ? (v as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function mapStop(reason: string | undefined, hasTools: boolean): StopReason {
  if (hasTools || reason === "tool_calls") return "tool_use";
  switch (reason) {
    case "stop":
      return "end";
    case "length":
      return "max_tokens";
    default:
      return "end";
  }
}
