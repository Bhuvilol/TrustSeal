import { FormEvent, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import DeviceCard from '@/components/DeviceCard';
import EmptyState from '@/components/EmptyState';
import ErrorState from '@/components/ErrorState';
import LoadingState from '@/components/LoadingState';
import { createDevice, deleteDevice, updateDevice } from '@/api/devices';
import { useAuth } from '@/hooks/useAuth';
import { useDevices } from '@/hooks/useDevices';
import { useShipments } from '@/hooks/useShipments';
import { useToast } from '@/hooks/useToast';
import type { Device, DeviceStatus, Shipment } from '@/types';
import { getErrorMessage, getHttpStatus } from '@/utils/errors';
import { hasPermission } from '@/utils/permissions';

type DeviceFilter = 'all' | DeviceStatus;

const FILTER_OPTIONS: DeviceFilter[] = ['all', 'active', 'inactive', 'maintenance'];

interface DeviceFormState {
  device_uid: string;
  model: string;
  firmware_version: string;
  battery_capacity_mAh: string;
  status: DeviceStatus;
}

const defaultFormState: DeviceFormState = {
  device_uid: '',
  model: '',
  firmware_version: '',
  battery_capacity_mAh: '',
  status: 'active',
};

function toUpdatePayload(form: DeviceFormState) {
  return {
    model: form.model.trim(),
    firmware_version: form.firmware_version.trim(),
    battery_capacity_mAh: form.battery_capacity_mAh.trim() ? Number(form.battery_capacity_mAh) : null,
    status: form.status,
  };
}

function toCreatePayload(form: DeviceFormState) {
  return {
    ...toUpdatePayload(form),
    device_uid: form.device_uid.trim(),
  };
}

function buildShipmentCountMap(shipments: Shipment[] | undefined): Map<string, number> {
  return (shipments ?? []).reduce((map, shipment) => {
    const currentCount = map.get(shipment.device_id) ?? 0;
    map.set(shipment.device_id, currentCount + 1);
    return map;
  }, new Map<string, number>());
}

function DevicesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { showError, showSuccess } = useToast();
  const canManageDevices = hasPermission(user?.role, 'manage_devices');

  const [statusFilter, setStatusFilter] = useState<DeviceFilter>('all');
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingDevice, setEditingDevice] = useState<Device | null>(null);
  const [formState, setFormState] = useState<DeviceFormState>(defaultFormState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deletingDeviceId, setDeletingDeviceId] = useState<string | null>(null);

  const {
    data: devices,
    isLoading,
    isError,
    error,
    refetch,
  } = useDevices(statusFilter === 'all' ? undefined : { status: statusFilter });

  const { data: shipments } = useShipments();

  const shipmentCountByDevice = useMemo(() => buildShipmentCountMap(shipments), [shipments]);

  const title = useMemo(
    () => (editingDevice ? `Edit Device ${editingDevice.device_uid}` : 'Add Device'),
    [editingDevice],
  );

  const closeForm = () => {
    setIsFormOpen(false);
    setEditingDevice(null);
    setFormState(defaultFormState);
  };

  const openCreateForm = () => {
    setEditingDevice(null);
    setFormState(defaultFormState);
    setIsFormOpen(true);
  };

  const openEditForm = (device: Device) => {
    setEditingDevice(device);
    setFormState({
      device_uid: device.device_uid,
      model: device.model,
      firmware_version: device.firmware_version,
      battery_capacity_mAh: device.battery_capacity_mAh === null ? '' : String(device.battery_capacity_mAh),
      status: device.status,
    });
    setIsFormOpen(true);
  };

  const refreshDeviceLists = async () => {
    await queryClient.invalidateQueries({ queryKey: ['devices'] });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);

    try {
      if (editingDevice) {
        await updateDevice(editingDevice.id, toUpdatePayload(formState));
        showSuccess(`Device ${editingDevice.device_uid} updated.`);
      } else {
        const created = await createDevice(toCreatePayload(formState));
        showSuccess(`Device ${created.device_uid} created.`);
      }

      await refreshDeviceLists();
      closeForm();
    } catch (submitError) {
      if (getHttpStatus(submitError) !== 403) {
        showError(getErrorMessage(submitError, 'Device operation failed.'));
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (device: Device) => {
    if (!window.confirm(`Delete device ${device.device_uid}?`)) {
      return;
    }

    setDeletingDeviceId(device.id);
    try {
      await deleteDevice(device.id);
      showSuccess(`Device ${device.device_uid} deleted.`);
      if (editingDevice?.id === device.id) {
        closeForm();
      }
      await refreshDeviceLists();
    } catch (deleteError) {
      if (getHttpStatus(deleteError) !== 403) {
        showError(getErrorMessage(deleteError, 'Unable to delete device.'));
      }
    } finally {
      setDeletingDeviceId(null);
    }
  };

  if (isLoading) {
    return <LoadingState message="Loading devices..." />;
  }

  if (isError) {
    return (
      <ErrorState
        message={getErrorMessage(error, 'Failed to load devices.')}
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-100">Devices</h1>
            <p className="mt-1 text-sm text-slate-400">
              Clean operational overview of hardware health, status and linked shipments.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm text-slate-300" htmlFor="device-status-filter">
              Status
            </label>
            <select
              id="device-status-filter"
              className="input-field min-w-40 py-2"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as DeviceFilter)}
            >
              {FILTER_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option === 'all' ? 'All' : option.replace('_', ' ')}
                </option>
              ))}
            </select>
            {canManageDevices && (
              <button type="button" className="btn-primary" onClick={openCreateForm}>
                Add Device
              </button>
            )}
          </div>
        </div>
      </section>

      {isFormOpen && canManageDevices && (
        <section className="panel animate-fade-up p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
            <button type="button" className="btn-secondary px-3 py-2 text-sm" onClick={closeForm}>
              Cancel
            </button>
          </div>

          <form className="grid gap-4 md:grid-cols-2" onSubmit={handleSubmit}>
            <div className="space-y-1 md:col-span-2">
              <label htmlFor="device_uid" className="text-sm text-slate-300">
                Device UID
              </label>
              <input
                id="device_uid"
                type="text"
                className="input-field"
                value={formState.device_uid}
                onChange={(event) => setFormState((prev) => ({ ...prev, device_uid: event.target.value }))}
                disabled={Boolean(editingDevice)}
                required
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="device_model" className="text-sm text-slate-300">
                Model
              </label>
              <input
                id="device_model"
                type="text"
                className="input-field"
                value={formState.model}
                onChange={(event) => setFormState((prev) => ({ ...prev, model: event.target.value }))}
                required
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="device_firmware" className="text-sm text-slate-300">
                Firmware Version
              </label>
              <input
                id="device_firmware"
                type="text"
                className="input-field"
                value={formState.firmware_version}
                onChange={(event) => setFormState((prev) => ({ ...prev, firmware_version: event.target.value }))}
                required
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="device_battery" className="text-sm text-slate-300">
                Battery Capacity (mAh)
              </label>
              <input
                id="device_battery"
                type="number"
                min={0}
                className="input-field"
                value={formState.battery_capacity_mAh}
                onChange={(event) => setFormState((prev) => ({ ...prev, battery_capacity_mAh: event.target.value }))}
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="device_status" className="text-sm text-slate-300">
                Status
              </label>
              <select
                id="device_status"
                className="input-field"
                value={formState.status}
                onChange={(event) => setFormState((prev) => ({ ...prev, status: event.target.value as DeviceStatus }))}
                required
              >
                <option value="active">active</option>
                <option value="inactive">inactive</option>
                <option value="maintenance">maintenance</option>
              </select>
            </div>

            <button type="submit" className="btn-primary md:col-span-2" disabled={isSubmitting}>
              {isSubmitting ? 'Saving...' : editingDevice ? 'Update Device' : 'Create Device'}
            </button>
          </form>
        </section>
      )}

      {!devices || devices.length === 0 ? (
        <EmptyState
          title="No devices found"
          description="No devices match the selected filter."
          action={
            canManageDevices ? (
              <button type="button" className="btn-primary" onClick={openCreateForm}>
                Add Device
              </button>
            ) : null
          }
        />
      ) : (
        <motion.section
          initial="hidden"
          animate="visible"
          variants={{
            hidden: { opacity: 0 },
            visible: {
              opacity: 1,
              transition: { staggerChildren: 0.05 },
            },
          }}
          className="grid gap-4 xl:grid-cols-2"
        >
          {devices.map((device) => (
            <motion.div key={device.id} variants={{ hidden: { opacity: 0, y: 8 }, visible: { opacity: 1, y: 0 } }}>
              <DeviceCard
                device={device}
                linkedShipmentCount={shipmentCountByDevice.get(device.id) ?? 0}
                onOpen={(id) => navigate(`/devices/${id}`)}
                onEdit={canManageDevices ? openEditForm : undefined}
                onDelete={canManageDevices ? (target) => void handleDelete(target) : undefined}
                deleting={deletingDeviceId === device.id}
              />
            </motion.div>
          ))}
        </motion.section>
      )}
    </div>
  );
}

export default DevicesPage;
