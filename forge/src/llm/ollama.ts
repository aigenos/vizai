import { postJson } from "./http.js";
import { toOpenAIMessages } from "./openai.js";
import type {
  CompletionRequest,
  CompletionResult,
  Provider,
  StopReason,
  ToolUseBlock,
} from "./types.js";

/**
 * Ollama native adapter (`POST {host}/api/chat`).
 *
 * Ollama's chat API accepts OpenAI-style `tools` and returns tool calls on
 * `message.tool_calls`, but it expects tool-call arguments as JSON *objects*
 * (not stringified), which is why we pass `argsAsObject = true`.
 */
export interface OllamaConfig {
  host: string; // e.g. http://localhost:11434
  model: string;
  maxTokens?: number;
  temperature?: number;
}

interface OllamaToolCall {
  function?: { name?: string; arguments?: Record<string, unknown> };
}

interface OllamaResponse {
  message?: { content?: string; tool_calls?: OllamaToolCall[] };
  done_reason?: string;
  prompt_eval_count?: number;
  eval_count?: number;
}

export class OllamaProvider implements Provider {
  readonly kind = "ollama";
  readonly model: string;
  private readonly cfg: OllamaConfig;

  constructor(cfg: OllamaConfig) {
    this.cfg = cfg;
    this.model = cfg.model;
  }

  async complete(req: CompletionRequest): Promise<CompletionResult> {
    const body: Record<string, unknown> = {
      model: this.model,
      messages: toOpenAIMessages(req.system, req.messages, true),
      stream: false,
      options: {
        temperature: req.temperature ?? this.cfg.temperature ?? 0.2,
        num_predict: req.maxTokens ?? this.cfg.maxTokens ?? 8192,
      },
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

    const data = await postJson<OllamaResponse>({
      url: `${this.cfg.host.replace(/\/$/, "")}/api/chat`,
      body,
    });

    const text = data.message?.content ?? "";
    const toolCalls: ToolUseBlock[] = (data.message?.tool_calls ?? []).map(
      (tc, i) => ({
        type: "tool_use",
        id: `call_${i}_${Date.now()}`,
        name: tc.function?.name ?? "",
        input: tc.function?.arguments ?? {},
      }),
    );
    if (req.onText && text) req.onText(text);

    const stopReason: StopReason =
      toolCalls.length > 0
        ? "tool_use"
        : data.done_reason === "length"
          ? "max_tokens"
          : "end";

    return {
      text,
      toolCalls,
      stopReason,
      usage: {
        inputTokens: data.prompt_eval_count,
        outputTokens: data.eval_count,
      },
    };
  }
}
