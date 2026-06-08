import type { Provider } from "../llm/types.js";
import { userText } from "../llm/types.js";
import { ROLE_SYSTEM, type RoleName } from "./roles.js";

export interface PlanTask {
  id: string;
  title: string;
  role: RoleName;
  description: string;
  acceptance: string;
}

export interface Plan {
  overview: string;
  architecture: string;
  tasks: PlanTask[];
}

const VALID_ROLES: RoleName[] = ["architect", "coder", "tester", "devops"];

const PLAN_PROMPT = (goal: string) => `Goal from the user:
"""
${goal}
"""

Produce an execution plan as STRICT JSON (no markdown fences, no prose outside
the JSON). Shape:

{
  "overview": "1-3 sentence restatement of what we're building",
  "architecture": "short description of structure, key files/modules, tech choices",
  "tasks": [
    {
      "id": "t1",
      "title": "short title",
      "role": "architect | coder | tester | devops",
      "description": "what to do, concretely",
      "acceptance": "how we'll know it's done"
    }
  ]
}

Rules:
- Order tasks so each can build on the previous (architect first if scaffolding
  is needed, then coders, then tester, then devops).
- Keep it to the smallest number of tasks that actually delivers the goal
  (typically 3-7). Do not over-engineer.
- Only use the four roles listed. Output JSON only.`;

export async function planProject(provider: Provider, goal: string): Promise<Plan> {
  const result = await provider.complete({
    system: ROLE_SYSTEM.pm,
    messages: [userText(PLAN_PROMPT(goal))],
    maxTokens: 4096,
    temperature: 0.2,
  });
  const plan = parsePlan(result.text);
  if (!plan) {
    // Fallback: a single coder task so the run still proceeds.
    return {
      overview: goal,
      architecture: "(planner did not return structured output; proceeding with a single task)",
      tasks: [
        {
          id: "t1",
          title: "Implement the goal",
          role: "coder",
          description: goal,
          acceptance: "The goal is met and verified.",
        },
      ],
    };
  }
  return plan;
}

export function parsePlan(text: string): Plan | null {
  const json = extractJson(text);
  if (!json) return null;
  let raw: unknown;
  try {
    raw = JSON.parse(json);
  } catch {
    return null;
  }
  if (typeof raw !== "object" || raw === null) return null;
  const obj = raw as Record<string, unknown>;
  const tasksRaw = Array.isArray(obj.tasks) ? obj.tasks : [];
  const tasks: PlanTask[] = [];
  tasksRaw.forEach((t, i) => {
    if (typeof t !== "object" || t === null) return;
    const to = t as Record<string, unknown>;
    const role = normalizeRole(to.role);
    tasks.push({
      id: typeof to.id === "string" ? to.id : `t${i + 1}`,
      title: typeof to.title === "string" ? to.title : `Task ${i + 1}`,
      role,
      description: typeof to.description === "string" ? to.description : "",
      acceptance: typeof to.acceptance === "string" ? to.acceptance : "",
    });
  });
  if (tasks.length === 0) return null;
  return {
    overview: typeof obj.overview === "string" ? obj.overview : "",
    architecture: typeof obj.architecture === "string" ? obj.architecture : "",
    tasks,
  };
}

function normalizeRole(v: unknown): RoleName {
  if (typeof v === "string") {
    const lower = v.toLowerCase();
    const match = VALID_ROLES.find((r) => lower.includes(r));
    if (match) return match;
  }
  return "coder";
}

/** Extract the first balanced JSON object from a possibly-noisy LLM response. */
export function extractJson(text: string): string | null {
  const start = text.indexOf("{");
  if (start < 0) return null;
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = start; i < text.length; i++) {
    const c = text[i];
    if (inStr) {
      if (esc) esc = false;
      else if (c === "\\") esc = true;
      else if (c === '"') inStr = false;
    } else {
      if (c === '"') inStr = true;
      else if (c === "{") depth++;
      else if (c === "}") {
        depth--;
        if (depth === 0) return text.slice(start, i + 1);
      }
    }
  }
  return null;
}
