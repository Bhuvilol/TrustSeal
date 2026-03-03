import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { sendAdminChat } from '@/api/chat';
import { useAuth } from '@/hooks/useAuth';
import { useShipment } from '@/hooks/useShipments';
import type { ChatResponse } from '@/types';
import { getErrorMessage } from '@/utils/errors';

type ChatRole = 'user' | 'assistant';

interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  meta?: {
    confidence: ChatResponse['confidence'];
    sources: string[];
  };
}

const QUICK_PROMPTS = [
  'Show all compromised shipments',
  'List shipments currently in transit',
  'Which shipments had temperature above 8 degrees?',
  'Were there any shock events yesterday?',
];

const CHAT_SESSION_KEY = 'trustseal_admin_chat_session_id';

function makeMessageId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function loadChatSessionId(): string | null {
  if (typeof window === 'undefined') return null;
  const value = window.localStorage.getItem(CHAT_SESSION_KEY);
  if (!value || value.trim().length === 0) return null;
  return value.trim();
}

function AdminChatWidget() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const location = useLocation();
  const shipmentIdFromRoute = useMemo(() => {
    const match = location.pathname.match(/^\/(?:shipments|shipment)\/([^/]+)/i);
    return match?.[1];
  }, [location.pathname]);
  const deviceIdFromRoute = useMemo(() => {
    const match = location.pathname.match(/^\/(?:devices|device)\/([^/]+)/i);
    return match?.[1];
  }, [location.pathname]);
  const { data: shipmentFromRoute } = useShipment(isAdmin ? shipmentIdFromRoute : undefined);

  const [isOpen, setIsOpen] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(() => loadChatSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'TrustSeal AI is ready. Ask about shipments, devices, sensor logs, or custody checkpoints.',
    },
  ]);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const quickPrompts = useMemo(() => QUICK_PROMPTS, []);
  const chatTenantId = useMemo(() => (user?.id ? `user:${user.id}` : undefined), [user?.id]);
  const chatDeviceId = useMemo(
    () => shipmentFromRoute?.device_id || deviceIdFromRoute || undefined,
    [shipmentFromRoute?.device_id, deviceIdFromRoute],
  );

  useEffect(() => {
    if (!isOpen) return;
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isOpen]);

  if (!isAdmin) {
    return null;
  }

  const submitQuestion = async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || isSending) return;

    setMessages((prev) => [
      ...prev,
      {
        id: makeMessageId(),
        role: 'user',
        content: trimmed,
      },
    ]);

    setInput('');
    setIsSending(true);

    try {
      const response = await sendAdminChat(trimmed, {
        tenantId: chatTenantId,
        deviceId: chatDeviceId,
        sessionId: sessionId ?? undefined,
        topK: 5,
      });
      if (response.session_id && response.session_id.trim().length > 0) {
        const nextSessionId = response.session_id.trim();
        setSessionId(nextSessionId);
        window.localStorage.setItem(CHAT_SESSION_KEY, nextSessionId);
      }
      setMessages((prev) => [
        ...prev,
        {
          id: makeMessageId(),
          role: 'assistant',
          content: response.answer,
          meta: {
            confidence: response.confidence,
            sources: Array.isArray(response.sources) ? response.sources : [],
          },
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: makeMessageId(),
          role: 'assistant',
          content: getErrorMessage(error, 'Chat request failed.'),
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await submitQuestion(input);
  };

  return (
    <div className="fixed bottom-4 right-4 z-40 w-[min(420px,calc(100vw-2rem))]">
      {!isOpen ? (
        <button
          type="button"
          className="btn-primary w-full shadow-panel"
          onClick={() => setIsOpen(true)}
        >
          Open TrustSeal AI
        </button>
      ) : (
        <section className="panel flex h-[75vh] max-h-[640px] flex-col overflow-hidden">
          <header className="flex items-center justify-between border-b border-slate-700/70 px-4 py-3">
            <div>
              <p className="text-xs uppercase tracking-[0.14em] text-brand-300">Admin Assistant</p>
              <h3 className="text-sm font-semibold text-slate-100">TrustSeal AI Chat</h3>
            </div>
            <button type="button" className="btn-secondary px-3 py-1.5 text-xs" onClick={() => setIsOpen(false)}>
              Close
            </button>
          </header>

          <div className="border-b border-slate-700/60 px-4 py-3">
            <p className="mb-2 text-xs text-slate-400">Quick prompts</p>
            <div className="flex flex-wrap gap-2">
              {quickPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="rounded-lg border border-slate-600 px-2 py-1 text-xs text-slate-200 hover:border-brand-400/60 hover:text-brand-300"
                  onClick={() => void submitQuestion(prompt)}
                  disabled={isSending}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {messages.map((message) => (
              <article
                key={message.id}
                className={
                  message.role === 'user'
                    ? 'ml-8 rounded-xl bg-brand-500/20 px-3 py-2 text-sm text-slate-100'
                    : 'mr-8 rounded-xl border border-slate-700 bg-surface-800/80 px-3 py-2 text-sm text-slate-100'
                }
              >
                <p>{message.content}</p>
                {message.role === 'assistant' && message.meta && (
                  <p className="mt-2 text-xs text-slate-400">
                    Confidence: {message.meta.confidence.toUpperCase()}
                    {message.meta.sources.length > 0 ? ` | Sources: ${message.meta.sources.length}` : ''}
                  </p>
                )}
              </article>
            ))}
            {isSending && (
              <article className="mr-8 rounded-xl border border-slate-700 bg-surface-800/80 px-3 py-2 text-sm text-slate-300">
                Thinking...
              </article>
            )}
            <div ref={bottomRef} />
          </div>

          <form onSubmit={handleSubmit} className="border-t border-slate-700/70 px-4 py-3">
            <div className="flex gap-2">
              <input
                type="text"
                className="input-field py-2"
                placeholder="Ask operational question..."
                value={input}
                onChange={(event) => setInput(event.target.value)}
                disabled={isSending}
              />
              <button type="submit" className="btn-primary px-4" disabled={isSending || input.trim().length === 0}>
                Send
              </button>
            </div>
          </form>
        </section>
      )}
    </div>
  );
}

export default AdminChatWidget;
