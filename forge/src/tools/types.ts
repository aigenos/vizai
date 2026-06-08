import type { PermissionChecker } from "../safety/permissions.js";
import type { ToolSchema } from "../llm/types.js";

export interface ToolContext {
  workspace: string;
  perms: PermissionChecker;
  /** Structured log sink for tool activity (rendered by the CLI). */
  log: (line: string) => void;
}

export interface Tool {
  name: string;
  description: string;
  parameters: ToolSchema["parameters"];
  /** True if the tool can modify the filesystem or run side effects. */
  mutating: boolean;
  run(input: Record<string, unknown>, ctx: ToolContext): Promise<string>;
}

export function toToolSchema(t: Tool): ToolSchema {
  return { name: t.name, description: t.description, parameters: t.parameters };
}

/** Coerce an unknown tool-arg value to a string, or throw if missing. */
export function reqString(
  input: Record<string, unknown>,
  key: string,
): string {
  const v = input[key];
  if (typeof v !== "string" || v.length === 0) {
    throw new Error(`Missing required string argument: ${key}`);
  }
  return v;
}

export function optString(
  input: Record<string, unknown>,
  key: string,
): string | undefined {
  const v = input[key];
  return typeof v === "string" ? v : undefined;
}
