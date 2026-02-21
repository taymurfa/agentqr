import { ChatMessage } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
    request<{ session_id: string; response: string; agents_used: string[] }>("/api/chat/send", {
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
  getOverview: () =>
    request<{
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
    }>("/api/monitoring/overview"),
};
