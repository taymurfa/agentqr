"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Hash, Send, AtSign } from "lucide-react";
import { AGENTS, agentLabel, agentTag } from "@/lib/agents";
import { agentsApi, monitoringApi, type MonitoringOverview } from "@/lib/api";

type ChannelId =
  | "ch:all-activity"
  | "ch:trades"
  | "ch:research"
  | `dm:${string}`;

type ChannelDef = {
  id: ChannelId;
  kind: "channel" | "dm";
  label: string;
  hint: string;
};

const CHANNELS: ChannelDef[] = [
  { id: "ch:all-activity", kind: "channel", label: "all-activity", hint: "Every agent log message" },
  { id: "ch:trades", kind: "channel", label: "trades", hint: "Trading agent activity" },
  { id: "ch:research", kind: "channel", label: "research", hint: "Sector / Fundamental / Technical" },
];

const DM_CHANNELS: ChannelDef[] = AGENTS.map((a) => ({
  id: `dm:${a.id}` as ChannelId,
  kind: "dm",
  label: a.label,
  hint: a.description,
}));

type LocalMessage = {
  id: string;
  role: "user" | "agent";
  agent?: string;
  content: string;
  time: string;
};

function matchesChannel(
  channel: ChannelDef,
  entry: { agent: string; message: string; status: string }
) {
  if (channel.kind === "dm") {
    return `dm:${entry.agent}` === channel.id;
  }
  switch (channel.id) {
    case "ch:all-activity":
      return true;
    case "ch:trades":
      return (
        entry.agent === "trading_agent" ||
        /order|fill|position|trade/i.test(entry.message)
      );
    case "ch:research":
      return ["sector_researcher", "fundamental_analyst", "technical_analyst"].includes(entry.agent);
    default:
      return false;
  }
}

export default function AgentsPage() {
  const [selectedId, setSelectedId] = useState<ChannelId>("ch:all-activity");
  const [overview, setOverview] = useState<MonitoringOverview | null>(null);
  const [localByChannel, setLocalByChannel] = useState<Record<string, LocalMessage[]>>({});
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const selected =
    [...CHANNELS, ...DM_CHANNELS].find((c) => c.id === selectedId) ?? CHANNELS[0];

  useEffect(() => {
    let cancelled = false;
    const refresh = () => {
      monitoringApi
        .getOverview()
        .then((data) => {
          if (!cancelled) setOverview(data);
        })
        .catch(() => {});
    };
    refresh();
    const t = window.setInterval(refresh, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, []);

  const messages = useMemo<LocalMessage[]>(() => {
    const fromFeed: LocalMessage[] = (overview?.recent_activity ?? [])
      .filter((entry) => matchesChannel(selected, entry))
      .map((entry, i) => ({
        id: `feed-${i}-${entry.created_at}`,
        role: "agent",
        agent: entry.agent,
        content: entry.message,
        time: entry.created_at,
      }));
    const local = localByChannel[selected.id] ?? [];
    return [...fromFeed.reverse(), ...local];
  }, [overview, selected, localByChannel]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages.length]);

  const onSend = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setSending(true);
    const id = `local-${Date.now()}`;
    const now = new Date().toISOString();
    setLocalByChannel((prev) => ({
      ...prev,
      [selected.id]: [
        ...(prev[selected.id] ?? []),
        { id, role: "user", content: text, time: now },
      ],
    }));
    setInput("");
    try {
      const tag =
        selected.kind === "dm"
          ? agentTag(selected.id.replace(/^dm:/, ""))
          : "ORCH";
      const res = await agentsApi.sendToAgent(tag, text);
      setLocalByChannel((prev) => ({
        ...prev,
        [selected.id]: [
          ...(prev[selected.id] ?? []),
          {
            id: `${id}-reply`,
            role: "agent",
            agent: selected.kind === "dm" ? selected.id.replace(/^dm:/, "") : "orchestrator",
            content: res.response,
            time: new Date().toISOString(),
          },
        ],
      }));
    } catch (e) {
      setLocalByChannel((prev) => ({
        ...prev,
        [selected.id]: [
          ...(prev[selected.id] ?? []),
          {
            id: `${id}-err`,
            role: "agent",
            agent: "orchestrator",
            content: "(failed to deliver — backend chat endpoint unreachable)",
            time: new Date().toISOString(),
          },
        ],
      }));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="grid h-full w-full grid-cols-[240px_minmax(0,1fr)] overflow-hidden bg-background">
      {/* Sidebar */}
      <aside className="flex min-w-0 flex-col overflow-y-auto border-r border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <p className="font-mono text-sm font-semibold text-foreground">AgentQR</p>
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground">workspace</p>
        </div>

        <div className="px-3 py-3">
          <p className="px-1 pb-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Channels
          </p>
          {CHANNELS.map((c) => (
            <ChannelButton
              key={c.id}
              channel={c}
              active={c.id === selectedId}
              onClick={() => setSelectedId(c.id)}
            />
          ))}
        </div>

        <div className="px-3 py-3">
          <p className="px-1 pb-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Direct Messages
          </p>
          {DM_CHANNELS.map((c) => (
            <ChannelButton
              key={c.id}
              channel={c}
              active={c.id === selectedId}
              onClick={() => setSelectedId(c.id)}
            />
          ))}
        </div>
      </aside>

      {/* Main */}
      <main className="flex min-w-0 flex-col overflow-hidden">
        <header className="flex shrink-0 items-center gap-2 border-b border-border px-5 py-3">
          {selected.kind === "channel" ? (
            <Hash className="h-4 w-4 text-muted-foreground" />
          ) : (
            <AtSign className="h-4 w-4 text-muted-foreground" />
          )}
          <h1 className="font-mono text-sm font-semibold text-foreground">{selected.label}</h1>
          <span className="ml-3 text-[10px] uppercase tracking-widest text-muted-foreground">
            {selected.hint}
          </span>
        </header>

        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {messages.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No messages yet. {selected.kind === "dm" ? `Ask ${agentLabel(selected.id.replace(/^dm:/, ""))} something.` : "Agents will speak here as they work."}
            </p>
          )}
          <div className="space-y-4">
            {messages.map((m) => (
              <MessageRow key={m.id} message={m} />
            ))}
          </div>
        </div>

        <div className="shrink-0 border-t border-border p-3">
          <div className="flex items-end gap-2 rounded-md border border-border bg-card p-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onSend();
                }
              }}
              placeholder={
                selected.kind === "dm"
                  ? `Message ${agentLabel(selected.id.replace(/^dm:/, ""))}…`
                  : `Message #${selected.label}…`
              }
              rows={1}
              className="max-h-32 min-h-[36px] flex-1 resize-none bg-transparent px-2 py-1 font-mono text-xs text-foreground outline-none placeholder:text-muted-foreground"
              disabled={sending}
            />
            <button
              onClick={onSend}
              disabled={sending || !input.trim()}
              className="rounded bg-primary p-2 text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-40"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

function ChannelButton({
  channel,
  active,
  onClick,
}: {
  channel: ChannelDef;
  active: boolean;
  onClick: () => void;
}) {
  const Icon = channel.kind === "channel" ? Hash : AtSign;
  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left font-mono text-xs transition-colors ${
        active ? "bg-accent/60 text-foreground" : "text-muted-foreground hover:bg-accent/30 hover:text-foreground"
      }`}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" />
      <span className="truncate">{channel.label}</span>
    </button>
  );
}

function MessageRow({ message }: { message: LocalMessage }) {
  const isUser = message.role === "user";
  const name = isUser ? "you" : message.agent ? agentLabel(message.agent) : "agent";
  const tag = isUser ? "YOU" : message.agent ? agentTag(message.agent) : "AGT";
  const time = message.time ? new Date(message.time).toLocaleTimeString() : "";

  return (
    <div className="flex gap-3">
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-mono text-[10px] font-semibold ${
          isUser ? "border border-border bg-background text-foreground" : "bg-accent text-foreground"
        }`}
      >
        {tag.slice(0, 4)}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2 font-mono text-[11px]">
          <span className="font-semibold text-foreground">{name}</span>
          <span className="text-muted-foreground">{time}</span>
        </div>
        <p className="mt-0.5 whitespace-pre-wrap font-mono text-xs text-foreground">{message.content}</p>
      </div>
    </div>
  );
}
