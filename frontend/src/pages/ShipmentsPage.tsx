import { FormEvent, useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import EmptyState from '@/components/EmptyState';
import ErrorState from '@/components/ErrorState';
import LoadingState from '@/components/LoadingState';
import StatusBadge from '@/components/StatusBadge';
import { createShipment } from '@/api/shipments';
import { useAuth } from '@/hooks/useAuth';
import { useDevices } from '@/hooks/useDevices';
import { useShipments } from '@/hooks/useShipments';
import { useToast } from '@/hooks/useToast';
import type { ShipmentStatus } from '@/types';
import { getErrorMessage, getHttpStatus } from '@/utils/errors';
import { hasPermission } from '@/utils/permissions';

type ShipmentFilter = 'all' | ShipmentStatus;

const SHIPMENT_FILTER_OPTIONS: ShipmentFilter[] = [
  'all',
  'created',
  'in_transit',
  'docking',
  'completed',
  'compromised',
];

interface ShipmentFormState {
  shipment_code: string;
  description: string;
  origin: string;
  destination: string;
  device_id: string;
}

const defaultFormState: ShipmentFormState = {
  shipment_code: '',
  description: '',
  origin: '',
  destination: '',
  device_id: '',
};

function ShipmentsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { showError, showSuccess } = useToast();
  const canCreateShipments = hasPermission(user?.role, 'create_shipments');

  const [statusFilter, setStatusFilter] = useState<ShipmentFilter>('all');
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formState, setFormState] = useState<ShipmentFormState>(defaultFormState);

  const {
    data: shipments,
    isLoading: shipmentsLoading,
    isError: shipmentsError,
    error: shipmentsErrorObj,
    refetch: refetchShipments,
  } = useShipments(statusFilter === 'all' ? undefined : { status: statusFilter });

  const { data: devices, isLoading: devicesLoading } = useDevices();

  useEffect(() => {
    if (!isCreateOpen) {
      return;
    }

    if (!formState.device_id && devices && devices.length > 0) {
      setFormState((prev) => ({ ...prev, device_id: devices[0].id }));
    }
  }, [devices, formState.device_id, isCreateOpen]);

  const resetCreateForm = () => {
    setFormState(defaultFormState);
    setIsCreateOpen(false);
  };

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);

    try {
      const created = await createShipment({
        shipment_code: formState.shipment_code.trim(),
        description: formState.description.trim() || null,
        origin: formState.origin.trim(),
        destination: formState.destination.trim(),
        device_id: formState.device_id,
      });
      showSuccess(`Shipment ${created.shipment_code} created.`);
      await queryClient.invalidateQueries({ queryKey: ['shipments'] });
      resetCreateForm();
      navigate(`/shipments/${created.id}`);
    } catch (createError) {
      if (getHttpStatus(createError) !== 403) {
        showError(getErrorMessage(createError, 'Unable to create shipment.'));
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (shipmentsLoading) {
    return <LoadingState message="Loading shipments..." />;
  }

  if (shipmentsError) {
    return (
      <ErrorState
        message={getErrorMessage(shipmentsErrorObj, 'Failed to load shipments.')}
        onRetry={() => void refetchShipments()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-100">Shipments</h1>
            <p className="mt-1 text-sm text-slate-400">Create and track operational shipment workflows.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm text-slate-300" htmlFor="shipment-status-filter">
              Status
            </label>
            <select
              id="shipment-status-filter"
              className="input-field min-w-44 py-2"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as ShipmentFilter)}
            >
              {SHIPMENT_FILTER_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option === 'all' ? 'All' : option.replace('_', ' ')}
                </option>
              ))}
            </select>
            {canCreateShipments && (
              <button type="button" className="btn-primary" onClick={() => setIsCreateOpen(true)}>
                Create Shipment
              </button>
            )}
          </div>
        </div>
      </section>

      {isCreateOpen && canCreateShipments && (
        <section className="panel animate-fade-up p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-100">Create Shipment</h2>
            <button type="button" className="btn-secondary px-3 py-2 text-sm" onClick={resetCreateForm}>
              Cancel
            </button>
          </div>

          <form className="grid gap-4 md:grid-cols-2" onSubmit={handleCreate}>
            <div className="space-y-1">
              <label htmlFor="shipment_code" className="text-sm text-slate-300">
                Shipment Code
              </label>
              <input
                id="shipment_code"
                type="text"
                className="input-field"
                value={formState.shipment_code}
                onChange={(event) =>
                  setFormState((prev) => ({ ...prev, shipment_code: event.target.value }))
                }
                required
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="shipment_device" className="text-sm text-slate-300">
                Device
              </label>
              <select
                id="shipment_device"
                className="input-field"
                value={formState.device_id}
                onChange={(event) => setFormState((prev) => ({ ...prev, device_id: event.target.value }))}
                disabled={devicesLoading || !devices || devices.length === 0}
                required
              >
                {!devices || devices.length === 0 ? (
                  <option value="">No devices available</option>
                ) : (
                  devices.map((device) => (
                    <option key={device.id} value={device.id}>
                      {device.device_uid} ({device.model})
                    </option>
                  ))
                )}
              </select>
            </div>

            <div className="space-y-1 md:col-span-2">
              <label htmlFor="shipment_description" className="text-sm text-slate-300">
                Description
              </label>
              <textarea
                id="shipment_description"
                className="input-field min-h-[90px] resize-y"
                value={formState.description}
                onChange={(event) => setFormState((prev) => ({ ...prev, description: event.target.value }))}
                placeholder="Optional shipment description"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="shipment_origin" className="text-sm text-slate-300">
                Origin
              </label>
              <input
                id="shipment_origin"
                type="text"
                className="input-field"
                value={formState.origin}
                onChange={(event) => setFormState((prev) => ({ ...prev, origin: event.target.value }))}
                required
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="shipment_destination" className="text-sm text-slate-300">
                Destination
              </label>
              <input
                id="shipment_destination"
                type="text"
                className="input-field"
                value={formState.destination}
                onChange={(event) => setFormState((prev) => ({ ...prev, destination: event.target.value }))}
                required
              />
            </div>

            <button
              type="submit"
              className="btn-primary md:col-span-2"
              disabled={isSubmitting || !formState.device_id}
            >
              {isSubmitting ? 'Creating...' : 'Create Shipment'}
            </button>
          </form>
        </section>
      )}

      {!shipments || shipments.length === 0 ? (
        <EmptyState
          title="No shipments found"
          description="No shipments match the selected filter."
          action={
            canCreateShipments ? (
              <button type="button" className="btn-primary" onClick={() => setIsCreateOpen(true)}>
                Create Shipment
              </button>
            ) : null
          }
        />
      ) : (
        <section className="panel overflow-x-auto p-2">
          <table className="min-w-full table-auto border-collapse text-left text-sm">
            <thead className="border-b border-slate-700 text-xs uppercase tracking-[0.12em] text-slate-400">
              <tr>
                <th className="px-3 py-2 font-medium">Shipment Code</th>
                <th className="px-3 py-2 font-medium">Origin</th>
                <th className="px-3 py-2 font-medium">Destination</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Device ID</th>
                <th className="px-3 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {shipments.map((shipment) => (
                <tr key={shipment.id} className="border-b border-slate-700/40 text-slate-200">
                  <td className="px-3 py-3 font-medium">{shipment.shipment_code}</td>
                  <td className="px-3 py-3">{shipment.origin}</td>
                  <td className="px-3 py-3">{shipment.destination}</td>
                  <td className="px-3 py-3">
                    <StatusBadge kind="shipment" status={shipment.status} />
                  </td>
                  <td className="max-w-[260px] truncate px-3 py-3 font-mono text-xs">{shipment.device_id}</td>
                  <td className="px-3 py-3">
                    <button
                      type="button"
                      className="btn-primary px-3 py-1.5 text-xs"
                      onClick={() => navigate(`/shipments/${shipment.id}`)}
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}

export default ShipmentsPage;
