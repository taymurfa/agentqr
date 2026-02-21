"use client";

import { useState, useCallback, useRef } from "react";
import { ChatMessage, AgentStatus, WSMessage } from "@/types";
import { chatApi } from "@/lib/api";
import { ChatWebSocket } from "@/lib/websocket";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const wsRef = useRef<ChatWebSocket | null>(null);

  const initSession = useCallback(async (title?: string) => {
    const res = await chatApi.createSession(title);
    setSessionId(res.session_id);
    return res.session_id;
  }, []);

  const loadSession = useCallback(async (id: string) => {
    setSessionId(id);
    const res = await chatApi.getMessages(id);
    setMessages(res.messages);
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim()) return;

      let currentSessionId = sessionId;
      if (!currentSessionId) {
        currentSessionId = await initSession();
      }

      const userMessage: ChatMessage = {
        id: `temp-${Date.now()}`,
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      setStreamingContent("");

      try {
        const res = await chatApi.sendMessage(content, currentSessionId!);
        const assistantMessage: ChatMessage = {
          id: `resp-${Date.now()}`,
          role: "assistant",
          content: res.response,
          agents_used: res.agents_used,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } catch (error) {
        const errorMessage: ChatMessage = {
          id: `err-${Date.now()}`,
          role: "assistant",
          content: "Sorry, there was an error processing your request. Please try again.",
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      } finally {
        setIsLoading(false);
        setAgentStatus(null);
      }
    },
    [sessionId, initSession]
  );

  const sendMessageStreaming = useCallback(
    async (content: string) => {
      if (!content.trim()) return;

      let currentSessionId = sessionId;
      if (!currentSessionId) {
        currentSessionId = await initSession();
      }

      const userMessage: ChatMessage = {
        id: `temp-${Date.now()}`,
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      setStreamingContent("");

      const ws = new ChatWebSocket(
        currentSessionId!,
        (msg: WSMessage) => {
          if (msg.type === "token") {
            setStreamingContent((prev) => prev + (msg.content || ""));
          } else if (msg.type === "agent_status") {
            setAgentStatus({ agent: msg.agent || "", status: msg.status as AgentStatus["status"] });
          } else if (msg.type === "done") {
            setStreamingContent((prev) => {
              if (prev) {
                const assistantMessage: ChatMessage = {
                  id: `resp-${Date.now()}`,
                  role: "assistant",
                  content: prev,
                  created_at: new Date().toISOString(),
                };
                setMessages((msgs) => [...msgs, assistantMessage]);
              }
              return "";
            });
            setIsLoading(false);
            setAgentStatus(null);
          }
        },
        () => {
          setIsLoading(false);
        }
      );

      try {
        await ws.connect();
        ws.send(content);
        wsRef.current = ws;
      } catch {
        // Fall back to non-streaming
        await sendMessage(content);
      }
    },
    [sessionId, initSession, sendMessage]
  );

  const clearChat = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    setStreamingContent("");
    wsRef.current?.disconnect();
  }, []);

  return {
    messages,
    sessionId,
    isLoading,
    agentStatus,
    streamingContent,
    sendMessage,
    sendMessageStreaming,
    initSession,
    loadSession,
    clearChat,
  };
}
