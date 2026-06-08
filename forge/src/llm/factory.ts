import type { ForgeConfig } from "../config/config.js";
import { AnthropicProvider } from "./anthropic.js";
import { OllamaProvider } from "./ollama.js";
import { OpenAIProvider } from "./openai.js";
import type { Provider } from "./types.js";

/** Build the active LLM provider from config. Optionally override the model. */
export function createProvider(cfg: ForgeConfig, model?: string): Provider {
  const m = model ?? cfg.model;
  switch (cfg.provider) {
    case "anthropic":
      if (!cfg.anthropicApiKey) {
        throw new Error(
          "ANTHROPIC_API_KEY is required for provider=anthropic. " +
            "Set it in .env or switch FORGE_PROVIDER to ollama/openai.",
        );
      }
      return new AnthropicProvider({
        apiKey: cfg.anthropicApiKey,
        model: m,
        maxTokens: cfg.maxTokens,
      });
    case "openai":
      return new OpenAIProvider({
        apiKey: cfg.openaiApiKey,
        model: m,
        baseUrl: cfg.baseUrl,
        maxTokens: cfg.maxTokens,
        temperature: cfg.temperature,
      });
    case "ollama":
      return new OllamaProvider({
        host: cfg.ollamaHost,
        model: m,
        maxTokens: cfg.maxTokens,
        temperature: cfg.temperature,
      });
    default:
      throw new Error(`Unknown provider: ${String(cfg.provider)}`);
  }
}
