"use client";

import { useChat } from "@/hooks/useChat";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { ChatInput } from "@/components/chat/ChatInput";
import { AgentStatusBar } from "@/components/chat/AgentStatus";
import { ResearchPanel } from "@/components/chat/ResearchPanel";
import { useState } from "react";
import { PanelRightOpen, PanelRightClose } from "lucide-react";

export default function ChatPage() {
  const {
    messages,
    isLoading,
    agentStatus,
    streamingContent,
    sendMessage,
  } = useChat();
  const [showPanel, setShowPanel] = useState(false);

  return (
    <div className="flex h-full gap-4">
      <div className="flex flex-1 flex-col">
        {agentStatus && <AgentStatusBar status={agentStatus} />}
        <ChatWindow
          messages={messages}
          streamingContent={streamingContent}
          isLoading={isLoading}
        />
        <ChatInput onSend={sendMessage} isLoading={isLoading} />
      </div>

      <button
        onClick={() => setShowPanel(!showPanel)}
        className="hidden self-start rounded-lg border border-border p-2 text-muted-foreground hover:bg-accent lg:block"
        title="Toggle research panel"
      >
        {showPanel ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
      </button>

      {showPanel && (
        <ResearchPanel
          messages={messages}
          onClose={() => setShowPanel(false)}
        />
      )}
    </div>
  );
}
