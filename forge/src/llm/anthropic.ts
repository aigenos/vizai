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
 * Anthropic Messages API adapter.
 *
 * Note: the default model (claude-opus-4-8) rejects `temperature`/`top_p` and
 * `thinking.budget_tokens`, so this adapter never sends sampling parameters.
 * Thinking is left off by default to keep the tool loop simple and portable
 * across Opus/Sonnet/Haiku.
 */
export interface AnthropicConfig {
  apiKey: string;
  model: string;
  baseUrl?: string;
  maxTokens?: number;
  anthropicVersion?: string;
}

interface AnthropicContentBlock {
  type: string;
  text?: string;
  id?: string;
  name?: string;
  input?: Record<string, unknown>;
}

interface AnthropicResponse {
  content: AnthropicContentBlock[];
  stop_reason: string | null;
  usage?: { input_tokens?: number; output_tokens?: number };
}

export class AnthropicProvider implements Provider {
  readonly kind = "anthropic";
  readonly model: string;
  private readonly cfg: AnthropicConfig;

  constructor(cfg: AnthropicConfig) {
    this.cfg = cfg;
    this.model = cfg.model;
  }

  async complete(req: CompletionRequest): Promise<CompletionResult> {
    const body: Record<string, unknown> = {
      model: this.model,
      max_tokens: req.maxTokens ?? this.cfg.maxTokens ?? 8192,
      messages: req.messages.map(toAnthropicMessage),
    };
    if (req.system) body.system = req.system;
    if (req.tools && req.tools.length > 0) {
      body.tools = req.tools.map((t) => ({
        name: t.name,
        description: t.description,
        input_schema: t.parameters,
      }));
    }

    const data = await postJson<AnthropicResponse>({
      url: `${this.cfg.baseUrl ?? "https://api.anthropic.com"}/v1/messages`,
      headers: {
        "x-api-key": this.cfg.apiKey,
        "anthropic-version": this.cfg.anthropicVersion ?? "2023-06-01",
      },
      body,
    });

    let text = "";
    const toolCalls: ToolUseBlock[] = [];
    for (const block of data.content ?? []) {
      if (block.type === "text" && block.text) text += block.text;
      else if (block.type === "tool_use") {
        toolCalls.push({
          type: "tool_use",
          id: block.id ?? `call_${toolCalls.length}`,
          name: block.name ?? "",
          input: block.input ?? {},
        });
      }
    }
    if (req.onText && text) req.onText(text);

    return {
      text,
      toolCalls,
      stopReason: mapStop(data.stop_reason),
      usage: {
        inputTokens: data.usage?.input_tokens,
        outputTokens: data.usage?.output_tokens,
      },
    };
  }
}

function toAnthropicMessage(m: Message): Record<string, unknown> {
  // The internal model already mirrors Anthropic's shape; map block names.
  return {
    role: m.role,
    content: m.content.map((b) => {
      if (b.type === "text") return { type: "text", text: b.text };
      if (b.type === "tool_use")
        return { type: "tool_use", id: b.id, name: b.name, input: b.input };
      return {
        type: "tool_result",
        tool_use_id: b.toolUseId,
        content: b.content,
        ...(b.isError ? { is_error: true } : {}),
      };
    }),
  };
}

function mapStop(reason: string | null): StopReason {
  switch (reason) {
    case "end_turn":
    case "stop_sequence":
      return "end";
    case "tool_use":
      return "tool_use";
    case "max_tokens":
      return "max_tokens";
    default:
      return "other";
  }
}
