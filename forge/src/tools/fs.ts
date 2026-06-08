import { readFile, writeFile, mkdir, readdir, stat } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import type { Tool } from "./types.js";
import { reqString, optString } from "./types.js";

const MAX_READ_BYTES = 256 * 1024;

export const readFileTool: Tool = {
  name: "read_file",
  description:
    "Read a UTF-8 text file from the workspace. Returns the file contents with line numbers. Use before editing.",
  mutating: false,
  parameters: {
    type: "object",
    properties: {
      path: { type: "string", description: "Path relative to the workspace root." },
    },
    required: ["path"],
  },
  async run(input, ctx) {
    const abs = ctx.perms.resolvePath(reqString(input, "path"));
    const buf = await readFile(abs);
    if (buf.byteLength > MAX_READ_BYTES) {
      return `File is ${buf.byteLength} bytes (over ${MAX_READ_BYTES}). Read a smaller slice or use search.`;
    }
    const lines = buf.toString("utf8").split("\n");
    return lines.map((l, i) => `${String(i + 1).padStart(5)}\t${l}`).join("\n");
  },
};

export const writeFileTool: Tool = {
  name: "write_file",
  description:
    "Create or overwrite a file with the given content. Creates parent directories as needed.",
  mutating: true,
  parameters: {
    type: "object",
    properties: {
      path: { type: "string", description: "Path relative to the workspace root." },
      content: { type: "string", description: "Full file content to write." },
    },
    required: ["path", "content"],
  },
  async run(input, ctx) {
    const rel = reqString(input, "path");
    const content = reqString(input, "content");
    const abs = ctx.perms.resolvePath(rel);
    await mkdir(dirname(abs), { recursive: true });
    await writeFile(abs, content, "utf8");
    ctx.log(`wrote ${rel} (${content.length} chars)`);
    return `Wrote ${content.length} chars to ${rel}.`;
  },
};

export const editFileTool: Tool = {
  name: "edit_file",
  description:
    "Replace an exact substring in a file with new text. The old_string must appear exactly once unless replace_all is true.",
  mutating: true,
  parameters: {
    type: "object",
    properties: {
      path: { type: "string", description: "Path relative to the workspace root." },
      old_string: { type: "string", description: "Exact text to find." },
      new_string: { type: "string", description: "Replacement text." },
      replace_all: { type: "boolean", description: "Replace every occurrence." },
    },
    required: ["path", "old_string", "new_string"],
  },
  async run(input, ctx) {
    const rel = reqString(input, "path");
    const oldStr = reqString(input, "old_string");
    const newStr = optString(input, "new_string") ?? "";
    const replaceAll = input.replace_all === true;
    const abs = ctx.perms.resolvePath(rel);
    const original = await readFile(abs, "utf8");

    const count = original.split(oldStr).length - 1;
    if (count === 0) return `No match for old_string in ${rel}. Read the file first.`;
    if (count > 1 && !replaceAll) {
      return `old_string appears ${count} times in ${rel}; pass replace_all or add more context.`;
    }
    const updated = replaceAll
      ? original.split(oldStr).join(newStr)
      : original.replace(oldStr, newStr);
    await writeFile(abs, updated, "utf8");
    ctx.log(`edited ${rel} (${count} replacement${count > 1 ? "s" : ""})`);
    return `Edited ${rel} (${count} replacement${count > 1 ? "s" : ""}).`;
  },
};

export const listFilesTool: Tool = {
  name: "list_files",
  description:
    "List files and directories under a workspace path (non-recursive by default). Skips node_modules and .git.",
  mutating: false,
  parameters: {
    type: "object",
    properties: {
      path: { type: "string", description: "Directory relative to workspace root (default '.')." },
      recursive: { type: "boolean", description: "Recurse into subdirectories." },
    },
    required: [],
  },
  async run(input, ctx) {
    const rel = optString(input, "path") ?? ".";
    const recursive = input.recursive === true;
    const base = ctx.perms.resolvePath(rel);
    const out: string[] = [];
    await walk(base, ctx.workspace, recursive, out);
    if (out.length === 0) return `(empty: ${rel})`;
    return out.slice(0, 500).join("\n");
  },
};

async function walk(
  dir: string,
  workspace: string,
  recursive: boolean,
  out: string[],
): Promise<void> {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const e of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (e.name === "node_modules" || e.name === ".git") continue;
    const full = join(dir, e.name);
    const rel = relative(workspace, full);
    if (e.isDirectory()) {
      out.push(`${rel}/`);
      if (recursive) await walk(full, workspace, recursive, out);
    } else {
      out.push(rel);
    }
  }
}

export async function fileExists(path: string): Promise<boolean> {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}
