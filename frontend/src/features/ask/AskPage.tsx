import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChatMessageRecord,
  getChatThread,
  sendChatMessage,
} from "../../shared/api/httpClient";

function getStoredChatThreadId(userId: string) {
  return window.localStorage.getItem(`northstar_chat_thread_${userId}`);
}

function setStoredChatThreadId(userId: string, threadId: string) {
  window.localStorage.setItem(`northstar_chat_thread_${userId}`, threadId);
}

function clearStoredChatThreadId(userId: string) {
  window.localStorage.removeItem(`northstar_chat_thread_${userId}`);
}

interface AskPageProps {
  userId: string;
}

export function AskPage({ userId }: AskPageProps) {
  const [messages, setMessages] = useState<ChatMessageRecord[]>([]);
  const [input, setInput] = useState("");
  const [threadId, setThreadId] = useState<string | null>(() =>
    getStoredChatThreadId(userId),
  );
  const [summary, setSummary] = useState<string | null>(null);
  const [intent, setIntent] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const storedThreadId = getStoredChatThreadId(userId);
    setThreadId(storedThreadId);
    if (!storedThreadId) {
      setMessages([]);
      setSummary(null);
      setIntent(null);
      return;
    }

    let cancelled = false;
    const loadThread = async () => {
      try {
        const thread = await getChatThread(storedThreadId);
        if (cancelled) {
          return;
        }
        setMessages(thread.messages || []);
        setSummary(thread.summary || null);
        setIntent(null);
      } catch {
        if (!cancelled) {
          clearStoredChatThreadId(userId);
          setThreadId(null);
          setMessages([]);
          setSummary(null);
        }
      }
    };

    void loadThread();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  useEffect(() => {
    const container = listRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages, sending]);

  const handleNewChat = useCallback(() => {
    clearStoredChatThreadId(userId);
    setThreadId(null);
    setMessages([]);
    setSummary(null);
    setIntent(null);
    setError(null);
    setInput("");
  }, [userId]);

  const handleSend = useCallback(async () => {
    const content = input.trim();
    if (!content || sending) {
      return;
    }

    setSending(true);
    setError(null);
    setInput("");

    const optimisticUserMessage: ChatMessageRecord = {
      message_id: `local-${Date.now()}`,
      thread_id: threadId || "local",
      user_id: userId,
      role: "user",
      content,
      metadata: {},
      created_at: new Date().toISOString(),
    };

    setMessages((current) => [...current, optimisticUserMessage]);

    try {
      const response = await sendChatMessage({
        message: content,
        thread_id: threadId,
      });

      const nextThreadId = response.thread.thread_id;
      setThreadId(nextThreadId);
      setStoredChatThreadId(userId, nextThreadId);
      setSummary(response.thread.summary || null);
      setIntent(response.intent.kind);
      setMessages(
        response.thread.messages.length > 0
          ? response.thread.messages
          : [response.user_message, response.assistant_message],
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message.");
      setMessages((current) =>
        current.filter(
          (message) => message.message_id !== optimisticUserMessage.message_id,
        ),
      );
    } finally {
      setSending(false);
    }
  }, [input, sending, threadId, userId]);

  return (
    <main
      style={{
        flex: 1,
        display: "flex",
        justifyContent: "center",
        padding: 20,
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 900,
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <div style={{ fontSize: 12, color: "#666" }}>
          {intent ? `Intent: ${intent}` : "Ask across everything you've captured"}
        </div>

        {summary ? (
            <div
              style={{
                padding: 12,
                borderRadius: 12,
                background: "#fff",
                border: "1px solid #e5e0d8",
              }}
            >
              <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>
                Conversation summary
              </div>
              <div style={{ whiteSpace: "pre-wrap" }}>{summary}</div>
            </div>
          ) : null}

          <div
            ref={listRef}
            style={{
              flex: 1,
              minHeight: 420,
              maxHeight: "calc(100vh - 250px)",
              overflowY: "auto",
              padding: 12,
              borderRadius: 16,
              background: "#fff",
              border: "1px solid #e5e0d8",
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            {messages.length === 0 ? (
              <div style={{ color: "#777", padding: 12 }}>
                Ask about your notes, tasks, decisions, or anything you want
                retrieved from memory.
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.message_id}
                  style={{
                    display: "flex",
                    justifyContent:
                      message.role === "user" ? "flex-end" : "flex-start",
                  }}
                >
                  <div
                    style={{
                      maxWidth: "80%",
                      padding: "12px 14px",
                      borderRadius: 16,
                      whiteSpace: "pre-wrap",
                      background: message.role === "user" ? "#111" : "#f0ebe3",
                      color: message.role === "user" ? "#fff" : "#111",
                    }}
                  >
                    {message.content}
                  </div>
                </div>
              ))
            )}
            {sending ? <div style={{ color: "#777" }}>Thinking...</div> : null}
          </div>

          {error ? <div style={{ color: "#b00020" }}>{error}</div> : null}

          <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void handleSend();
                }
              }}
              placeholder="Message NorthStar..."
              rows={3}
              style={{
                flex: 1,
                resize: "none",
                padding: 12,
                borderRadius: 14,
                border: "1px solid #cfc7bc",
                fontFamily: "inherit",
              }}
              disabled={sending}
            />
            <button
              onClick={() => void handleSend()}
              disabled={sending || !input.trim()}
            >
              Send
            </button>
            <button onClick={handleNewChat}>New chat</button>
          </div>
      </div>
    </main>
  );
}
