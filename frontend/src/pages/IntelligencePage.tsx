import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { AlertTriangle, BrainCircuit } from 'lucide-react';
import EmptyState from '@/components/EmptyState';
import ErrorState from '@/components/ErrorState';
import LoadingState from '@/components/LoadingState';
import { getPipelineStatus, getWorkersStatus, reconcilePipeline, reprocessDeadLetter } from '@/api/ops';
import { useAuth } from '@/hooks/useAuth';
import { useShipments } from '@/hooks/useShipments';
import { useToast } from '@/hooks/useToast';
import { getErrorMessage } from '@/utils/errors';
import { hasPermission } from '@/utils/permissions';

function IntelligencePage() {
  const { user } = useAuth();
  const { showError, showInfo, showSuccess } = useToast();
  const canManageOperations = hasPermission(user?.role, 'manage_operations');
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const { data: shipments, isLoading: shipmentsLoading, isError: shipmentsError, error: shipmentsErrObj, refetch: refetchShipments } =
    useShipments();
  const {
    data: pipeline,
    isLoading: pipelineLoading,
    isError: pipelineError,
    error: pipelineErrObj,
    refetch: refetchPipeline,
  } = useQuery({
    queryKey: ['ops', 'pipeline-status'],
    queryFn: () => getPipelineStatus(),
    retry: 0,
    staleTime: 20_000,
    gcTime: 2 * 60_000,
  });
  const {
    data: workers,
    isLoading: workersLoading,
    refetch: refetchWorkers,
  } = useQuery({
    queryKey: ['ops', 'workers-status'],
    queryFn: () => getWorkersStatus(),
    enabled: canManageOperations,
    retry: 0,
    staleTime: 20_000,
    gcTime: 2 * 60_000,
  });

  const shipmentSummary = useMemo(() => {
    const source = shipments ?? [];
    return {
      total: source.length,
      inTransit: source.filter((s) => s.status === 'in_transit').length,
      completed: source.filter((s) => s.status === 'completed').length,
      compromised: source.filter((s) => s.status === 'compromised').length,
    };
  }, [shipments]);

  const batchStatusChartData = useMemo(
    () =>
      Object.entries(pipeline?.pipeline.batch_status_counts ?? {}).map(([status, count]) => ({
        status,
        count,
      })),
    [pipeline],
  );

  const streamChartData = useMemo(() => {
    const redis = pipeline?.redis;
    if (!redis || !redis.available) {
      return [];
    }
    return [
      { stream: 'telemetry', length: redis.telemetry_stream_len ?? 0 },
      { stream: 'custody', length: redis.custody_stream_len ?? 0 },
      { stream: 'bundle_ready', length: redis.bundle_ready_stream_len ?? 0 },
      { stream: 'anchor_request', length: redis.anchor_request_stream_len ?? 0 },
    ];
  }, [pipeline]);

  const workerRows = useMemo(
    () => Object.entries(workers?.workers ?? {}),
    [workers],
  );

  const handleOpsAction = async (action: 'reconcile' | 'dead-letter') => {
    setPendingAction(action);
    try {
      if (action === 'reconcile') {
        const result = await reconcilePipeline(undefined, true);
        showSuccess(`Reconciliation scanned ${result.scanned_batches} batches and repaired ${result.repaired_bundle_ids.length}.`);
      } else {
        const result = await reprocessDeadLetter(100, false);
        showInfo(`Dead-letter sweep scanned ${result.scanned} entries and requeued ${result.requeued}.`);
      }
      await refetchPipeline();
      await refetchWorkers();
    } catch (error) {
      showError(getErrorMessage(error, 'Operations action failed.'));
    } finally {
      setPendingAction(null);
    }
  };

  if (shipmentsLoading || pipelineLoading) {
    return <LoadingState message="Loading operational intelligence..." />;
  }

  if (shipmentsError || pipelineError) {
    return (
      <ErrorState
        message={getErrorMessage(pipelineError ? pipelineErrObj : shipmentsErrObj, 'Unable to load intelligence metrics.')}
        onRetry={() => {
          void refetchShipments();
          void refetchPipeline();
        }}
      />
    );
  }

  if (!shipments || shipments.length === 0) {
    return (
      <EmptyState
        title="No shipments for intelligence analysis"
        description="Create shipments to start monitoring live pipeline risk and proof metrics."
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-slate-100">Intelligence</h1>
            <p className="mt-1 text-sm text-slate-400">Real pipeline and proof health analytics from backend state.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {canManageOperations && (
              <>
                <button
                  type="button"
                  className="btn-secondary px-3 py-2 text-xs"
                  onClick={() => void handleOpsAction('reconcile')}
                  disabled={pendingAction !== null}
                >
                  {pendingAction === 'reconcile' ? 'Reconciling...' : 'Run Reconcile'}
                </button>
                <button
                  type="button"
                  className="btn-secondary px-3 py-2 text-xs"
                  onClick={() => void handleOpsAction('dead-letter')}
                  disabled={pendingAction !== null}
                >
                  {pendingAction === 'dead-letter' ? 'Reprocessing...' : 'Reprocess Dead Letter'}
                </button>
              </>
            )}
            <span className="inline-flex items-center gap-2 rounded-full border border-cyan-300/40 bg-cyan-400/15 px-3 py-1 text-xs font-semibold text-cyan-100">
              <BrainCircuit className="h-4 w-4" />
              Pipeline Intelligence
            </span>
          </div>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-2xl border border-cyan-300/35 bg-cyan-500/10 p-3">
            <p className="text-xs uppercase tracking-[0.14em] text-cyan-100/80">Total Shipments</p>
            <p className="mt-2 text-2xl font-semibold text-cyan-100">{shipmentSummary.total}</p>
          </article>
          <article className="rounded-2xl border border-amber-300/35 bg-amber-500/10 p-3">
            <p className="text-xs uppercase tracking-[0.14em] text-amber-100/80">In Transit</p>
            <p className="mt-2 text-2xl font-semibold text-amber-100">{shipmentSummary.inTransit}</p>
          </article>
          <article className="rounded-2xl border border-red-300/35 bg-red-500/10 p-3">
            <p className="text-xs uppercase tracking-[0.14em] text-red-100/80">Anchor Failures</p>
            <p className="mt-2 text-2xl font-semibold text-red-100">{pipeline?.pipeline.anchors_failed ?? 0}</p>
          </article>
          <article className="rounded-2xl border border-emerald-300/35 bg-emerald-500/10 p-3">
            <p className="text-xs uppercase tracking-[0.14em] text-emerald-100/80">Anchor Pending</p>
            <p className="mt-2 text-2xl font-semibold text-emerald-100">{pipeline?.pipeline.anchors_pending ?? 0}</p>
          </article>
        </div>
      </section>

      {(pipeline?.pipeline.anchors_failed ?? 0) > 0 && (
        <section className="panel p-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-red-300/45 bg-red-500/15 px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-red-100">
            <AlertTriangle className="h-3.5 w-3.5" />
            Anchor failures detected
          </div>
          <p className="mt-3 text-sm text-slate-300">
            Use Operations panel to retry failed anchor candidates and run reconciliation.
          </p>
        </section>
      )}

      <section className="grid gap-4 xl:grid-cols-2">
        <article className="panel p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Batch State Distribution</p>
          <div className="mt-3 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={batchStatusChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.12)" />
                <XAxis dataKey="status" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} width={30} />
                <RechartsTooltip
                  contentStyle={{
                    background: 'rgba(9, 16, 28, 0.95)',
                    border: '1px solid rgba(148,163,184,0.2)',
                    borderRadius: 12,
                  }}
                />
                <Bar dataKey="count" fill="#22d3ee" radius={[8, 8, 0, 0]} name="Batches" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Redis Stream Backlog</p>
          {streamChartData.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">Redis stream metrics unavailable.</p>
          ) : (
            <div className="mt-3 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={streamChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.12)" />
                  <XAxis dataKey="stream" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} width={30} />
                  <RechartsTooltip
                    contentStyle={{
                      background: 'rgba(9, 16, 28, 0.95)',
                      border: '1px solid rgba(148,163,184,0.2)',
                      borderRadius: 12,
                    }}
                  />
                  <Bar dataKey="length" fill="#f59e0b" radius={[8, 8, 0, 0]} name="Messages" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </article>
      </section>

      {canManageOperations && (
        <section className="panel p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Worker Runtime</p>
              <h2 className="mt-1 text-lg font-semibold text-slate-100">Redis Worker Orchestration</h2>
            </div>
            <button
              type="button"
              className="btn-secondary px-3 py-2 text-xs"
              onClick={() => void refetchWorkers()}
              disabled={workersLoading}
            >
              {workersLoading ? 'Refreshing...' : 'Refresh Workers'}
            </button>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <article className="rounded-2xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Orchestrator</p>
              <p className="mt-2 text-lg font-semibold text-slate-100">
                {workers?.orchestrator.started ? 'Started' : 'Stopped'}
              </p>
            </article>
            <article className="rounded-2xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Health</p>
              <p className="mt-2 text-lg font-semibold text-slate-100">
                {workers?.orchestrator.healthy ? 'Healthy' : 'Degraded'}
              </p>
            </article>
            <article className="rounded-2xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Shutdown Requested</p>
              <p className="mt-2 text-lg font-semibold text-slate-100">
                {workers?.orchestrator.shutdown_requested ? 'Yes' : 'No'}
              </p>
            </article>
          </div>

          <div className="mt-4 space-y-3">
            {workerRows.length === 0 ? (
              <p className="text-sm text-slate-400">Worker details are unavailable.</p>
            ) : (
              workerRows.map(([workerName, snapshot]) => (
                <article key={workerName} className="rounded-2xl border border-slate-700/70 bg-surface-800/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-slate-100">{workerName}</p>
                      <p className="mt-1 text-xs text-slate-400">
                        Running: {String(snapshot.running ?? 'unknown')} • Restarts: {String(snapshot.restart_count ?? 0)}
                      </p>
                    </div>
                    <p className="text-xs text-slate-400">Heartbeat: {snapshot.last_heartbeat || 'N/A'}</p>
                  </div>
                  {snapshot.error && (
                    <p className="mt-3 rounded-xl border border-red-300/25 bg-red-500/10 px-3 py-2 text-sm text-red-100">
                      {String(snapshot.error)}
                    </p>
                  )}
                </article>
              ))
            )}
          </div>
        </section>
      )}
    </div>
  );
}

export default IntelligencePage;
