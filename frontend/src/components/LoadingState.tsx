interface LoadingStateProps {
  message?: string;
  fullscreen?: boolean;
}

function LoadingState({ message = 'Loading data...', fullscreen = false }: LoadingStateProps) {
  return (
    <div
      className={`flex items-center justify-center ${
        fullscreen ? 'min-h-screen' : 'min-h-[200px]'
      }`}
    >
      <div className="panel-soft flex items-center gap-3 px-5 py-4 text-sm text-slate-200">
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-brand-400 border-t-transparent" />
        {message}
      </div>
    </div>
  );
}

export default LoadingState;

