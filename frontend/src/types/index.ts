export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  agents_used?: string[];
  context_sources?: ContextSource[];
  created_at: string;
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string | null;
}

export interface ContextSource {
  type: string;
  ticker?: string;
  date?: string;
  section?: string;
  score?: number;
}

export interface Company {
  id: string;
  ticker: string;
  name: string;
  sector: string;
  industry?: string;
  market_cap: number | null;
  description?: string;
  research_summary?: string;
  fundamentals?: Record<string, number | null>;
  last_updated: string | null;
}

export interface Strategy {
  id: string;
  name: string;
  sector: string;
  tickers: string[];
  recommendation: string;
  rationale?: string;
  confidence: number | null;
  risk_assessment?: string;
  sharpe_ratio: number | null;
  max_drawdown?: number | null;
  backtest_results?: Record<string, unknown>;
  created_at: string;
}

export interface AgentStatus {
  agent: string;
  status: "thinking" | "working" | "completed" | "error";
}

export interface WSMessage {
  type: "token" | "agent_status" | "context" | "done" | "status";
  content?: string;
  agent?: string;
  status?: string;
  sources?: ContextSource[];
}

export interface TechnicalSignal {
  ticker: string;
  signal: string;
  confidence: number;
  trend_strength: string;
  bullish_signals: number;
  bearish_signals: number;
  indicators: Record<string, number | null>;
}

export interface ResearchResult {
  ticker: string;
  sector: string;
  synthesis: string;
  agents_used: string[];
}
