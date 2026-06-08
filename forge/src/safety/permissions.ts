import { resolve, relative, isAbsolute } from "node:path";
import type { PermissionMode } from "../config/config.js";

export type Decision = "allow" | "confirm" | "deny";

export interface PermissionResult {
  decision: Decision;
  reason?: string;
}

/** Confirm callback: return true to allow the action. */
export type Confirmer = (prompt: string) => Promise<boolean>;

/** Commands that are never auto-run and are blocked outright unless in yolo. */
const DANGEROUS_PATTERNS: Array<{ re: RegExp; why: string }> = [
  { re: /\brm\s+(-[a-z]*\s+)*-?[a-z]*f[a-z]*\s+(\/|~|\$HOME)(\s|$)/i, why: "recursive force-delete of a root/home path" },
  { re: /\brm\s+-rf\s+\*/i, why: "recursive force-delete with wildcard" },
  { re: /\bmkfs(\.\w+)?\b/i, why: "filesystem format" },
  { re: /\bdd\b.*\bof=\/dev\//i, why: "raw write to a device" },
  { re: /\b(shutdown|reboot|halt|poweroff)\b/i, why: "power-state change" },
  { re: /:\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;/, why: "fork bomb" },
  { re: />\s*\/dev\/(sd|nvme|hd)\w+/i, why: "overwrite of a block device" },
  { re: /\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(bash|sh|zsh)\b/i, why: "pipe-to-shell of remote content" },
  { re: /\bgit\s+push\b.*--force/i, why: "force push" },
];

/** Commands considered read-only / safe to run without confirmation. */
const SAFE_PREFIXES = [
  "ls", "cat", "pwd", "echo", "head", "tail", "wc", "grep", "rg", "find",
  "git status", "git diff", "git log", "git show", "git branch",
  "node --version", "npm --version", "python --version", "python3 --version",
  "which", "env", "date", "whoami", "tree", "stat", "file",
];

export class PermissionChecker {
  constructor(
    private readonly workspace: string,
    private readonly mode: PermissionMode,
    private readonly confirmer?: Confirmer,
  ) {}

  get permissionMode(): PermissionMode {
    return this.mode;
  }

  /** Whether a mutating (write/edit) tool is permitted at all. */
  canMutate(): boolean {
    return this.mode !== "readonly";
  }

  /**
   * Resolve a path and guarantee it stays inside the workspace sandbox.
   * Throws on traversal outside the root.
   */
  resolvePath(p: string): string {
    const abs = isAbsolute(p) ? resolve(p) : resolve(this.workspace, p);
    const rel = relative(this.workspace, abs);
    if (rel === "" ) return abs;
    if (rel.startsWith("..") || isAbsolute(rel)) {
      throw new Error(
        `Path escapes the workspace sandbox: ${p} (workspace: ${this.workspace})`,
      );
    }
    return abs;
  }

  /** Static classification of a shell command under the current mode. */
  classifyBash(command: string): PermissionResult {
    const cmd = command.trim();
    for (const { re, why } of DANGEROUS_PATTERNS) {
      if (re.test(cmd)) {
        if (this.mode === "yolo") return { decision: "confirm", reason: why };
        return { decision: "deny", reason: `Blocked dangerous command (${why}).` };
      }
    }
    if (this.mode === "yolo" || this.mode === "auto") return { decision: "allow" };
    if (this.mode === "readonly") {
      return isSafe(cmd)
        ? { decision: "allow" }
        : { decision: "deny", reason: "readonly mode: only read-only commands allowed." };
    }
    // safe mode: auto-allow read-only commands, confirm the rest.
    return isSafe(cmd) ? { decision: "allow" } : { decision: "confirm" };
  }

  /** Resolve a `confirm` decision via the injected confirmer (defaults to deny). */
  async confirm(prompt: string): Promise<boolean> {
    if (!this.confirmer) return false;
    return this.confirmer(prompt);
  }
}

function isSafe(cmd: string): boolean {
  return SAFE_PREFIXES.some(
    (p) => cmd === p || cmd.startsWith(p + " ") || cmd.startsWith(p + "\t"),
  );
}
