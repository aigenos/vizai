import type { Tool } from "./types.js";
import { reqString } from "./types.js";

/** Sentinel a sub-agent uses to declare its assigned task finished. */
export const TASK_COMPLETE = "task_complete";

export const taskCompleteTool: Tool = {
  name: TASK_COMPLETE,
  description:
    "Call this when the assigned task is fully done. Provide a concise summary of what changed and how it was verified. " +
    "This ends your turn.",
  mutating: false,
  parameters: {
    type: "object",
    properties: {
      summary: { type: "string", description: "What you did and how you verified it." },
    },
    required: ["summary"],
  },
  async run(input) {
    return reqString(input, "summary");
  },
};
