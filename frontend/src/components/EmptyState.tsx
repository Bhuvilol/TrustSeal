import type { ReactNode } from 'react';

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
}

function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="panel flex flex-col items-start gap-3 p-6">
      <h3 className="text-lg font-semibold text-slate-100">{title}</h3>
      <p className="text-sm text-slate-300">{description}</p>
      {action ?? null}
    </div>
  );
}

export default EmptyState;
