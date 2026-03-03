import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, Cpu, Droplets, Thermometer, Waves } from 'lucide-react';
import EmptyState from '@/components/EmptyState';
import ErrorState from '@/components/ErrorState';
import LoadingState from '@/components/LoadingState';
import { useDevices } from '@/hooks/useDevices';
import { buildDeviceIntelligence, type DeviceLogEntry, type DeviceLogSeverity } from '@/utils/device-intelligence';
import { getErrorMessage } from '@/utils/errors';

type EventTypeFilter = 'all' | 'temperature' | 'shock' | 'humidity' | 'system';
type SeverityFilter = 'all' | DeviceLogSeverity;

interface DeviceLogRow extends DeviceLogEntry {
  deviceId: string;
  deviceName: string;
  deviceUid: string;
  eventType: EventTypeFilter;
}

function detectEventType(log: DeviceLogEntry): EventTypeFilter {
  const text = `${log.type} ${log.description}`.toLowerCase();
  if (log.category === 'system') {
    return 'system';
  }
  if (text.includes('temp')) {
    return 'temperature';
  }
  if (text.includes('humidity')) {
    return 'humidity';
  }
  if (text.includes('shock') || text.includes('accelerometer') || text.includes('tilt')) {
    return 'shock';
  }
  return 'system';
}

function getSeverityClasses(severity: DeviceLogSeverity): string {
  if (severity === 'critical') {
    return 'border-red-300/45 bg-red-500/15 text-red-100 shadow-[0_0_18px_rgba(239,68,68,0.22)]';
  }
  if (severity === 'warning') {
    return 'border-amber-300/45 bg-amber-500/15 text-amber-100 shadow-[0_0_16px_rgba(245,158,11,0.18)]';
  }
  return 'border-cyan-300/45 bg-cyan-500/15 text-cyan-100';
}

function getEventIcon(eventType: EventTypeFilter) {
  if (eventType === 'temperature') {
    return Thermometer;
  }
  if (eventType === 'humidity') {
    return Droplets;
  }
  if (eventType === 'shock') {
    return Waves;
  }
  return Cpu;
}

function DeviceLogsPage() {
  const [searchParams] = useSearchParams();
  const initialDeviceId = searchParams.get('device_id') ?? 'all';
  const [deviceFilter, setDeviceFilter] = useState<string>(initialDeviceId);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all');
  const [eventTypeFilter, setEventTypeFilter] = useState<EventTypeFilter>('all');
  const { data: devices, isLoading, isError, error, refetch } = useDevices();

  const logs = useMemo<DeviceLogRow[]>(() => {
    return (devices ?? [])
      .flatMap((device) => {
        const snapshot = buildDeviceIntelligence(device);
        return snapshot.logs.map((log) => ({
          ...log,
          deviceId: device.id,
          deviceName: device.model,
          deviceUid: device.device_uid,
          eventType: detectEventType(log),
        }));
      })
      .sort((left, right) => right.timestamp.localeCompare(left.timestamp));
  }, [devices]);

  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      const matchesDevice = deviceFilter === 'all' || log.deviceId === deviceFilter;
      const matchesSeverity = severityFilter === 'all' || log.severity === severityFilter;
      const matchesType = eventTypeFilter === 'all' || log.eventType === eventTypeFilter;
      return matchesDevice && matchesSeverity && matchesType;
    });
  }, [deviceFilter, severityFilter, eventTypeFilter, logs]);

  if (isLoading) {
    return <LoadingState message="Loading device logs..." />;
  }

  if (isError) {
    return (
      <ErrorState
        message={getErrorMessage(error, 'Unable to load device logs.')}
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="panel p-5">
        <h1 className="text-2xl font-semibold text-slate-100">Device Logs</h1>
        <p className="mt-1 text-sm text-slate-400">
          Centralized event stream across all devices with operational severity filtering.
        </p>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div>
            <label htmlFor="log-device-filter" className="text-xs uppercase tracking-[0.14em] text-slate-400">
              Device
            </label>
            <select
              id="log-device-filter"
              className="input-field mt-2 py-2"
              value={deviceFilter}
              onChange={(event) => setDeviceFilter(event.target.value)}
            >
              <option value="all">All devices</option>
              {(devices ?? []).map((device) => (
                <option key={device.id} value={device.id}>
                  {device.device_uid}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="log-severity-filter" className="text-xs uppercase tracking-[0.14em] text-slate-400">
              Severity
            </label>
            <select
              id="log-severity-filter"
              className="input-field mt-2 py-2"
              value={severityFilter}
              onChange={(event) => setSeverityFilter(event.target.value as SeverityFilter)}
            >
              <option value="all">All</option>
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          </div>

          <div>
            <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Event Type</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(['all', 'temperature', 'shock', 'humidity', 'system'] as EventTypeFilter[]).map((type) => (
                <button
                  key={type}
                  type="button"
                  className={`rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.1em] transition ${
                    eventTypeFilter === type
                      ? 'border-cyan-300/55 bg-cyan-400/20 text-cyan-100'
                      : 'border-white/10 bg-white/5 text-slate-300 hover:border-cyan-200/35'
                  }`}
                  onClick={() => setEventTypeFilter(type)}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {filteredLogs.length === 0 ? (
        <EmptyState
          title="No logs found"
          description="No events match the selected filters."
        />
      ) : (
        <section className="panel p-4">
          <div className="max-h-[72vh] space-y-3 overflow-y-auto pr-1">
            <AnimatePresence initial={false}>
              {filteredLogs.map((log) => {
                const EventIcon = getEventIcon(log.eventType);
                return (
                  <motion.article
                    key={log.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 8 }}
                    className={`rounded-2xl border bg-slate-900/35 p-4 ${log.severity === 'critical' ? 'animate-critical-shake border-red-300/35' : 'border-white/10'}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex items-start gap-3">
                        <div className="rounded-xl border border-white/10 bg-white/5 p-2">
                          <EventIcon className="h-4 w-4 text-cyan-200" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-slate-100">{log.type}</p>
                          <p className="text-xs text-slate-300">{log.deviceName} ({log.deviceUid})</p>
                          <p className="mt-1 text-sm text-slate-300">{log.description}</p>
                          <p className="mt-1 text-xs text-slate-400">
                            {new Date(log.timestamp).toLocaleString()}
                          </p>
                        </div>
                      </div>

                      <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.1em] ${getSeverityClasses(log.severity)}`}>
                        {log.severity === 'critical' && <AlertTriangle className="h-3.5 w-3.5" />}
                        {log.severity}
                      </span>
                    </div>
                  </motion.article>
                );
              })}
            </AnimatePresence>
          </div>
        </section>
      )}
    </div>
  );
}

export default DeviceLogsPage;
