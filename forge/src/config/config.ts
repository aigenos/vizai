import { readFileSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";

export type ProviderKind = "ollama" | "openai" | "anthropic";
export type PermissionMode = "safe" | "auto" | "yolo" | "readonly";

export interface ForgeConfig {
  provider: ProviderKind;
  model: string;
  /** OpenAI-compatible endpoint root, e.g. http://localhost:8000/v1 */
  baseUrl: string;
  /** Ollama host, e.g. http://localhost:11434 */
  ollamaHost: string;
  /** API key for the OpenAI-compatible endpoint (optional for local). */
  openaiApiKey?: string;
  anthropicApiKey?: string;
  maxTokens: number;
  temperature: number;
  /** Root directory the agent is allowed to touch. */
  workspace: string;
  permissionMode: PermissionMode;
  /** Max tool-using steps per single agent turn. */
  maxSteps: number;
}

const DEFAULT_MODELS: Record<ProviderKind, string> = {
  ollama: "qwen2.5-coder:7b",
  openai: "gpt-oss",
  anthropic: "claude-opus-4-8",
};

/** Tiny .env loader so `forge` works without extra deps. */
function loadDotEnv(dir: string): void {
  const path = join(dir, ".env");
  if (!existsSync(path)) return;
  for (const raw of readFileSync(path, "utf8").split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq < 0) continue;
    const key = line.slice(0, eq).trim();
    let val = line.slice(eq + 1).trim();
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1);
    }
    if (!(key in process.env)) process.env[key] = val;
  }
}

function loadConfigFile(workspace: string): Partial<ForgeConfig> {
  for (const path of [
    join(workspace, "forge.config.json"),
    join(homedir(), ".forge", "config.json"),
  ]) {
    if (existsSync(path)) {
      try {
        return JSON.parse(readFileSync(path, "utf8")) as Partial<ForgeConfig>;
      } catch {
        // ignore malformed config; fall through to env defaults
      }
    }
  }
  return {};
}

export function loadConfig(overrides: Partial<ForgeConfig> = {}): ForgeConfig {
  const workspace = resolve(
    overrides.workspace ?? process.env.FORGE_WORKSPACE ?? process.cwd(),
  );
  loadDotEnv(workspace);
  const file = loadConfigFile(workspace);

  const provider = (overrides.provider ??
    file.provider ??
    (process.env.FORGE_PROVIDER as ProviderKind | undefined) ??
    "ollama") as ProviderKind;

  const model =
    overrides.model ??
    file.model ??
    process.env.FORGE_MODEL ??
    DEFAULT_MODELS[provider];

  const permissionMode = (overrides.permissionMode ??
    file.permissionMode ??
    (process.env.FORGE_PERMISSION_MODE as PermissionMode | undefined) ??
    "safe") as PermissionMode;

  return {
    provider,
    model,
    baseUrl:
      overrides.baseUrl ??
      file.baseUrl ??
      process.env.FORGE_BASE_URL ??
      process.env.OPENAI_BASE_URL ??
      "http://localhost:8000/v1",
    ollamaHost:
      overrides.ollamaHost ??
      file.ollamaHost ??
      process.env.OLLAMA_HOST ??
      "http://localhost:11434",
    openaiApiKey:
      overrides.openaiApiKey ??
      file.openaiApiKey ??
      process.env.OPENAI_API_KEY ??
      process.env.FORGE_API_KEY,
    anthropicApiKey:
      overrides.anthropicApiKey ??
      file.anthropicApiKey ??
      process.env.ANTHROPIC_API_KEY,
    maxTokens:
      overrides.maxTokens ??
      file.maxTokens ??
      intEnv("FORGE_MAX_TOKENS", 8192),
    temperature:
      overrides.temperature ??
      file.temperature ??
      floatEnv("FORGE_TEMPERATURE", 0.2),
    workspace,
    permissionMode,
    maxSteps:
      overrides.maxSteps ?? file.maxSteps ?? intEnv("FORGE_MAX_STEPS", 50),
  };
}

function intEnv(name: string, fallback: number): number {
  const v = process.env[name];
  if (!v) return fallback;
  const n = Number.parseInt(v, 10);
  return Number.isFinite(n) ? n : fallback;
}

function floatEnv(name: string, fallback: number): number {
  const v = process.env[name];
  if (!v) return fallback;
  const n = Number.parseFloat(v);
  return Number.isFinite(n) ? n : fallback;
}
