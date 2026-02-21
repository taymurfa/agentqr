import { WSMessage } from "@/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export class ChatWebSocket {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private onMessage: (msg: WSMessage) => void;
  private onClose: () => void;
  private reconnectAttempts = 0;
  private maxReconnects = 5;

  constructor(
    sessionId: string,
    onMessage: (msg: WSMessage) => void,
    onClose: () => void = () => {}
  ) {
    this.sessionId = sessionId;
    this.onMessage = onMessage;
    this.onClose = onClose;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(`${WS_URL}/api/chat/ws/${this.sessionId}`);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WSMessage;
          this.onMessage(data);
        } catch {
          console.error("Failed to parse WebSocket message");
        }
      };

      this.ws.onclose = () => {
        this.onClose();
        if (this.reconnectAttempts < this.maxReconnects) {
          this.reconnectAttempts++;
          setTimeout(() => this.connect(), 1000 * this.reconnectAttempts);
        }
      };

      this.ws.onerror = (error) => {
        reject(error);
      };
    });
  }

  send(message: string) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ content: message }));
    }
  }

  disconnect() {
    this.maxReconnects = 0;
    this.ws?.close();
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
