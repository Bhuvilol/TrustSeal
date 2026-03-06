import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, Droplets, Thermometer, Waves } from 'lucide-react';
import EmptyState from '@/components/EmptyState';
import ErrorState from '@/components/ErrorState';
import LoadingState from '@/components/LoadingState';
import { useShipmentTelemetry, useShipments } from '@/hooks/useShipments';
import type { TelemetryEvent } from '@/types';
import { getErrorMessage } from '@/utils/errors';

type EventTypeFilter = 'all' | 'temperature' | 'shock' | 'humidity' | 'system';
type DeviceLogSeverity = 'info' | 'warning' | 'critical';
type SeverityFilter = 'all' | DeviceLogSeverity;

interface DeviceLogRow {
  id: string;
  shipmentId: string;
  shipmentCode: string;
  timestamp: string;
  eventType: EventTypeFilter;
  severity: DeviceLogSeverity;
  title: string;
  description: string;
}

function getSeverity(log: TelemetryEvent): DeviceLogSeverity {
  const critical = (log.temperature_c ?? -999) > 8 || (log.shock_g ?? -999) > 2.2;
  const warning =
    (log.temperature_c ?? -999) > 7.4 ||
    (log.shock_g ?? -999) > 1.5 ||
    (log.humidity_pct ?? -999) > 75 ||
    (log.tilt_deg ?? -999) > 24;
  if (critical) {
    return 'critical';
  }
  if (warning) {
    return 'warning';
  }
  return 'info';
}

function detectEventType(log: TelemetryEvent): EventTypeFilter {
  if (log.shock_g !== null && log.shock_g !== undefined) {
    return 'shock';
  }
  if (log.temperature_c !== null && log.temperature_c !== undefined) {
    return 'temperature';
  }
  if (log.humidity_pct !== null && log.humidity_pct !== undefined) {
    return 'humidity';
  }
  return 'system';
}

function buildDescription(log: TelemetryEvent): string {
  const parts: string[] = [];
  if (log.temperature_c !== null && log.temperature_c !== undefined) {
    parts.push(`Temp ${log.temperature_c.toFixed(1)} C`);
  }
  if (log.humidity_pct !== null && log.humidity_pct !== undefined) {
    parts.push(`Humidity ${log.humidity_pct.toFixed(1)}%`);
  }
  if (log.shock_g !== null && log.shock_g !== undefined) {
    parts.push(`Shock ${log.shock_g.toFixed(2)} g`);
  }
  if (log.tilt_deg !== null && log.tilt_deg !== undefined) {
    parts.push(`Tilt ${log.tilt_deg.toFixed(1)} deg`);
  }
  return parts.length > 0 ? parts.join(' | ') : 'Telemetry event recorded.';
}

function getSeverityClasses(severity: DeviceLogSeverity): string {
  if (severity === 'critical') {
    return 'border-red-300/45 bg-red-500/15 text-red-100';
  }
  if (severity === 'warning') {
    return 'border-amber-300/45 bg-amber-500/15 text-amber-100';
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
  return Thermometer;
}

function DeviceLogsPage() {
  const [searchParams] = useSearchParams();
  const initialShipmentId = searchParams.get('shipment_id') ?? 'all';
  const [shipmentFilter, setShipmentFilter] = useState<string>(initialShipmentId);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all');
  const [eventTypeFilter, setEventTypeFilter] = useState<EventTypeFilter>('all');

  const { data: shipments, isLoading: shipmentsLoading, isError: shipmentsError, error: shipmentsErrObj, refetch: refetchShipments } =
    useShipments();
  const selectedShipment = useMemo(
    () => (shipments ?? []).find((shipment) => shipment.id === shipmentFilter),
    [shipments, shipmentFilter],
  );
  const {
    data: telemetry,
    isLoading: telemetryLoading,
    isError: telemetryError,
    error: telemetryErrObj,
    refetch: refetchTelemetry,
  } = useShipmentTelemetry(selectedShipment?.id, { limit: 500 });

  const logs = useMemo<DeviceLogRow[]>(() => {
    if (!selectedShipment || !telemetry) {
      return [];
    }
    return telemetry
      .map((log) => {
        const eventType = detectEventType(log);
        const severity = getSeverity(log);
        return {
          id: log.event_id,
          shipmentId: selectedShipment.id,
          shipmentCode: selectedShipment.shipment_code,
          timestamp: log.ts,
          eventType,
          severity,
          title: `${eventType.toUpperCase()} telemetry`,
          description: buildDescription(log),
        };
      })
      .sort((left, right) => right.timestamp.localeCompare(left.timestamp));
  }, [selectedShipment, telemetry]);

  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      const matchesSeverity = severityFilter === 'all' || log.severity === severityFilter;
      const matchesType = eventTypeFilter === 'all' || log.eventType === eventTypeFilter;
      return matchesSeverity && matchesType;
    });
  }, [eventTypeFilter, logs, severityFilter]);

  if (shipmentsLoading) {
    return <LoadingState message="Loading shipment logs..." />;
  }

  if (shipmentsError) {
    return (
      <ErrorState
        message={getErrorMessage(shipmentsErrObj, 'Unable to load shipments.')}
        onRetry={() => void refetchShipments()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="panel p-5">
        <h1 className="text-2xl font-semibold text-slate-100">Device Logs</h1>
        <p className="mt-1 text-sm text-slate-400">Real telemetry-derived event stream from shipment data.</p>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div>
            <label htmlFor="log-shipment-filter" className="text-xs uppercase tracking-[0.14em] text-slate-400">
              Shipment
            </label>
            <select
              id="log-shipment-filter"
              className="input-field mt-2 py-2"
              value={shipmentFilter}
              onChange={(event) => setShipmentFilter(event.target.value)}
            >
              <option value="all">Select shipment</option>
              {(shipments ?? []).map((shipment) => (
                <option key={shipment.id} value={shipment.id}>
                  {shipment.shipment_code}
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

      {!selectedShipment ? (
        <EmptyState title="Select a shipment" description="Choose a shipment to view real telemetry logs." />
      ) : telemetryLoading ? (
        <LoadingState message="Loading telemetry logs..." />
      ) : telemetryError ? (
        <ErrorState
          message={getErrorMessage(telemetryErrObj, 'Unable to load telemetry logs.')}
          onRetry={() => void refetchTelemetry()}
        />
      ) : filteredLogs.length === 0 ? (
        <EmptyState title="No logs found" description="No telemetry events match the selected filters." />
      ) : (
        <section className="panel p-4">
          <div className="mb-3 text-xs uppercase tracking-[0.14em] text-slate-400">
            Shipment {selectedShipment.shipment_code}
          </div>
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
                    className={`rounded-2xl border bg-slate-900/35 p-4 ${
                      log.severity === 'critical' ? 'border-red-300/35' : 'border-white/10'
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex items-start gap-3">
                        <div className="rounded-xl border border-white/10 bg-white/5 p-2">
                          <EventIcon className="h-4 w-4 text-cyan-200" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-slate-100">{log.title}</p>
                          <p className="text-xs text-slate-300">Shipment {log.shipmentCode}</p>
                          <p className="mt-1 text-sm text-slate-300">{log.description}</p>
                          <p className="mt-1 text-xs text-slate-400">{new Date(log.timestamp).toLocaleString()}</p>
                        </div>
                      </div>

                      <span
                        className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.1em] ${getSeverityClasses(log.severity)}`}
                      >
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
