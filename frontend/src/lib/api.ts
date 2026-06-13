import { ChatMessage } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface MonitoringOverview {
  agent_stats: Record<string, { total_calls: number; total_tokens: number; avg_latency_ms: number }>;
  recent_activity: Array<{
    agent: string;
    status: string;
    message: string;
    tokens: number;
    latency_ms: number;
    created_at: string;
  }>;
  system: {
    companies_ingested: number;
    strategies_generated: number;
    total_tokens_used: number;
    total_agent_calls: number;
  };
}

export interface TradingAccount {
  cash: number;
  buying_power: number;
  equity: number;
  initial_balance: number;
  circuit_breaker_tripped: boolean;
  is_live: boolean;
  trading_mode: string;
  trading_dry_run: boolean;
  trading_auto_execute: boolean;
}

export interface TradingPosition {
  ticker: string;
  qty: number;
  avg_entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

export interface TradingOrder {
  id: string;
  ticker: string;
  side: string;
  qty: number;
  order_type: string;
  limit_price: number | null;
  status: string;
  filled_qty: number | null;
  avg_fill_price: number | null;
  agent_rationale: string | null;
  created_at: string;
}

export interface MarketCandle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// Chat
export const chatApi = {
  createSession: (title?: string) =>
    request<{ session_id: string; title: string }>("/api/chat/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  listSessions: () =>
    request<{ sessions: Array<{ id: string; title: string; created_at: string }> }>("/api/chat/sessions"),
  getMessages: (sessionId: string) =>
    request<{ messages: ChatMessage[] }>(`/api/chat/sessions/${sessionId}/messages`),
  sendMessage: (message: string, sessionId?: string) =>
    request<{
      session_id: string;
      response: string;
      agents_used: string[];
      context_sources: Array<Record<string, unknown>>;
    }>("/api/chat/send", {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId }),
    }),
};

// Research
export const researchApi = {
  run: (ticker: string, sector?: string, depth?: string) =>
    request<Record<string, unknown>>("/api/research/run", {
      method: "POST",
      body: JSON.stringify({ ticker, sector, depth }),
    }),
  compare: (tickers: string[]) =>
    request<Record<string, unknown>>("/api/research/compare", {
      method: "POST",
      body: JSON.stringify({ tickers }),
    }),
  getSummary: (ticker: string) =>
    request<Record<string, unknown>>(`/api/research/summary/${ticker}`),
};

// Companies
export const companiesApi = {
  list: (sector?: string, limit = 50) => {
    const params = new URLSearchParams();
    if (sector) params.set("sector", sector);
    params.set("limit", String(limit));
    return request<{ companies: Array<Record<string, unknown>> }>(`/api/companies/?${params}`);
  },
  get: (ticker: string) =>
    request<Record<string, unknown>>(`/api/companies/${ticker}`),
};

// Strategies
export const strategiesApi = {
  list: (sector?: string) => {
    const params = new URLSearchParams();
    if (sector) params.set("sector", sector);
    return request<{ strategies: Array<Record<string, unknown>> }>(`/api/strategies/?${params}`);
  },
  get: (id: string) =>
    request<Record<string, unknown>>(`/api/strategies/${id}`),
};

// Ingestion
export const ingestionApi = {
  ingestTicker: (ticker: string, sources?: string[]) =>
    request<{ status: string; ticker: string; name: string; sector: string | null }>(
      "/api/ingestion/ticker",
      {
        method: "POST",
        body: JSON.stringify({ ticker, sources }),
      }
    ),
  ingestBulk: (tickers: string[]) =>
    request<{ status: string }>("/api/ingestion/bulk", {
      method: "POST",
      body: JSON.stringify({ tickers }),
    }),
};

// Monitoring
export const monitoringApi = {
  getOverview: () => request<MonitoringOverview>("/api/monitoring/overview"),
};

// Market
export const marketApi = {
  getCandles: (ticker: string, period = "5d", interval = "15m", limit = 120) => {
    const params = new URLSearchParams({ period, interval, limit: String(limit) });
    return request<{
      ticker: string;
      period: string;
      interval: string;
      source: string;
      candles: MarketCandle[];
    }>(`/api/market/candles/${ticker}?${params}`);
  },
};

// Agents (frontend stub — routes through chat with @<tag> prefix; replace with dedicated endpoint later)
export const agentsApi = {
  sendToAgent: (agentTag: string, message: string, sessionId?: string) =>
    chatApi.sendMessage(`@${agentTag} ${message}`, sessionId),
};

// Command (orchestrator entry point)
export interface CommandJob {
  job_id: string;
  status:
    | "queued"
    | "running"
    | "researching"
    | "building_data"
    | "modeling"
    | "backtesting"
    | "risk_review"
    | "ready_for_paper"
    | "paper_trading"
    | "completed"
    | "rejected"
    | "failed";
  command?: string;
  strategy_id?: string;
  strategy_name?: string;
  metrics?: { sharpe: number; max_drawdown: number; annualized_return: number };
  risk_status?: string;
  error?: string;
}

export interface AgentEvent {
  id: string;
  job_id: string | null;
  agent: string;
  status: string;
  message: string;
  latency_ms: number;
  created_at: string;
}

export const commandApi = {
  submit: (command: string) =>
    request<{ job_id: string; status: string }>("/api/command", {
      method: "POST",
      body: JSON.stringify({ command }),
    }),
  status: (jobId: string) => request<CommandJob>(`/api/command/${jobId}`),
  events: (limit = 30, jobId?: string) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (jobId) params.set("job_id", jobId);
    return request<{ events: AgentEvent[] }>(`/api/agent-events?${params}`);
  },
};

// Trading
export const tradingApi = {
  getAccount: () => request<TradingAccount>("/api/trading/account"),
  getPositions: () =>
    request<{ positions: TradingPosition[] }>("/api/trading/positions"),
  getOrders: (limit = 50) =>
    request<{ orders: TradingOrder[] }>(`/api/trading/orders?limit=${limit}`),
  placeOrder: (ticker: string, side: string, qty: number, orderType = "MARKET", limitPrice?: number) =>
    request<{
      order_id: string;
      broker_order_id: string;
      status: string;
      filled_qty: number | null;
      avg_fill_price: number | null;
      error?: string;
    }>("/api/trading/orders", {
      method: "POST",
      body: JSON.stringify({ ticker, side, qty, order_type: orderType, limit_price: limitPrice }),
    }),
  toggleAuto: (enabled: boolean) =>
    request<{ status: string; trading_auto_execute: boolean }>(`/api/trading/toggle-auto?enabled=${enabled}`, {
      method: "POST",
    }),
  toggleDryRun: (enabled: boolean) =>
    request<{ status: string; trading_dry_run: boolean }>(`/api/trading/toggle-dry-run?enabled=${enabled}`, {
      method: "POST",
    }),
  triggerKillSwitch: () =>
    request<{ status: string; message: string }>("/api/trading/kill-switch", {
      method: "POST",
    }),
  resetCircuitBreaker: () =>
    request<{ status: string; message: string }>("/api/trading/reset-circuit-breaker", {
      method: "POST",
    }),
};
