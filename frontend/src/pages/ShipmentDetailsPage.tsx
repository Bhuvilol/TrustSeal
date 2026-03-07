import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import ComplianceCard from '@/components/ComplianceCard';
import EmptyState from '@/components/EmptyState';
import ErrorState from '@/components/ErrorState';
import LiveTelemetryModule from '@/components/LiveTelemetryModule';
import LoadingState from '@/components/LoadingState';
import ProofPanel from '@/components/ProofPanel';
import SensorStatsStrip from '@/components/SensorStatsStrip';
import StatusBadge from '@/components/StatusBadge';
import { getLatestShipmentProof } from '@/api/proofs';
import { getPipelineStatus, reconcilePipeline, retryAnchor, retryCustodyGate, retryIpfs } from '@/api/ops';
import {
  completeShipmentLeg,
  createShipmentLeg,
  startShipmentLeg,
  updateShipment,
} from '@/api/shipments';
import { useAuth } from '@/hooks/useAuth';
import { useDevice } from '@/hooks/useDevices';
import {
  useShipment,
  useShipmentCustody,
  useShipmentLegs,
  useShipmentOverview,
  useShipmentSensorStats,
  useShipmentTelemetry,
} from '@/hooks/useShipments';
import { useToast } from '@/hooks/useToast';
import type { ShipmentStatus } from '@/types';
import { calculateSensorStats, sensorStatsFromBackend } from '@/utils/compliance';
import { getErrorMessage, getHttpStatus } from '@/utils/errors';
import { formatDateTime } from '@/utils/format';
import { hasPermission } from '@/utils/permissions';

interface LegFormState {
  leg_number: string;
  from_location: string;
  to_location: string;
}

const defaultLegForm: LegFormState = {
  leg_number: '',
  from_location: '',
  to_location: '',
};

function ShipmentDetailsPage() {
  const { shipmentId } = useParams<{ shipmentId: string }>();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { showError, showInfo, showSuccess } = useToast();

  const canManageLegs = hasPermission(user?.role, 'manage_legs');
  const canUpdateShipmentStatus = hasPermission(user?.role, 'update_shipment_status');
  const canManageOperations = hasPermission(user?.role, 'manage_operations');

  const [isAddLegOpen, setIsAddLegOpen] = useState(false);
  const [isSubmittingLeg, setIsSubmittingLeg] = useState(false);
  const [pendingLegActionKey, setPendingLegActionKey] = useState<string | null>(null);
  const [pendingShipmentStatus, setPendingShipmentStatus] = useState<ShipmentStatus | null>(null);
  const [pendingOpsAction, setPendingOpsAction] = useState<string | null>(null);
  const [legForm, setLegForm] = useState<LegFormState>(defaultLegForm);
  const [liveShipmentStatus, setLiveShipmentStatus] = useState<ShipmentStatus | null>(null);
  const lastTelemetryRefreshRef = useRef(0);

  const {
    data: shipment,
    isLoading: shipmentLoading,
    isError: shipmentError,
    error: shipmentErrorObj,
    refetch: refetchShipment,
  } = useShipment(shipmentId);
  const { data: shipmentOverview } = useShipmentOverview(shipmentId);
  const {
    data: telemetry,
    isLoading: telemetryLoading,
    isError: telemetryError,
    error: telemetryErrorObj,
  } = useShipmentTelemetry(shipment?.id, { limit: 500 });
  const {
    data: sensorStatsSnapshot,
    isLoading: sensorStatsLoading,
    isError: sensorStatsError,
    error: sensorStatsErrorObj,
  } = useShipmentSensorStats(shipment?.id);
  const {
    data: legs,
    isError: legsError,
    error: legsErrorObj,
  } = useShipmentLegs(shipment?.id);
  const {
    data: custody,
    isError: custodyError,
    error: custodyErrorObj,
  } = useShipmentCustody(shipment?.id);

  const {
    data: attachedDevice,
    isError: deviceError,
  } = useDevice(shipment?.device_id);
  const {
    data: latestProof,
    isLoading: proofLoading,
    isError: proofError,
    error: proofErrorObj,
    refetch: refetchProof,
  } = useQuery({
    queryKey: ['proof', 'shipment-latest', shipment?.id],
    queryFn: () => getLatestShipmentProof(shipment?.id as string),
    enabled: Boolean(shipment?.id),
    retry: 0,
    staleTime: 30_000,
    gcTime: 5 * 60_000,
  });
  const { data: pipelineStatus } = useQuery({
    queryKey: ['ops', 'pipeline-status', shipment?.id],
    queryFn: () => getPipelineStatus(shipment?.id as string),
    enabled: Boolean(shipment?.id) && canManageOperations,
    retry: 0,
    staleTime: 20_000,
    gcTime: 2 * 60_000,
  });

  const sortedLegs = useMemo(
    () => [...(legs ?? [])].sort((left, right) => left.leg_number - right.leg_number),
    [legs],
  );

  const sortedCustody = useMemo(
    () =>
      [...(custody ?? [])].sort(
        (left, right) => new Date(right.ts || right.created_at).getTime() - new Date(left.ts || left.created_at).getTime(),
      ),
    [custody],
  );

  const sensorStats = useMemo(
    () =>
      sensorStatsSnapshot
        ? sensorStatsFromBackend(sensorStatsSnapshot, shipment?.status)
        : calculateSensorStats(telemetry ?? [], shipment?.status),
    [sensorStatsSnapshot, telemetry, shipment?.status],
  );
  const telemetryRecords = useMemo(() => telemetry ?? [], [telemetry]);

  useEffect(() => {
    setLiveShipmentStatus(shipment?.status ?? null);
  }, [shipment?.status]);

  if (!shipmentId) {
    return <ErrorState message="Shipment ID is missing from the route." />;
  }

  if (shipmentLoading) {
    return <LoadingState message="Loading shipment operations..." />;
  }

  if (shipmentError) {
    const message = getErrorMessage(shipmentErrorObj, 'Failed to load shipment.');
    return (
      <ErrorState
        message={message}
        onRetry={() => {
          void refetchShipment();
        }}
      />
    );
  }

  if (!shipment) {
    return (
      <EmptyState
        title="Shipment not found"
        description="The requested shipment does not exist or is not accessible."
        action={
          <Link className="btn-secondary" to="/shipments">
            Back to Shipments
          </Link>
        }
      />
    );
  }

  const refreshShipmentData = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId] }),
      queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'overview'] }),
      queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'logs'] }),
      queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'telemetry'] }),
      queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'sensor-stats'] }),
      queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'legs'] }),
      queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'custody'] }),
      queryClient.invalidateQueries({ queryKey: ['proof', 'shipment-latest', shipmentId] }),
      queryClient.invalidateQueries({ queryKey: ['ops', 'pipeline-status', shipmentId] }),
      queryClient.invalidateQueries({ queryKey: ['shipments'] }),
    ]);
  };

  const handleRealtimeEvent = async (eventName: string) => {
    if (eventName === 'shipment.status_changed' || eventName === 'shipment.settled') {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId] }),
        queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'overview'] }),
        queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'legs'] }),
        queryClient.invalidateQueries({ queryKey: ['proof', 'shipment-latest', shipmentId] }),
        queryClient.invalidateQueries({ queryKey: ['ops', 'pipeline-status', shipmentId] }),
        queryClient.invalidateQueries({ queryKey: ['shipments'] }),
      ]);
      return;
    }

    if (eventName === 'telemetry-update') {
      const now = Date.now();
      if (now - lastTelemetryRefreshRef.current < 20_000) {
        return;
      }
      lastTelemetryRefreshRef.current = now;
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'sensor-stats'] }),
        queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'overview'] }),
      ]);
    }
  };

  const openAddLegForm = () => {
    const nextLeg = (sortedLegs.at(-1)?.leg_number ?? 0) + 1;
    setLegForm({
      leg_number: String(nextLeg),
      from_location: '',
      to_location: '',
    });
    setIsAddLegOpen(true);
  };

  const handleAddLeg = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmittingLeg(true);

    try {
      await createShipmentLeg({
        shipment_id: shipmentId,
        leg_number: Number(legForm.leg_number),
        from_location: legForm.from_location.trim(),
        to_location: legForm.to_location.trim(),
      });
      showSuccess('Shipment leg created.');
      await refreshShipmentData();
      setIsAddLegOpen(false);
      setLegForm(defaultLegForm);
    } catch (legError) {
      if (getHttpStatus(legError) !== 403) {
        showError(getErrorMessage(legError, 'Unable to create shipment leg.'));
      }
    } finally {
      setIsSubmittingLeg(false);
    }
  };

  const handleLegStatus = async (legId: string, action: 'start' | 'complete') => {
    const actionKey = `${legId}:${action}`;
    setPendingLegActionKey(actionKey);

    try {
      if (action === 'start') {
        await startShipmentLeg(legId);
        showSuccess('Leg marked in progress.');
      } else {
        await completeShipmentLeg(legId);
        showSuccess('Leg marked settled.');
      }
      await refreshShipmentData();
    } catch (actionError) {
      if (getHttpStatus(actionError) !== 403) {
        showError(getErrorMessage(actionError, 'Unable to update leg status.'));
      }
    } finally {
      setPendingLegActionKey(null);
    }
  };

  const handleShipmentStatus = async (status: ShipmentStatus) => {
    setPendingShipmentStatus(status);

    try {
      await updateShipment(shipmentId, { status });
      showSuccess(`Shipment status updated to ${status.replace('_', ' ')}.`);
      await refreshShipmentData();
    } catch (statusError) {
      if (getHttpStatus(statusError) !== 403) {
        showError(getErrorMessage(statusError, 'Unable to update shipment status.'));
      }
    } finally {
      setPendingShipmentStatus(null);
    }
  };

  const handleOpsAction = async (
    action: 'retry-ipfs' | 'retry-custody-gate' | 'retry-anchor' | 'reconcile',
  ) => {
    const bundleId =
      pipelineStatus?.shipment?.latest_bundle_id || shipmentOverview?.latest_bundle?.bundle_id || latestProof?.bundle_id;
    setPendingOpsAction(action);

    try {
      if (action === 'retry-ipfs') {
        if (!bundleId) {
          showError('No bundle is available for IPFS retry.');
          return;
        }
        const response = await retryIpfs(bundleId);
        showSuccess(`IPFS retry queued for bundle ${response.bundle_id}.`);
      } else if (action === 'retry-custody-gate') {
        if (!bundleId) {
          showError('No bundle is available for custody gate retry.');
          return;
        }
        const response = await retryCustodyGate(bundleId);
        showSuccess(`Custody gate re-run completed for bundle ${response.bundle_id}.`);
      } else if (action === 'retry-anchor') {
        if (!bundleId) {
          showError('No bundle is available for anchor retry.');
          return;
        }
        const response = await retryAnchor(bundleId);
        showSuccess(`Anchor retry queued for bundle ${response.bundle_id}.`);
      } else {
        const response = await reconcilePipeline(shipment.id, true);
        showInfo(
          `Reconciliation scanned ${response.scanned_batches} batches and repaired ${response.repaired_bundle_ids.length}.`,
        );
      }

      await refreshShipmentData();
      void refetchProof();
    } catch (opsError) {
      if (getHttpStatus(opsError) !== 403) {
        showError(getErrorMessage(opsError, 'Unable to complete the requested pipeline operation.'));
      }
    } finally {
      setPendingOpsAction(null);
    }
  };

  const renderLegActionButton = (
    legId: string,
    action: 'start' | 'complete',
    label: string,
    disabled: boolean,
  ) => {
    const actionKey = `${legId}:${action}`;
    return (
      <button
        type="button"
        className="btn-secondary px-3 py-1.5 text-xs"
        onClick={() => void handleLegStatus(legId, action)}
        disabled={disabled || pendingLegActionKey === actionKey}
      >
        {pendingLegActionKey === actionKey ? 'Updating...' : label}
      </button>
    );
  };

  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <Link to="/shipments" className="text-sm font-medium text-brand-300 transition hover:text-brand-400">
          &larr; Back to shipments
        </Link>
        <div className="panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Shipment Code</p>
              <h1 className="mt-1 text-2xl font-semibold text-slate-100">{shipment.shipment_code}</h1>
              <p className="mt-2 text-sm text-slate-300">
                {shipment.origin} {'->'} {shipment.destination}
              </p>
            </div>
            <StatusBadge kind="shipment" status={liveShipmentStatus ?? shipment.status} />
          </div>
        </div>
      </header>

      <section className="panel p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-100">Shipment Information</h2>
          {canUpdateShipmentStatus && (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="btn-primary px-3 py-2 text-sm"
                onClick={() => void handleShipmentStatus('in_transit')}
                disabled={pendingShipmentStatus === 'in_transit' || (liveShipmentStatus ?? shipment.status) === 'in_transit'}
              >
                {pendingShipmentStatus === 'in_transit' ? 'Updating...' : 'Mark as In Transit'}
              </button>
              <button
                type="button"
                className="btn-primary px-3 py-2 text-sm"
                onClick={() => void handleShipmentStatus('completed')}
                disabled={pendingShipmentStatus === 'completed' || (liveShipmentStatus ?? shipment.status) === 'completed'}
              >
                {pendingShipmentStatus === 'completed' ? 'Updating...' : 'Mark as Completed'}
              </button>
            </div>
          )}
        </div>
        <div className="grid gap-3 text-sm text-slate-300 md:grid-cols-2">
          <p>Shipment ID: {shipment.id}</p>
          <p>Created: {formatDateTime(shipment.created_at)}</p>
          <p>Description: {shipment.description || 'N/A'}</p>
          <p>Device ID: {shipment.device_id}</p>
          <p>Latest Bundle: {shipmentOverview?.latest_bundle?.bundle_id || 'Not created yet'}</p>
          <p>Latest Anchor: {shipmentOverview?.latest_bundle?.anchor_status || 'Not anchored yet'}</p>
        </div>
      </section>

      {canManageOperations && pipelineStatus?.shipment && (
        <section className="panel p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-100">Pipeline Status</h2>
            <div className="flex flex-wrap items-center gap-2">
              <>
                <button
                  type="button"
                  className="btn-secondary px-3 py-2 text-xs"
                  onClick={() => void handleOpsAction('retry-ipfs')}
                  disabled={pendingOpsAction !== null}
                >
                  {pendingOpsAction === 'retry-ipfs' ? 'Retrying IPFS...' : 'Retry IPFS'}
                </button>
                <button
                  type="button"
                  className="btn-secondary px-3 py-2 text-xs"
                  onClick={() => void handleOpsAction('retry-custody-gate')}
                  disabled={pendingOpsAction !== null}
                >
                  {pendingOpsAction === 'retry-custody-gate' ? 'Checking custody...' : 'Retry Custody Gate'}
                </button>
                <button
                  type="button"
                  className="btn-secondary px-3 py-2 text-xs"
                  onClick={() => void handleOpsAction('retry-anchor')}
                  disabled={pendingOpsAction !== null}
                >
                  {pendingOpsAction === 'retry-anchor' ? 'Retrying anchor...' : 'Retry Anchor'}
                </button>
                <button
                  type="button"
                  className="btn-secondary px-3 py-2 text-xs"
                  onClick={() => void handleOpsAction('reconcile')}
                  disabled={pendingOpsAction !== null}
                >
                  {pendingOpsAction === 'reconcile' ? 'Reconciling...' : 'Reconcile'}
                </button>
              </>
              <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                Canonical ops state
              </span>
            </div>
          </div>
          <div className="grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Ingest</p>
              <p className="mt-2 font-semibold text-slate-100">{pipelineStatus.shipment.ingest}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Batch</p>
              <p className="mt-2 font-semibold text-slate-100">{pipelineStatus.shipment.batch}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Custody</p>
              <p className="mt-2 font-semibold text-slate-100">{pipelineStatus.shipment.custody}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Anchor</p>
              <p className="mt-2 font-semibold text-slate-100">{pipelineStatus.shipment.anchor}</p>
            </div>
          </div>
          {(pipelineStatus.shipment.latest_bundle_id || pipelineStatus.shipment.latest_ipfs_cid || pipelineStatus.shipment.latest_tx_hash) && (
            <div className="mt-4 grid gap-2 text-xs text-slate-400 md:grid-cols-3">
              <p>Bundle: {pipelineStatus.shipment.latest_bundle_id || 'N/A'}</p>
              <p className="truncate">IPFS CID: {pipelineStatus.shipment.latest_ipfs_cid || 'N/A'}</p>
              <p className="truncate">Tx Hash: {pipelineStatus.shipment.latest_tx_hash || 'N/A'}</p>
            </div>
          )}
          {pipelineStatus.shipment.error_message && (
            <p className="mt-3 rounded-xl border border-amber-300/25 bg-amber-500/10 px-3 py-2 text-sm text-amber-100">
              {pipelineStatus.shipment.error_message}
            </p>
          )}
        </section>
      )}

      {proofLoading ? (
        <div className="panel p-5">
          <p className="text-sm text-slate-400">Loading proof state...</p>
        </div>
      ) : proofError ? (
        <div className="panel p-5">
          <h2 className="mb-3 text-lg font-semibold text-slate-100">Proof & Chain Anchor</h2>
          <p className="rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">
            {getErrorMessage(proofErrorObj, 'Proof state is unavailable for this shipment.')}
          </p>
        </div>
      ) : latestProof ? (
        <ProofPanel proof={latestProof} onRefresh={() => void refetchProof()} isRefreshing={proofLoading} />
      ) : (
        <div className="panel p-5">
          <h2 className="mb-3 text-lg font-semibold text-slate-100">Proof & Chain Anchor</h2>
          <p className="text-sm text-slate-400">No proof bundle found yet for this shipment.</p>
        </div>
      )}

      <section className="panel p-5">
        <h2 className="text-lg font-semibold text-slate-100">Attached Device</h2>
        {attachedDevice ? (
          <div className="mt-4 grid gap-3 text-sm text-slate-300 md:grid-cols-2">
            <p>Device UID: {attachedDevice.device_uid}</p>
            <p>Model: {attachedDevice.model}</p>
            <p>Firmware: {attachedDevice.firmware_version}</p>
            <p>
              Battery Capacity:{' '}
              {attachedDevice.battery_capacity_mAh === null
                ? 'N/A'
                : `${attachedDevice.battery_capacity_mAh} mAh`}
            </p>
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-400">
            {deviceError ? 'Attached device details could not be loaded.' : 'Attached device details are unavailable.'}
          </p>
        )}
      </section>

      <section className="space-y-4">
        {(telemetryLoading || sensorStatsLoading || telemetryError || sensorStatsError) && (
          <div className="rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-300">
            {telemetryLoading || sensorStatsLoading
              ? 'Telemetry data is still loading...'
              : `Telemetry is temporarily unavailable: ${
                  telemetryError
                    ? getErrorMessage(telemetryErrorObj, 'Failed to load shipment telemetry logs.')
                    : getErrorMessage(sensorStatsErrorObj, 'Failed to load shipment sensor statistics.')
                }`}
          </div>
        )}
        <SensorStatsStrip stats={sensorStats} />
        <ComplianceCard stats={sensorStats} />
        <LiveTelemetryModule
          shipmentId={shipment.id}
          initialTelemetry={telemetryRecords}
          legs={sortedLegs}
          origin={shipment.origin}
          destination={shipment.destination}
          status={liveShipmentStatus ?? shipment.status}
          onRealtimeShipmentStatus={setLiveShipmentStatus}
          onRealtimeEvent={(eventName) => {
            void handleRealtimeEvent(eventName);
          }}
        />
      </section>

      <section className="panel p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-100">Shipment Legs</h2>
          {canManageLegs && (
            <button type="button" className="btn-primary px-3 py-2 text-sm" onClick={openAddLegForm}>
              Add Leg
            </button>
          )}
        </div>

        {isAddLegOpen && canManageLegs && (
          <form className="mb-5 grid gap-4 rounded-xl border border-slate-700/70 p-4 md:grid-cols-3" onSubmit={handleAddLeg}>
            <div className="space-y-1">
              <label htmlFor="leg_number" className="text-sm text-slate-300">
                Leg Number
              </label>
              <input
                id="leg_number"
                type="number"
                min={1}
                className="input-field"
                value={legForm.leg_number}
                onChange={(event) => setLegForm((prev) => ({ ...prev, leg_number: event.target.value }))}
                required
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="from_location" className="text-sm text-slate-300">
                From Location
              </label>
              <input
                id="from_location"
                type="text"
                className="input-field"
                value={legForm.from_location}
                onChange={(event) => setLegForm((prev) => ({ ...prev, from_location: event.target.value }))}
                required
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="to_location" className="text-sm text-slate-300">
                To Location
              </label>
              <input
                id="to_location"
                type="text"
                className="input-field"
                value={legForm.to_location}
                onChange={(event) => setLegForm((prev) => ({ ...prev, to_location: event.target.value }))}
                required
              />
            </div>

            <div className="md:col-span-3 flex flex-wrap gap-2">
              <button type="submit" className="btn-primary" disabled={isSubmittingLeg}>
                {isSubmittingLeg ? 'Saving...' : 'Create Leg'}
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setIsAddLegOpen(false);
                  setLegForm(defaultLegForm);
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {legsError ? (
          <p className="rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">
            {getErrorMessage(legsErrorObj, 'Shipment legs could not be loaded right now.')}
          </p>
        ) : sortedLegs.length === 0 ? (
          <p className="rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">
            No legs defined for this shipment.
          </p>
        ) : (
          <ol className="space-y-4">
            {sortedLegs.map((leg, index) => (
              <li key={leg.id} className="relative pl-8">
                {index < sortedLegs.length - 1 && (
                  <span className="absolute left-[7px] top-6 h-[calc(100%+0.5rem)] w-px bg-slate-600" />
                )}
                <span className="absolute left-0 top-1.5 h-4 w-4 rounded-full border border-brand-300 bg-brand-500/25" />

                <div className="rounded-xl border border-slate-700/70 bg-surface-800/60 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-100">
                      Leg {leg.leg_number}: {leg.from_location} {'->'} {leg.to_location}
                    </p>
                    <StatusBadge kind="leg" status={leg.status} />
                  </div>
                  <div className="mt-2 grid gap-2 text-xs text-slate-400 md:grid-cols-2">
                    <p>Started: {formatDateTime(leg.started_at)}</p>
                    <p>Completed: {formatDateTime(leg.completed_at)}</p>
                  </div>
                  {canManageLegs && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {renderLegActionButton(
                        leg.id,
                        'start',
                        'Start Leg',
                        leg.status === 'in_progress' || leg.status === 'settled',
                      )}
                      {renderLegActionButton(leg.id, 'complete', 'Complete Leg', leg.status === 'settled')}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="panel p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-100">Custody Timeline</h2>
        </div>

        {custodyError ? (
          <p className="rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">
            {getErrorMessage(custodyErrorObj, 'Custody timeline could not be loaded right now.')}
          </p>
        ) : sortedCustody.length === 0 ? (
          <p className="rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">
            No custody verification events recorded for this shipment.
          </p>
        ) : (
          <ol className="space-y-4">
            {sortedCustody.map((checkpoint, index) => (
              <li key={checkpoint.custody_event_id} className="relative pl-8">
                {index < sortedCustody.length - 1 && (
                  <span className="absolute left-[7px] top-6 h-[calc(100%+0.5rem)] w-px bg-slate-600" />
                )}
                <span className="absolute left-0 top-1.5 h-4 w-4 rounded-full border border-brand-300 bg-brand-500/25" />
                <article className="rounded-xl border border-slate-700/70 bg-surface-800/60 p-4 text-sm text-slate-200">
                  <p>Verifier user: {checkpoint.verifier_user_id || 'N/A'}</p>
                  <p>Verifier device: {checkpoint.verifier_device_id || 'N/A'}</p>
                  <p>Timestamp: {formatDateTime(checkpoint.ts || checkpoint.created_at)}</p>
                  <p>Fingerprint result: {checkpoint.fingerprint_result || 'unknown'}</p>
                  <p>Verification status: {checkpoint.verification_status || 'unknown'}</p>
                  <p className="max-w-full truncate font-mono text-xs text-slate-300">
                    Approval hash: {checkpoint.approval_hash || 'N/A'}
                  </p>
                </article>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

export default ShipmentDetailsPage;
