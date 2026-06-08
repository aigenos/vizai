import type { ForgeConfig } from "../config/config.js";
import { PermissionChecker, type Confirmer } from "../safety/permissions.js";
import type { ToolContext } from "../tools/types.js";
import { Orchestrator, type TeamEvents } from "../orchestrator/orchestrator.js";
import { makeAgentEvents } from "./agentEvents.js";
import { banner, info, ok, warn, c, Spinner } from "./render.js";

const ROLE_ICON: Record<string, string> = {
  architect: "📐",
  coder: "💻",
  tester: "🧪",
  devops: "🚀",
  reviewer: "🔍",
};

export async function runTeam(
  cfg: ForgeConfig,
  goal: string,
  confirmer?: Confirmer,
): Promise<void> {
  const perms = new PermissionChecker(cfg.workspace, cfg.permissionMode, confirmer);
  const ctx: ToolContext = {
    workspace: cfg.workspace,
    perms,
    log: (l) => info("    " + l),
  };
  const spinner = new Spinner();
  const base = makeAgentEvents(spinner, "  ");

  const events: TeamEvents = {
    ...base,
    onPhase(phase) {
      spinner.stop();
      banner(`\n▣ ${phase}`);
    },
    onPlan(plan) {
      spinner.stop();
      ok(`\nPlan (${plan.tasks.length} tasks): ${plan.overview}`);
      info(plan.architecture);
      plan.tasks.forEach((t, i) => {
        const icon = ROLE_ICON[t.role] ?? "•";
        console.log(`  ${i + 1}. ${icon} ${c.bold(t.role)} — ${t.title}`);
      });
    },
    onTaskStart(task, index, total) {
      spinner.stop();
      const icon = ROLE_ICON[task.role] ?? "•";
      banner(`\n[${index}/${total}] ${icon} ${task.role.toUpperCase()}: ${task.title}`);
    },
    onTaskDone(task, summary) {
      spinner.stop();
      ok(`✓ ${task.title}`);
      info(indent(summary));
    },
    onReview(report, approved) {
      spinner.stop();
      if (approved) ok("\n✓ Review: APPROVED");
      else warn("\n△ Review: changes needed");
      console.log(indent(report));
    },
  };

  banner("⚒  Forge agent team");
  info(`goal: ${goal}`);
  info(`provider: ${cfg.provider} · model: ${cfg.model} · mode: ${cfg.permissionMode}\n`);

  const orch = new Orchestrator(cfg, ctx, events);
  try {
    const result = await orch.build(goal);
    spinner.stop();
    banner("\n══ Done ══");
    if (result.approved) ok("Goal delivered and reviewer-approved.");
    else warn("Completed with outstanding review notes (see above).");
    info(`${result.taskSummaries.length} tasks executed.`);
  } catch (e) {
    spinner.stop();
    console.error(c.red(`\nteam run failed: ${(e as Error).message}`));
  }
}

function indent(text: string): string {
  return text
    .split("\n")
    .map((l) => "    " + l)
    .join("\n");
}
