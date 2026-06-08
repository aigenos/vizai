/**
 * Provider-agnostic message and tool types.
 *
 * The internal representation mirrors Anthropic's content-block model (the
 * richest of the three backends). Each provider adapter is responsible for
 * translating to/from its own wire format, so the agent loop never has to know
 * which backend it is talking to.
 */

export type MessageRole = "user" | "assistant";

export interface TextBlock {
  type: "text";
  text: string;
}

export interface ToolUseBlock {
  type: "tool_use";
  /** Stable id so a result can be correlated back to the call. */
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export interface ToolResultBlock {
  type: "tool_result";
  toolUseId: string;
  content: string;
  isError?: boolean;
}

export type ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock;

export interface Message {
  role: MessageRole;
  content: ContentBlock[];
}

/** JSON-schema-ish description of a tool's input. */
export interface ToolSchema {
  name: string;
  description: string;
  parameters: {
    type: "object";
    properties: Record<string, unknown>;
    required?: string[];
  };
}

export interface CompletionRequest {
  system?: string;
  messages: Message[];
  tools?: ToolSchema[];
  temperature?: number;
  maxTokens?: number;
  /** Optional per-token streaming callback for live terminal output. */
  onText?: (delta: string) => void;
}

export type StopReason = "end" | "tool_use" | "max_tokens" | "other";

export interface Usage {
  inputTokens?: number;
  outputTokens?: number;
}

export interface CompletionResult {
  text: string;
  toolCalls: ToolUseBlock[];
  stopReason: StopReason;
  usage?: Usage;
}

export interface Provider {
  /** Backend identifier, e.g. "ollama", "openai", "anthropic". */
  readonly kind: string;
  /** The active model name. */
  readonly model: string;
  complete(req: CompletionRequest): Promise<CompletionResult>;
}

/** Convenience helpers for building messages. */
export function userText(text: string): Message {
  return { role: "user", content: [{ type: "text", text }] };
}

export function assistantText(text: string): Message {
  return { role: "assistant", content: [{ type: "text", text }] };
}

export function toolResults(results: ToolResultBlock[]): Message {
  return { role: "user", content: results };
}

/** Collect all plain text from a message's content blocks. */
export function textOf(message: Message): string {
  return message.content
    .filter((b): b is TextBlock => b.type === "text")
    .map((b) => b.text)
    .join("");
}
