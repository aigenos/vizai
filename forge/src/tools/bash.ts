import { spawn } from "node:child_process";
import type { Tool } from "./types.js";
import { reqString } from "./types.js";

const DEFAULT_TIMEOUT_MS = 120_000;
const MAX_OUTPUT = 60_000;

export const bashTool: Tool = {
  name: "bash",
  description:
    "Run a shell command in the workspace directory. Use for building, running tests, git, package managers, etc. " +
    "Read-only commands run automatically; mutating commands may require approval depending on permission mode. " +
    "Returns combined stdout/stderr and the exit code.",
  mutating: true,
  parameters: {
    type: "object",
    properties: {
      command: { type: "string", description: "The shell command to execute." },
      timeout_ms: { type: "number", description: "Optional timeout in ms (default 120000)." },
    },
    required: ["command"],
  },
  async run(input, ctx) {
    const command = reqString(input, "command");
    const timeout =
      typeof input.timeout_ms === "number" ? input.timeout_ms : DEFAULT_TIMEOUT_MS;

    const verdict = ctx.perms.classifyBash(command);
    if (verdict.decision === "deny") {
      return `Refused to run command. ${verdict.reason ?? ""}`.trim();
    }
    if (verdict.decision === "confirm") {
      const ok = await ctx.perms.confirm(
        `Run command?\n  $ ${command}${verdict.reason ? `\n  (${verdict.reason})` : ""}`,
      );
      if (!ok) return "Command not approved by user; skipped.";
    }

    ctx.log(`$ ${command}`);
    const { stdout, code } = await exec(command, ctx.workspace, timeout);
    const trimmed =
      stdout.length > MAX_OUTPUT
        ? stdout.slice(0, MAX_OUTPUT) + `\n…[truncated ${stdout.length - MAX_OUTPUT} chars]`
        : stdout;
    return `exit code: ${code}\n${trimmed || "(no output)"}`;
  },
};

function exec(
  command: string,
  cwd: string,
  timeoutMs: number,
): Promise<{ stdout: string; code: number }> {
  return new Promise((resolveP) => {
    const child = spawn(command, {
      cwd,
      shell: true,
      env: process.env,
    });
    let out = "";
    const onData = (d: Buffer) => {
      out += d.toString();
    };
    child.stdout.on("data", onData);
    child.stderr.on("data", onData);

    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      out += `\n…[killed: exceeded ${timeoutMs}ms timeout]`;
    }, timeoutMs);

    child.on("close", (code) => {
      clearTimeout(timer);
      resolveP({ stdout: out, code: code ?? -1 });
    });
    child.on("error", (err) => {
      clearTimeout(timer);
      resolveP({ stdout: `${out}\n${err.message}`, code: -1 });
    });
  });
}
