import type { ForgeConfig } from "../config/config.js";
import { createProvider } from "../llm/factory.js";
import type { Provider } from "../llm/types.js";
import { AGENT_TOOLS } from "../tools/index.js";
import type { ToolContext } from "../tools/types.js";
import { Agent, type AgentEvents } from "../agent/agent.js";
import { planProject, type Plan, type PlanTask } from "./planner.js";
import { ROLE_SYSTEM } from "./roles.js";

export interface TeamEvents extends AgentEvents {
  onPhase?: (phase: string) => void;
  onPlan?: (plan: Plan) => void;
  onTaskStart?: (task: PlanTask, index: number, total: number) => void;
  onTaskDone?: (task: PlanTask, summary: string) => void;
  onReview?: (report: string, approved: boolean) => void;
}

export interface TeamResult {
  plan: Plan;
  taskSummaries: Array<{ task: PlanTask; summary: string }>;
  review: string;
  approved: boolean;
}

export class Orchestrator {
  private readonly provider: Provider;

  constructor(
    private readonly cfg: ForgeConfig,
    private readonly ctx: ToolContext,
    private readonly events: TeamEvents = {},
  ) {
    this.provider = createProvider(cfg);
  }

  async build(goal: string): Promise<TeamResult> {
    this.events.onPhase?.("Planning (PM)");
    const plan = await planProject(this.provider, goal);
    this.events.onPlan?.(plan);

    const summaries: Array<{ task: PlanTask; summary: string }> = [];
    const contextParts: string[] = [
      `OVERVIEW: ${plan.overview}`,
      `ARCHITECTURE: ${plan.architecture}`,
    ];

    for (let i = 0; i < plan.tasks.length; i++) {
      const task = plan.tasks[i];
      this.events.onTaskStart?.(task, i + 1, plan.tasks.length);
      const summary = await this.runTask(goal, task, contextParts.join("\n"));
      summaries.push({ task, summary });
      contextParts.push(`COMPLETED [${task.role}] ${task.title}: ${summary}`);
      this.events.onTaskDone?.(task, summary);
    }

    // Review, with up to one remediation round.
    let review = await this.runReview(goal, plan, contextParts.join("\n"));
    let approved = isApproved(review);
    this.events.onReview?.(review, approved);

    if (!approved) {
      this.events.onPhase?.("Remediation (Coder)");
      const fixTask: PlanTask = {
        id: "fix",
        title: "Address review findings",
        role: "coder",
        description:
          "Fix the issues raised by the reviewer below, then verify with tests/build.\n\n" +
          review,
        acceptance: "All reviewer findings resolved and verified.",
      };
      const fixSummary = await this.runTask(goal, fixTask, contextParts.join("\n"));
      contextParts.push(`COMPLETED [coder] remediation: ${fixSummary}`);
      summaries.push({ task: fixTask, summary: fixSummary });

      this.events.onPhase?.("Re-review");
      review = await this.runReview(goal, plan, contextParts.join("\n"));
      approved = isApproved(review);
      this.events.onReview?.(review, approved);
    }

    return { plan, taskSummaries: summaries, review, approved };
  }

  private async runTask(goal: string, task: PlanTask, context: string): Promise<string> {
    const agent = new Agent({
      provider: this.provider,
      tools: AGENT_TOOLS,
      system: ROLE_SYSTEM[task.role],
      ctx: this.ctx,
      maxSteps: this.cfg.maxSteps,
      temperature: this.cfg.temperature,
      events: this.events,
    });
    const prompt = `Project goal: ${goal}

Shared context so far:
${context}

YOUR TASK (${task.role}) — ${task.title}
${task.description}

Acceptance criteria: ${task.acceptance}

Complete this task end to end using the tools. When done and verified, call
task_complete with a summary.`;
    const run = await agent.runTask(prompt);
    return (run.completion ?? run.text ?? "").trim() || "(no summary returned)";
  }

  private async runReview(goal: string, plan: Plan, context: string): Promise<string> {
    const agent = new Agent({
      provider: this.provider,
      tools: AGENT_TOOLS,
      system: ROLE_SYSTEM.reviewer,
      ctx: this.ctx,
      maxSteps: Math.min(this.cfg.maxSteps, 20),
      temperature: this.cfg.temperature,
      events: this.events,
    });
    const prompt = `Original goal: ${goal}

Plan overview: ${plan.overview}

Work completed:
${context}

Review the actual state of the workspace against the goal. Read the key changed
files and run the build/tests to verify. Then end your response with a final
line that is exactly one of:
  VERDICT: APPROVED
  VERDICT: CHANGES_NEEDED
If CHANGES_NEEDED, list the specific fixes required above that line. Call
task_complete with your review report and the verdict line.`;
    const run = await agent.runTask(prompt);
    return (run.completion ?? run.text ?? "").trim();
  }
}

function isApproved(review: string): boolean {
  return /VERDICT:\s*APPROVED/i.test(review) && !/VERDICT:\s*CHANGES_NEEDED/i.test(review);
}
