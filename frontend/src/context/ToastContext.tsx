import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from 'react';
import { AnimatePresence, motion } from 'framer-motion';

type ToastKind = 'success' | 'error' | 'info';

interface ToastMessage {
  id: string;
  message: string;
  kind: ToastKind;
}

interface ToastContextValue {
  showToast: (kind: ToastKind, message: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

function getToastClasses(kind: ToastKind): string {
  if (kind === 'success') {
    return 'border-status-green/45 bg-status-green/15 text-status-green';
  }
  if (kind === 'error') {
    return 'border-status-red/45 bg-status-red/15 text-status-red';
  }
  return 'border-status-blue/45 bg-status-blue/15 text-status-blue';
}

export function ToastProvider({ children }: PropsWithChildren) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const timeoutHandles = useRef<number[]>([]);

  const removeToast = useCallback((toastId: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== toastId));
  }, []);

  const showToast = useCallback(
    (kind: ToastKind, message: string) => {
      if (!message.trim()) {
        return;
      }

      const toastId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      setToasts((prev) => [...prev, { id: toastId, message, kind }]);

      const handle = window.setTimeout(() => {
        removeToast(toastId);
      }, 5000);
      timeoutHandles.current.push(handle);
    },
    [removeToast],
  );

  useEffect(() => {
    const handleForbidden = (event: Event) => {
      if (!(event instanceof CustomEvent)) {
        showToast('error', 'Insufficient permissions for this operation.');
        return;
      }

      const message = typeof event.detail === 'string' ? event.detail : undefined;
      showToast('error', message || 'Insufficient permissions for this operation.');
    };

    window.addEventListener('trustseal:forbidden', handleForbidden);
    return () => {
      window.removeEventListener('trustseal:forbidden', handleForbidden);
    };
  }, [showToast]);

  useEffect(
    () => () => {
      timeoutHandles.current.forEach((timeoutId) => window.clearTimeout(timeoutId));
      timeoutHandles.current = [];
    },
    [],
  );

  const value = useMemo<ToastContextValue>(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-[60] flex w-[min(420px,calc(100vw-2rem))] flex-col gap-2">
        <AnimatePresence initial={false}>
          {toasts.map((toast) => (
            <motion.article
              key={toast.id}
              initial={{ opacity: 0, x: 40, scale: 0.96 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 40, scale: 0.98 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className={`pointer-events-auto rounded-xl border px-4 py-3 text-sm shadow-panel ${getToastClasses(toast.kind)}`}
              role="alert"
              aria-live="polite"
            >
              <div className="flex items-start gap-3">
                <p className="flex-1">{toast.message}</p>
                <button
                  type="button"
                  className="text-xs font-semibold uppercase tracking-wide opacity-85 hover:opacity-100"
                  onClick={() => removeToast(toast.id)}
                >
                  Close
                </button>
              </div>
            </motion.article>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export default ToastContext;
