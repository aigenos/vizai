import { readdir, readFile } from "node:fs/promises";
import { join, relative } from "node:path";
import type { Tool } from "./types.js";
import { reqString, optString } from "./types.js";

const SKIP_DIRS = new Set(["node_modules", ".git", "dist", "build", ".next", "coverage"]);
const MAX_FILE_BYTES = 1024 * 1024;

export const searchTextTool: Tool = {
  name: "search_text",
  description:
    "Search file contents under the workspace using a regular expression. Returns matching lines as path:line: text.",
  mutating: false,
  parameters: {
    type: "object",
    properties: {
      pattern: { type: "string", description: "JavaScript regular expression." },
      path: { type: "string", description: "Directory to search (default '.')." },
      ext: { type: "string", description: "Optional file extension filter, e.g. 'ts'." },
      max_results: { type: "number", description: "Max matches to return (default 100)." },
    },
    required: ["pattern"],
  },
  async run(input, ctx) {
    const pattern = reqString(input, "pattern");
    const ext = optString(input, "ext");
    const max = typeof input.max_results === "number" ? input.max_results : 100;
    const base = ctx.perms.resolvePath(optString(input, "path") ?? ".");
    let re: RegExp;
    try {
      re = new RegExp(pattern);
    } catch (err) {
      return `Invalid regex: ${(err as Error).message}`;
    }

    const results: string[] = [];
    const files: string[] = [];
    await collectFiles(base, files);
    for (const f of files) {
      if (ext && !f.endsWith("." + ext)) continue;
      let content: string;
      try {
        const buf = await readFile(f);
        if (buf.byteLength > MAX_FILE_BYTES) continue;
        content = buf.toString("utf8");
      } catch {
        continue;
      }
      const lines = content.split("\n");
      for (let i = 0; i < lines.length; i++) {
        if (re.test(lines[i])) {
          results.push(`${relative(ctx.workspace, f)}:${i + 1}: ${lines[i].trim().slice(0, 200)}`);
          if (results.length >= max) return results.join("\n");
        }
      }
    }
    return results.length ? results.join("\n") : `No matches for /${pattern}/.`;
  },
};

export const globTool: Tool = {
  name: "glob",
  description:
    "Find files matching a glob pattern (supports ** and *). Returns matching paths relative to the workspace.",
  mutating: false,
  parameters: {
    type: "object",
    properties: {
      pattern: { type: "string", description: "Glob, e.g. 'src/**/*.ts'." },
    },
    required: ["pattern"],
  },
  async run(input, ctx) {
    const pattern = reqString(input, "pattern");
    const re = globToRegExp(pattern);
    const files: string[] = [];
    await collectFiles(ctx.workspace, files);
    const matched = files
      .map((f) => relative(ctx.workspace, f))
      .filter((p) => re.test(p))
      .sort()
      .slice(0, 500);
    return matched.length ? matched.join("\n") : `No files match ${pattern}.`;
  },
};

async function collectFiles(dir: string, out: string[]): Promise<void> {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const e of entries) {
    if (e.isDirectory()) {
      if (SKIP_DIRS.has(e.name)) continue;
      await collectFiles(join(dir, e.name), out);
    } else {
      out.push(join(dir, e.name));
    }
  }
}

function globToRegExp(glob: string): RegExp {
  let re = "";
  for (let i = 0; i < glob.length; i++) {
    const c = glob[i];
    if (c === "*") {
      if (glob[i + 1] === "*") {
        re += ".*";
        i++;
        if (glob[i + 1] === "/") i++;
      } else {
        re += "[^/]*";
      }
    } else if (c === "?") {
      re += "[^/]";
    } else if (".+^${}()|[]\\".includes(c)) {
      re += "\\" + c;
    } else {
      re += c;
    }
  }
  return new RegExp("^" + re + "$");
}
