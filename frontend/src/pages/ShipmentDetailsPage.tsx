import { FormEvent, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import ComplianceCard from '@/components/ComplianceCard';
import EmptyState from '@/components/EmptyState';
import ErrorState from '@/components/ErrorState';
import LiveTelemetryModule from '@/components/LiveTelemetryModule';
import LoadingState from '@/components/LoadingState';
import SensorStatsStrip from '@/components/SensorStatsStrip';
import StatusBadge from '@/components/StatusBadge';
import {
  completeShipmentLeg,
  createCustodyCheckpoint,
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

interface CustodyFormState {
  leg_id: string;
  biometric_verified: boolean;
  blockchain_tx_hash: string;
  merkle_root_hash: string;
}

const defaultLegForm: LegFormState = {
  leg_number: '',
  from_location: '',
  to_location: '',
};

const defaultCustodyForm: CustodyFormState = {
  leg_id: '',
  biometric_verified: false,
  blockchain_tx_hash: '',
  merkle_root_hash: '',
};

function ShipmentDetailsPage() {
  const { shipmentId } = useParams<{ shipmentId: string }>();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { showError, showSuccess } = useToast();

  const canManageLegs = hasPermission(user?.role, 'manage_legs');
  const canManageCheckpoints = hasPermission(user?.role, 'manage_checkpoints');
  const canUpdateShipmentStatus = hasPermission(user?.role, 'update_shipment_status');

  const [isAddLegOpen, setIsAddLegOpen] = useState(false);
  const [isAddCustodyOpen, setIsAddCustodyOpen] = useState(false);
  const [isSubmittingLeg, setIsSubmittingLeg] = useState(false);
  const [isSubmittingCustody, setIsSubmittingCustody] = useState(false);
  const [pendingLegActionKey, setPendingLegActionKey] = useState<string | null>(null);
  const [pendingShipmentStatus, setPendingShipmentStatus] = useState<ShipmentStatus | null>(null);
  const [legForm, setLegForm] = useState<LegFormState>(defaultLegForm);
  const [custodyForm, setCustodyForm] = useState<CustodyFormState>(defaultCustodyForm);

  const {
    data: shipment,
    isLoading: shipmentLoading,
    isError: shipmentError,
    error: shipmentErrorObj,
    refetch: refetchShipment,
  } = useShipment(shipmentId);
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

  const sortedLegs = useMemo(
    () => [...(legs ?? [])].sort((left, right) => left.leg_number - right.leg_number),
    [legs],
  );

  const sortedCustody = useMemo(
    () =>
      [...(custody ?? [])].sort(
        (left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime(),
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
      queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'logs'] }),
      queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'telemetry'] }),
      queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'sensor-stats'] }),
      queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'legs'] }),
      queryClient.invalidateQueries({ queryKey: ['shipment', shipmentId, 'custody'] }),
      queryClient.invalidateQueries({ queryKey: ['shipments'] }),
    ]);
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

  const handleAddCustody = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmittingCustody(true);

    try {
      await createCustodyCheckpoint({
        shipment_id: shipmentId,
        leg_id: custodyForm.leg_id || null,
        biometric_verified: custodyForm.biometric_verified,
        blockchain_tx_hash: custodyForm.blockchain_tx_hash.trim() || null,
        merkle_root_hash: custodyForm.merkle_root_hash.trim() || null,
      });
      showSuccess('Custody checkpoint created.');
      await refreshShipmentData();
      setIsAddCustodyOpen(false);
      setCustodyForm(defaultCustodyForm);
    } catch (custodyError) {
      if (getHttpStatus(custodyError) !== 403) {
        showError(getErrorMessage(custodyError, 'Unable to create custody checkpoint.'));
      }
    } finally {
      setIsSubmittingCustody(false);
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
            <StatusBadge kind="shipment" status={shipment.status} />
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
                disabled={pendingShipmentStatus === 'in_transit' || shipment.status === 'in_transit'}
              >
                {pendingShipmentStatus === 'in_transit' ? 'Updating...' : 'Mark as In Transit'}
              </button>
              <button
                type="button"
                className="btn-primary px-3 py-2 text-sm"
                onClick={() => void handleShipmentStatus('completed')}
                disabled={pendingShipmentStatus === 'completed' || shipment.status === 'completed'}
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
        </div>
      </section>

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
          status={shipment.status}
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
          <h2 className="text-lg font-semibold text-slate-100">Custody Checkpoints</h2>
          {canManageCheckpoints && (
            <button
              type="button"
              className="btn-primary px-3 py-2 text-sm"
              onClick={() => setIsAddCustodyOpen(true)}
            >
              Add Custody Checkpoint
            </button>
          )}
        </div>

        {isAddCustodyOpen && canManageCheckpoints && (
          <form
            className="mb-5 grid gap-4 rounded-xl border border-slate-700/70 p-4 md:grid-cols-2"
            onSubmit={handleAddCustody}
          >
            <div className="space-y-1 md:col-span-2">
              <label htmlFor="custody_shipment_id" className="text-sm text-slate-300">
                Shipment ID
              </label>
              <input id="custody_shipment_id" type="text" className="input-field" value={shipmentId} disabled />
            </div>

            <div className="space-y-1">
              <label htmlFor="custody_leg_id" className="text-sm text-slate-300">
                Leg
              </label>
              <select
                id="custody_leg_id"
                className="input-field"
                value={custodyForm.leg_id}
                onChange={(event) => setCustodyForm((prev) => ({ ...prev, leg_id: event.target.value }))}
              >
                <option value="">No leg selected</option>
                {sortedLegs.map((leg) => (
                  <option key={leg.id} value={leg.id}>
                    Leg {leg.leg_number}: {leg.from_location} {'->'} {leg.to_location}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label htmlFor="custody_blockchain_hash" className="text-sm text-slate-300">
                Blockchain TX Hash
              </label>
              <input
                id="custody_blockchain_hash"
                type="text"
                className="input-field"
                value={custodyForm.blockchain_tx_hash}
                onChange={(event) =>
                  setCustodyForm((prev) => ({ ...prev, blockchain_tx_hash: event.target.value }))
                }
              />
            </div>

            <div className="space-y-1 md:col-span-2">
              <label htmlFor="custody_merkle_hash" className="text-sm text-slate-300">
                Merkle Root Hash
              </label>
              <input
                id="custody_merkle_hash"
                type="text"
                className="input-field"
                value={custodyForm.merkle_root_hash}
                onChange={(event) =>
                  setCustodyForm((prev) => ({ ...prev, merkle_root_hash: event.target.value }))
                }
              />
            </div>

            <label className="md:col-span-2 inline-flex items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={custodyForm.biometric_verified}
                onChange={(event) =>
                  setCustodyForm((prev) => ({ ...prev, biometric_verified: event.target.checked }))
                }
              />
              Biometric Verified
            </label>

            <div className="md:col-span-2 flex flex-wrap gap-2">
              <button type="submit" className="btn-primary" disabled={isSubmittingCustody}>
                {isSubmittingCustody ? 'Saving...' : 'Create Checkpoint'}
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setIsAddCustodyOpen(false);
                  setCustodyForm(defaultCustodyForm);
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {custodyError ? (
          <p className="rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">
            {getErrorMessage(custodyErrorObj, 'Custody checkpoints could not be loaded right now.')}
          </p>
        ) : sortedCustody.length === 0 ? (
          <p className="rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">
            No custody checkpoints recorded for this shipment.
          </p>
        ) : (
          <ol className="space-y-4">
            {sortedCustody.map((checkpoint, index) => (
              <li key={checkpoint.id} className="relative pl-8">
                {index < sortedCustody.length - 1 && (
                  <span className="absolute left-[7px] top-6 h-[calc(100%+0.5rem)] w-px bg-slate-600" />
                )}
                <span className="absolute left-0 top-1.5 h-4 w-4 rounded-full border border-brand-300 bg-brand-500/25" />
                <article className="rounded-xl border border-slate-700/70 bg-surface-800/60 p-4 text-sm text-slate-200">
                  <p>Verified by: {checkpoint.verified_by || 'N/A'}</p>
                  <p>Timestamp: {formatDateTime(checkpoint.timestamp)}</p>
                  <p>Biometric verified: {checkpoint.biometric_verified ? 'Yes' : 'No'}</p>
                  <p className="max-w-full truncate font-mono text-xs text-slate-300">
                    Blockchain tx hash: {checkpoint.blockchain_tx_hash || 'N/A'}
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
