import type { AgentEvents } from "../agent/agent.js";
import { Spinner, c, renderTool, renderToolResult } from "./render.js";

/** Wire agent lifecycle events to the terminal with a spinner. */
export function makeAgentEvents(spinner: Spinner, labelPrefix = ""): AgentEvents {
  return {
    onStep(step, max) {
      spinner.start(`${labelPrefix}thinking… (step ${step}/${max})`);
    },
    onAssistantText(text) {
      spinner.stop();
      const trimmed = text.trim();
      if (trimmed) console.log(c.bold("\nForge: ") + trimmed + "\n");
    },
    onToolStart(name, input) {
      spinner.stop();
      renderTool(name, input);
    },
    onToolResult(name, result, isError) {
      renderToolResult(name, result, isError);
    },
  };
}
