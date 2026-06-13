// Shared agent definitions — single source of truth for the UI.
// `id` matches the backend `agent_name` used in logs and the orchestrator's
// agent_map (see backend/src/agents/orchestrator.py). Display labels here are
// what the UI renders; keep them aligned with the real backend agent set.

export interface AgentDef {
  /** Backend agent identifier (matches AgentLog.agent_name / orchestrator agent_map). */
  id: string;
  /** Display name shown in the UI. */
  label: string;
  /** Short uppercase tag used in compact feeds (discourse, chat badges). */
  tag: string;
  /** One-line description of the agent's role. */
  description: string;
  /** Whether the agent is invoked directly by chat/research routes. */
  runnable: boolean;
}

export const AGENTS: AgentDef[] = [
  {
    id: "orchestrator",
    label: "Orchestrator",
    tag: "ORCH",
    description: "Routes queries to specialist agents and synthesizes results",
    runnable: true,
  },
  {
    id: "sector_researcher",
    label: "Sector Research Agent",
    tag: "SECTOR",
    description: "Analyzes sector trends and peer positioning",
    runnable: true,
  },
  {
    id: "fundamental_analyst",
    label: "Fundamental Analysis Agent",
    tag: "FUND",
    description: "Evaluates valuation, ratios, and financial health",
    runnable: true,
  },
  {
    id: "technical_analyst",
    label: "Technical Analysis Agent",
    tag: "TECH",
    description: "Reads price action, indicators, and momentum",
    runnable: true,
  },
  {
    id: "trading_agent",
    label: "Trading Agent",
    tag: "TRADER",
    description: "Sizes positions and executes orders",
    runnable: true,
  },
];

const byId = new Map(AGENTS.map((a) => [a.id, a]));

/** Resolve a display label from a backend agent_name (falls back to a titled id). */
export function agentLabel(id: string): string {
  return (
    byId.get(id)?.label ??
    id
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  );
}

/** Resolve a compact tag from a backend agent_name. */
export function agentTag(id: string): string {
  return byId.get(id)?.tag ?? id.split("_")[0].toUpperCase();
}
