interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="panel flex flex-col items-start gap-4 p-6 text-sm text-slate-200">
      <p className="rounded-lg border border-status-red/40 bg-status-red/15 px-3 py-2 text-status-red">
        {message}
      </p>
      {onRetry && (
        <button type="button" className="btn-secondary" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export default ErrorState;

