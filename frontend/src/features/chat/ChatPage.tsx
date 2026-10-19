import { useCallback, useEffect, useRef, useState } from "react";
import { PaperPlaneTilt, Paperclip, Plus, Microphone, Spinner } from "@phosphor-icons/react";
import clsx from "clsx";
import {
  ChatMessageRecord,
  getChatThread,
  sendChatMessage,
} from "../../shared/api/httpClient";
import { useAuthorization } from "../../shared/auth/useAuthorization";
import { Button } from "../../shared/ui/Button";
import { LogoMark } from "../../shared/ui/Logo";
import { ChatEmptyState } from "./ChatEmptyState";

function threadStorageKey(userId: string) {
  return `northstar_chat_thread_${userId}`;
}

export function ChatPage() {
  const { userId } = useAuthorization();
  const [messages, setMessages] = useState<ChatMessageRecord[]>([]);
  const [input, setInput] = useState("");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!userId) {
      return;
    }
    const storedThreadId = window.localStorage.getItem(threadStorageKey(userId));
    if (!storedThreadId) {
      return;
    }
    setThreadId(storedThreadId);
    void (async () => {
      try {
        const thread = await getChatThread(storedThreadId);
        setMessages(thread.messages || []);
        setSummary(thread.summary || null);
      } catch {
        window.localStorage.removeItem(threadStorageKey(userId));
        setThreadId(null);
      }
    })();
  }, [userId]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  const handleNewChat = () => {
    if (userId) {
      window.localStorage.removeItem(threadStorageKey(userId));
    }
    setThreadId(null);
    setMessages([]);
    setSummary(null);
    setError(null);
    setInput("");
  };

  const handleSend = useCallback(async () => {
    const content = input.trim();
    if (!content || sending || !userId) {
      return;
    }
    setSending(true);
    setError(null);
    setInput("");

    const optimistic: ChatMessageRecord = {
      message_id: `local-${Date.now()}`,
      thread_id: threadId || "local",
      user_id: userId,
      role: "user",
      content,
      metadata: {},
      created_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, optimistic]);

    try {
      const response = await sendChatMessage({ message: content, thread_id: threadId });
      window.localStorage.setItem(threadStorageKey(userId), response.thread.thread_id);
      setThreadId(response.thread.thread_id);
      setSummary(response.thread.summary || null);
      setMessages(
        response.thread.messages.length > 0
          ? response.thread.messages
          : [response.user_message, response.assistant_message],
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message.");
      setMessages((current) => current.filter((m) => m.message_id !== optimistic.message_id));
    } finally {
      setSending(false);
    }
  }, [input, sending, threadId, userId]);

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-3xl flex-col lg:h-[calc(100vh-5rem)]">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-neutral-950">Chat</h1>
          <p className="mt-1 text-sm text-neutral-500">Ask anything grounded in your captured notes.</p>
        </div>
        <Button variant="outline" size="sm" onClick={handleNewChat}>
          <Plus size={16} />
          New chat
        </Button>
      </header>

      {summary ? (
        <div className="mb-4 rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3 text-xs text-neutral-500">
          <span className="font-semibold text-neutral-700">Thread summary: </span>
          {summary}
        </div>
      ) : null}

      <div
        ref={listRef}
        className="flex flex-1 flex-col space-y-4 overflow-y-auto rounded-2xl border border-neutral-200 bg-white p-5 shadow-card"
      >
        {messages.length === 0 ? (
          <ChatEmptyState onUseSuggestion={setInput} />
        ) : (
          messages.map((message) => (
            <div
              key={message.message_id}
              className={clsx("flex items-end gap-2", message.role === "user" ? "justify-end" : "justify-start")}
            >
              {message.role === "assistant" ? (
                <span className="mb-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-neutral-950 text-white">
                  <LogoMark size={14} className="text-white" />
                </span>
              ) : null}
              <div
                className={clsx(
                  "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                  message.role === "user"
                    ? "bg-neutral-950 text-white"
                    : "bg-neutral-100 text-neutral-800",
                )}
              >
                {message.content}
              </div>
            </div>
          ))
        )}
        {sending ? (
          <div className="flex items-end justify-start gap-2">
            <span className="mb-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-neutral-950 text-white">
              <LogoMark size={14} className="text-white" />
            </span>
            <div className="flex items-center gap-2 rounded-2xl bg-neutral-100 px-4 py-2.5 text-sm text-neutral-500">
              <Spinner size={14} className="animate-spin" /> Thinking…
            </div>
          </div>
        ) : null}
      </div>

      {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}

      <form
        className="mt-4 flex items-center gap-1.5 rounded-2xl border border-neutral-300 bg-white p-2 pl-4 shadow-card transition-colors focus-within:border-neutral-950"
        onSubmit={(e) => {
          e.preventDefault();
          void handleSend();
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask me anything…"
          className="h-10 flex-1 border-none bg-transparent text-sm text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:ring-0"
        />
        <button
          type="button"
          disabled
          title="Attach a file (coming soon)"
          aria-label="Attach a file (coming soon)"
          className="inline-flex h-10 w-10 shrink-0 cursor-not-allowed items-center justify-center rounded-xl text-neutral-300"
        >
          <Paperclip size={18} />
        </button>
        <button
          type="button"
          disabled
          title="Voice input coming soon"
          aria-label="Voice input (coming soon)"
          className="inline-flex h-10 w-10 shrink-0 cursor-not-allowed items-center justify-center rounded-xl text-neutral-300"
        >
          <Microphone size={18} />
        </button>
        <Button type="submit" disabled={sending || !input.trim()} className="h-10 w-10 shrink-0 !px-0">
          <PaperPlaneTilt size={18} weight="bold" />
        </Button>
      </form>
    </div>
  );
}
