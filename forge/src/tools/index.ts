import type { ToolSchema } from "../llm/types.js";
import { bashTool } from "./bash.js";
import { taskCompleteTool } from "./finish.js";
import { editFileTool, listFilesTool, readFileTool, writeFileTool } from "./fs.js";
import { globTool, searchTextTool } from "./search.js";
import { toToolSchema, type Tool } from "./types.js";

/** All tools available to interactive single-agent sessions. */
export const BASE_TOOLS: Tool[] = [
  readFileTool,
  writeFileTool,
  editFileTool,
  listFilesTool,
  searchTextTool,
  globTool,
  bashTool,
];

/** Tools available to orchestrated sub-agents (adds the completion sentinel). */
export const AGENT_TOOLS: Tool[] = [...BASE_TOOLS, taskCompleteTool];

export function toolRegistry(tools: Tool[]): Map<string, Tool> {
  return new Map(tools.map((t) => [t.name, t]));
}

export function toSchemas(tools: Tool[]): ToolSchema[] {
  return tools.map(toToolSchema);
}

export { type Tool } from "./types.js";
