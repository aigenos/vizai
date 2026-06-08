/** Minimal ANSI styling with no dependencies. Honors NO_COLOR and non-TTY. */
const enabled =
  process.stdout.isTTY && !process.env.NO_COLOR && process.env.TERM !== "dumb";

function wrap(code: number, close: number) {
  return (s: string) => (enabled ? `\x1b[${code}m${s}\x1b[${close}m` : s);
}

export const c = {
  bold: wrap(1, 22),
  dim: wrap(2, 22),
  red: wrap(31, 39),
  green: wrap(32, 39),
  yellow: wrap(33, 39),
  blue: wrap(34, 39),
  magenta: wrap(35, 39),
  cyan: wrap(36, 39),
  gray: wrap(90, 39),
};

export function banner(line: string): void {
  console.log(c.bold(c.cyan(line)));
}

export function info(line: string): void {
  console.log(c.gray(line));
}

export function ok(line: string): void {
  console.log(c.green(line));
}

export function warn(line: string): void {
  console.log(c.yellow(line));
}

export function err(line: string): void {
  console.error(c.red(line));
}

/** Render a tool invocation compactly. */
export function renderTool(name: string, input: Record<string, unknown>): void {
  const detail = summarizeInput(name, input);
  console.log(`  ${c.magenta("⚙")} ${c.bold(name)} ${c.dim(detail)}`);
}

export function renderToolResult(_name: string, result: string, isError: boolean): void {
  const firstLine = result.split("\n")[0] ?? "";
  const preview = firstLine.length > 100 ? firstLine.slice(0, 100) + "…" : firstLine;
  const mark = isError ? c.red("✗") : c.green("✓");
  console.log(`  ${mark} ${c.dim(preview || "(done)")}`);
}

function summarizeInput(name: string, input: Record<string, unknown>): string {
  if (name === "bash") return String(input.command ?? "");
  if (typeof input.path === "string") return input.path;
  if (typeof input.pattern === "string") return input.pattern;
  if (typeof input.summary === "string") return "";
  const keys = Object.keys(input);
  return keys.length ? `{${keys.join(", ")}}` : "";
}

/** A tiny indeterminate spinner controllable via start/stop. */
export class Spinner {
  private frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
  private i = 0;
  private timer?: NodeJS.Timeout;
  private text = "";

  start(text: string): void {
    if (!enabled) {
      process.stdout.write(text + "\n");
      return;
    }
    this.text = text;
    this.stop();
    this.timer = setInterval(() => {
      process.stdout.write(`\r${c.cyan(this.frames[this.i])} ${c.dim(this.text)}  `);
      this.i = (this.i + 1) % this.frames.length;
    }, 80);
  }

  update(text: string): void {
    this.text = text;
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
      if (enabled) process.stdout.write("\r\x1b[2K");
    }
  }
}
