import { useEffect, useMemo, useRef, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import MapView, { Layer, MapRef, Marker, NavigationControl, Popup, Source, type ViewState } from 'react-map-gl/maplibre';
import type { LayerProps } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import clsx from 'clsx';
import { motion } from 'framer-motion';
import { Route, Wifi, Zap } from 'lucide-react';
import type { EChartsOption } from 'echarts';
import type { ShipmentLeg, ShipmentStatus, TelemetryEvent } from '@/types';
import { formatDateTime, formatNumber } from '@/utils/format';
import { getStoredToken } from '@/utils/token';

type RealtimeStatus = 'connecting' | 'live' | 'reconnecting' | 'offline';
type RangeMode = '10m' | '1h' | 'full';

const MAP_STYLE_URL = String(
  import.meta.env.VITE_MAP_STYLE_URL || 'https://demotiles.maplibre.org/style.json',
);
const MAX_POINTS = 2000;
const RANGE_MS = { '10m': 10 * 60 * 1000, '1h': 60 * 60 * 1000 } as const;

interface LiveTelemetryModuleProps {
  shipmentId: string;
  initialTelemetry: TelemetryEvent[];
  maxPoints?: number;
  legs?: ShipmentLeg[];
  origin?: string;
  destination?: string;
  status?: ShipmentStatus;
}

const historyLayer: LayerProps = {
  id: 'history',
  type: 'line',
  paint: { 'line-color': '#10b981', 'line-width': 4, 'line-opacity': 0.9 },
};

const activeLayer: LayerProps = {
  id: 'active',
  type: 'line',
  paint: { 'line-color': '#38bdf8', 'line-width': 4, 'line-opacity': 0.95 },
};

function parseTime(value: string): number {
  const t = new Date(value).getTime();
  return Number.isNaN(t) ? 0 : t;
}

function finiteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function buildWsUrl(shipmentId: string): string {
  const envWsBase = import.meta.env.VITE_WS_BASE_URL as string | undefined;
  const envBase = import.meta.env.VITE_API_BASE_URL as string | undefined;
  const fallbackApiBase = import.meta.env.DEV
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : 'https://trust-seal-1.onrender.com';
  const apiBase = String(envWsBase || envBase || fallbackApiBase).replace(/\/+$/, '').replace(/\/api\/v1$/i, '');
  const wsBase = apiBase.replace(/^http/i, 'ws');
  const tokenEnabled = String(import.meta.env.VITE_WS_SEND_TOKEN || 'false').toLowerCase() === 'true';
  const token = tokenEnabled ? getStoredToken() : null;
  const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : '';
  return `${wsBase}/api/v1/ws/shipments/${shipmentId}${tokenQuery}`;
}

function metricOption(title: string, unit: string, color: string, data: Array<[string, number]>): EChartsOption {
  return {
    animation: true,
    grid: { left: 42, right: 24, top: 36, bottom: 48 },
    tooltip: { trigger: 'axis', valueFormatter: (v) => `${formatNumber(Number(v))} ${unit}` },
    xAxis: { type: 'time', axisLabel: { color: '#94a3b8' }, splitLine: { show: false } },
    yAxis: {
      type: 'value',
      name: unit,
      scale: true,
      nameTextStyle: { color: '#94a3b8', padding: [0, 0, 0, 8] },
      axisLabel: { color: '#94a3b8' },
      splitLine: { lineStyle: { color: '#334155' } },
    },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 14, bottom: 8 }],
    series: [{ name: title, type: 'line', smooth: true, showSymbol: false, lineStyle: { width: 2.2, color }, areaStyle: { color: `${color}22` }, data }],
  };
}

function LiveTelemetryModule({
  shipmentId,
  initialTelemetry,
  maxPoints = MAX_POINTS,
  legs = [],
  origin,
  destination,
  status,
}: LiveTelemetryModuleProps) {
  const [telemetry, setTelemetry] = useState<TelemetryEvent[]>([...initialTelemetry].slice(-maxPoints));
  const [rangeMode, setRangeMode] = useState<RangeMode>('full');
  const [realtimeStatus, setRealtimeStatus] = useState<RealtimeStatus>('connecting');
  const [autoCenter, setAutoCenter] = useState(true);
  const [showHistory, setShowHistory] = useState(true);
  const [showPopup, setShowPopup] = useState(false);
  const [displayPoint, setDisplayPoint] = useState<{ latitude: number; longitude: number } | null>(null);
  const [viewState, setViewState] = useState<ViewState>({ latitude: 20, longitude: 0, zoom: 2.5, bearing: 0, pitch: 0, padding: { top: 0, right: 0, bottom: 0, left: 0 } });
  const mapRef = useRef<MapRef | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const rafRef = useRef<number | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const didInitialFitRef = useRef(false);
  const telemetryWsEnabled = String(import.meta.env.VITE_TELEMETRY_WS_ENABLED || 'false').toLowerCase() === 'true';

  useEffect(() => setTelemetry([...initialTelemetry].slice(-maxPoints)), [initialTelemetry, maxPoints]);

  useEffect(() => {
    if (!telemetryWsEnabled) {
      setRealtimeStatus('offline');
      return;
    }

    let unmounted = false;
    const clearReconnect = () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
    const connect = () => {
      if (unmounted) return;
      setRealtimeStatus(reconnectAttemptRef.current > 0 ? 'reconnecting' : 'connecting');
      const socket = new WebSocket(buildWsUrl(shipmentId));
      wsRef.current = socket;
      socket.onopen = () => {
        reconnectAttemptRef.current = 0;
        setRealtimeStatus('live');
      };
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as Record<string, unknown>;
          const eventName = String(payload.event || '');

          if (eventName === 'sensor_log.created') {
            const data = payload.data as Record<string, unknown> | undefined;
            const log = data?.log as Record<string, unknown> | undefined;
            if (!log) return;

            const latitude = finiteNumber(log.latitude) ? log.latitude : null;
            const longitude = finiteNumber(log.longitude) ? log.longitude : null;
            const recordedAt = String(log.recorded_at || new Date().toISOString());
            const entry: TelemetryEvent = {
              event_id: String(log.id || `ws-${shipmentId}-${recordedAt}-${Math.random().toString(16).slice(2, 8)}`),
              shipment_id: String(log.shipment_id || shipmentId),
              device_id: String(log.device_id || 'ws-device'),
              ts: recordedAt,
              seq_no: Number.isFinite(Number(log.seq_no)) ? Number(log.seq_no) : 0,
              temperature_c: finiteNumber(log.temperature) ? log.temperature : null,
              humidity_pct: finiteNumber(log.humidity) ? log.humidity : null,
              shock_g: finiteNumber(log.shock) ? log.shock : null,
              light_lux: null,
              tilt_deg: finiteNumber(log.tilt_angle) ? log.tilt_angle : null,
              battery_pct: null,
              network_type: null,
              firmware_version: null,
              gps: latitude !== null && longitude !== null ? {
                lat: latitude,
                lng: longitude,
                speed_kmh: finiteNumber(log.speed) ? log.speed : undefined,
                heading_deg: finiteNumber(log.heading) ? log.heading : undefined,
              } : null,
              bundle_id: null,
              payload_hash: String(log.hash_value || `ws-${Math.random().toString(16).slice(2, 10)}`),
              signature: null,
              verification_status: null,
              ingest_status: null,
              created_at: recordedAt,
            };

            setTelemetry((curr) => [...curr, entry].slice(-maxPoints));
            return;
          }

          if (eventName === 'telemetry-update') {
            const latitude = finiteNumber(payload.latitude) ? payload.latitude : null;
            const longitude = finiteNumber(payload.longitude) ? payload.longitude : null;
            if (latitude === null || longitude === null) return;

            const recordedAt = String(payload.timestamp || new Date().toISOString());
            const entry: TelemetryEvent = {
              event_id: `ws-${shipmentId}-${recordedAt}-${Math.random().toString(16).slice(2, 8)}`,
              shipment_id: String(payload.shipment_id || shipmentId),
              device_id: String(payload.device_id || 'ws-device'),
              ts: recordedAt,
              seq_no: 0,
              temperature_c: finiteNumber(payload.temperature) ? payload.temperature : null,
              humidity_pct: finiteNumber(payload.humidity) ? payload.humidity : null,
              shock_g: finiteNumber(payload.shock) ? payload.shock : null,
              light_lux: null,
              tilt_deg: finiteNumber(payload.tilt_angle) ? payload.tilt_angle : null,
              battery_pct: null,
              network_type: null,
              firmware_version: null,
              gps: {
                lat: latitude,
                lng: longitude,
                speed_kmh: finiteNumber(payload.speed) ? payload.speed : undefined,
                heading_deg: finiteNumber(payload.heading) ? payload.heading : undefined,
              },
              bundle_id: null,
              payload_hash: `ws-${Math.random().toString(16).slice(2, 10)}`,
              signature: null,
              verification_status: null,
              ingest_status: null,
              created_at: recordedAt,
            };

            setTelemetry((curr) => [...curr, entry].slice(-maxPoints));
          }
        } catch {
          // ignore malformed events
        }
      };
      socket.onerror = () => socket.close();
      socket.onclose = () => {
        if (unmounted) return;
        reconnectAttemptRef.current += 1;
        setRealtimeStatus('reconnecting');
        clearReconnect();
        reconnectTimerRef.current = window.setTimeout(connect, Math.min(10000, reconnectAttemptRef.current * 1000));
      };
    };
    connect();
    return () => {
      unmounted = true;
      clearReconnect();
      if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) wsRef.current.close();
    };
  }, [shipmentId, maxPoints, telemetryWsEnabled]);

  const routePoints = useMemo(
    () => telemetry.filter((x) => finiteNumber(x.gps?.lat) && finiteNumber(x.gps?.lng)),
    [telemetry],
  );
  const hasTelemetryRecords = telemetry.length > 0;
  const latest = routePoints.at(-1) ?? null;
  const start = routePoints[0] ?? null;
  const startOverlapsCurrent =
    !!start &&
    !!latest &&
    Math.abs((start.gps?.lat as number) - (latest.gps?.lat as number)) < 1e-5 &&
    Math.abs((start.gps?.lng as number) - (latest.gps?.lng as number)) < 1e-5;

  useEffect(() => {
    if (!routePoints.length || displayPoint) return;
    setDisplayPoint({ latitude: routePoints[0].gps?.lat as number, longitude: routePoints[0].gps?.lng as number });
  }, [routePoints, displayPoint]);

  useEffect(() => {
    if (!latest) return;
    const from = displayPoint ?? { latitude: latest.gps?.lat as number, longitude: latest.gps?.lng as number };
    const to = { latitude: latest.gps?.lat as number, longitude: latest.gps?.lng as number };
    const startTime = performance.now();
    if (rafRef.current !== null) window.cancelAnimationFrame(rafRef.current);
    const animate = (now: number) => {
      const p = Math.min(1, (now - startTime) / 1400);
      const eased = 1 - (1 - p) * (1 - p);
      setDisplayPoint({ latitude: from.latitude + (to.latitude - from.latitude) * eased, longitude: from.longitude + (to.longitude - from.longitude) * eased });
      if (p < 1) rafRef.current = window.requestAnimationFrame(animate);
    };
    rafRef.current = window.requestAnimationFrame(animate);
    return () => {
      if (rafRef.current !== null) window.cancelAnimationFrame(rafRef.current);
    };
  }, [latest?.gps?.lat, latest?.gps?.lng]);

  const displayCoords = useMemo(() => {
    if (!displayPoint || routePoints.length === 0) return [];
    const base = routePoints.slice(0, -1).map((p) => [p.gps?.lng as number, p.gps?.lat as number]);
    return [...base, [displayPoint.longitude, displayPoint.latitude]];
  }, [displayPoint, routePoints]);
  const historyCoords = displayCoords.length > 1 ? displayCoords.slice(0, -1) : [];
  const activeCoords = displayCoords.length > 1 ? displayCoords.slice(-2) : [];

  const fitToRoute = () => {
    if (!mapRef.current || !displayCoords.length) return;
    if (displayCoords.length === 1) {
      mapRef.current.easeTo({ center: displayCoords[0] as [number, number], zoom: 8, duration: 800 });
      return;
    }
    const lons = displayCoords.map((p) => p[0]);
    const lats = displayCoords.map((p) => p[1]);
    mapRef.current.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 48, duration: 900 });
  };

  useEffect(() => {
    if (!mapRef.current || !displayCoords.length || didInitialFitRef.current) return;
    fitToRoute();
    didInitialFitRef.current = true;
  }, [displayCoords.length]);

  useEffect(() => {
    if (!autoCenter || !displayPoint || !mapRef.current) return;
    mapRef.current.easeTo({ center: [displayPoint.longitude, displayPoint.latitude], zoom: Math.max(viewState.zoom, 8), duration: 600 });
  }, [autoCenter, displayPoint, viewState.zoom]);

  const windowed = useMemo(() => {
    if (rangeMode === 'full') return telemetry;
    const latestLog = telemetry.at(-1);
    const end = parseTime(latestLog?.ts || new Date().toISOString());
    const startMs = end - RANGE_MS[rangeMode];
    return telemetry.filter((row) => parseTime(row.ts) >= startMs);
  }, [telemetry, rangeMode]);

  const tempData = windowed.filter((x) => finiteNumber(x.temperature_c)).map((x) => [x.ts, x.temperature_c as number] as [string, number]);
  const humData = windowed.filter((x) => finiteNumber(x.humidity_pct)).map((x) => [x.ts, x.humidity_pct as number] as [string, number]);
  const shockData = windowed.filter((x) => finiteNumber(x.shock_g)).map((x) => [x.ts, x.shock_g as number] as [string, number]);
  const tiltData = windowed.filter((x) => finiteNumber(x.tilt_deg)).map((x) => [x.ts, x.tilt_deg as number] as [string, number]);
  const hasAnyMetricSamples = tempData.length > 0 || humData.length > 0 || shockData.length > 0 || tiltData.length > 0;
  const metricCards = [
    { key: 'temperature', label: 'Temperature', unit: 'C', color: '#f97316', data: tempData },
    { key: 'humidity', label: 'Humidity', unit: '%', color: '#38bdf8', data: humData },
    { key: 'shock', label: 'Shock', unit: 'g', color: '#f43f5e', data: shockData },
    { key: 'tilt', label: 'Tilt Angle', unit: 'deg', color: '#facc15', data: tiltData },
  ] as const;

  return (
    <section className="space-y-5">
      <article className="panel p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-slate-100">Live Tracking</h3>
            <p className="mt-1 text-sm text-slate-400">Realtime shipment position and route replay.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className={clsx('rounded-full border px-3 py-1 text-xs font-semibold', realtimeStatus === 'live' ? 'border-status-green/40 bg-status-green/15 text-status-green' : realtimeStatus === 'reconnecting' ? 'border-status-yellow/40 bg-status-yellow/15 text-status-yellow' : 'border-slate-600 bg-surface-700/70 text-slate-300')}>{realtimeStatus === 'live' ? 'LIVE' : realtimeStatus === 'reconnecting' ? 'Reconnecting...' : realtimeStatus === 'connecting' ? 'Connecting...' : 'Offline'}</span>
            <label className="inline-flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={autoCenter} onChange={(e) => setAutoCenter(e.target.checked)} /> Auto-center</label>
            <label className="inline-flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={showHistory} onChange={(e) => setShowHistory(e.target.checked)} /> Show route history</label>
            <button type="button" className="btn-secondary px-3 py-1.5 text-xs" onClick={fitToRoute}>Fit to Route</button>
          </div>
        </div>
        <div className="mb-4 flex flex-wrap gap-2 text-xs text-slate-300">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1"><Wifi className="h-3.5 w-3.5 text-cyan-200" /><span className="font-semibold text-slate-100">1</span><span className="text-slate-400">Devices linked</span></span>
          <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1"><Route className="h-3.5 w-3.5 text-cyan-200" /><span className="font-semibold text-slate-100">On-chain</span><span className="text-slate-400">Custody hash</span></span>
          <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1"><Zap className="h-3.5 w-3.5 text-cyan-200" /><span className="font-semibold text-slate-100">Active</span><span className="text-slate-400">AI monitor</span></span>
        </div>
        {!routePoints.length ? (
          <div className="rounded-xl border border-slate-700/70 bg-surface-800/60 px-4 py-5 text-sm text-slate-400"><div className="flex items-center gap-3"><span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-500 border-t-brand-300" /><span>{hasTelemetryRecords ? 'Telemetry found, but no GPS coordinates are present for map plotting.' : realtimeStatus === 'live' ? 'Waiting for live tracking data...' : 'Connecting to telemetry stream...'}</span></div></div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
            <div className="relative h-[460px] overflow-hidden rounded-xl border border-slate-700/70">
              <MapView ref={mapRef} mapStyle={MAP_STYLE_URL} {...viewState} onMove={(e) => setViewState(e.viewState)} dragRotate={false} scrollZoom dragPan>
                <NavigationControl position="top-right" />
                {showHistory && historyCoords.length > 1 && <Source id="history-src" type="geojson" data={{ type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'LineString', coordinates: historyCoords }, properties: {} }] }}><Layer {...historyLayer} /></Source>}
                {activeCoords.length > 1 && <Source id="active-src" type="geojson" data={{ type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'LineString', coordinates: activeCoords }, properties: {} }] }}><Layer {...activeLayer} /></Source>}
                {start && <Marker longitude={start.gps?.lng as number} latitude={start.gps?.lat as number} anchor="bottom"><motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center gap-1" style={startOverlapsCurrent ? { transform: 'translateY(-12px)' } : undefined}><div className="rounded-full bg-emerald-500/95 px-2 py-1 text-[10px] font-semibold text-white">Start</div><div className="relative h-3 w-3"><span className="absolute inset-0 rounded-full border-2 border-white bg-emerald-500" /><span className="absolute inset-0 -m-2 animate-ping rounded-full bg-emerald-400/25" /></div></motion.div></Marker>}
                {latest && <Marker longitude={latest.gps?.lng as number} latitude={latest.gps?.lat as number} anchor="bottom"><motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center gap-1"><div className="rounded-full bg-rose-500/95 px-2 py-1 text-[10px] font-semibold text-white">Destination</div><div className="h-3 w-3 rounded-full border-2 border-white bg-rose-500" /></motion.div></Marker>}
                {displayPoint && <Marker longitude={displayPoint.longitude} latitude={displayPoint.latitude} anchor="center"><button type="button" onClick={() => setShowPopup(true)} className="relative h-5 w-5 rounded-full border-2 border-white bg-sky-500 ring-2 ring-sky-300/50"><span className="absolute inset-0 -m-2 animate-ping rounded-full bg-sky-400/25" /></button></Marker>}
                {showPopup && latest && <Popup longitude={latest.gps?.lng as number} latitude={latest.gps?.lat as number} anchor="top" onClose={() => setShowPopup(false)} closeOnClick={false}><div className="space-y-1 text-xs"><p>Latitude: <span className="font-semibold">{formatNumber(latest.gps?.lat as number, 5)}</span></p><p>Longitude: <span className="font-semibold">{formatNumber(latest.gps?.lng as number, 5)}</span></p><p>Temperature: {formatNumber(latest.temperature_c)} degC</p><p>{formatDateTime(latest.ts)}</p></div></Popup>}
                <div className="pointer-events-none absolute left-3 top-3"><div className="pointer-events-auto flex items-center gap-2 rounded-lg bg-surface-900/80 px-3 py-2 ring-1 ring-slate-700/70"><button type="button" className="btn-secondary px-3 py-1 text-xs" onClick={() => displayPoint && mapRef.current?.easeTo({ center: [displayPoint.longitude, displayPoint.latitude], zoom: 11, duration: 600 })}>Zoom to current</button><button type="button" className="btn-secondary px-3 py-1 text-xs" onClick={fitToRoute}>Fit to Route</button></div></div>
              </MapView>
            </div>
            <div className="rounded-xl border border-slate-700/70 bg-surface-800/70 p-4 text-sm text-slate-200">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Live Summary</p>
              <div className="mt-3 space-y-3">
                <div className="flex items-center justify-between"><span className="text-slate-400">Current leg</span><span className="font-semibold">{(legs.find((x) => x.status === 'in_progress') || legs.at(-1)) ? `Leg ${(legs.find((x) => x.status === 'in_progress') || legs.at(-1))?.leg_number}` : 'N/A'}</span></div>
                <div className="flex items-center justify-between"><span className="text-slate-400">Shipment status</span><span className="font-semibold">{status ?? 'N/A'}</span></div>
                <div className="flex items-center justify-between"><span className="text-slate-400">Last update</span><span className="font-semibold">{latest ? formatDateTime(latest.ts) : 'Awaiting data'}</span></div>
                <div className="rounded-lg border border-slate-700/70 bg-surface-900/80 p-3 text-xs text-slate-300"><p className="font-semibold text-slate-100">Origin to Destination</p><p className="mt-1">{origin || 'Unknown'} to {destination || 'Unknown'}</p></div>
                {!!legs.length && <div className="space-y-2 text-xs text-slate-300"><p className="font-semibold text-slate-100">Shipment legs</p><div className="flex flex-wrap gap-2">{legs.map((leg) => <span key={leg.id} className={clsx('rounded-full px-3 py-1', leg.status === 'settled' ? 'bg-emerald-400/20 text-emerald-100' : leg.status === 'in_progress' ? 'bg-sky-400/20 text-sky-100' : 'bg-slate-500/20 text-slate-200')}>Leg {leg.leg_number}: {leg.from_location} to {leg.to_location}</span>)}</div></div>}
              </div>
            </div>
          </div>
        )}
      </article>
      <article className="panel p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div><h3 className="text-lg font-semibold text-slate-100">Telemetry Graphs</h3><p className="mt-1 text-sm text-slate-400">Live temperature, humidity, shock and tilt metrics.</p></div>
          <div className="flex flex-wrap gap-2">{(['10m', '1h', 'full'] as const).map((mode) => <button key={mode} type="button" className={mode === rangeMode ? 'btn-primary px-3 py-1.5 text-xs' : 'btn-secondary px-3 py-1.5 text-xs'} onClick={() => setRangeMode(mode)}>{mode === '10m' ? 'Last 10 min' : mode === '1h' ? 'Last 1 hour' : 'Full Journey'}</button>)}</div>
        </div>
        {!windowed.length ? <p className="rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">No telemetry records available for selected range.</p> : !hasAnyMetricSamples ? <p className="rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">Telemetry rows are available, but numeric metric values are missing for the selected range.</p> : <div className="grid gap-4 xl:grid-cols-2">{metricCards.map((metric) => <div key={metric.key} className="panel-soft p-3"><div className="mb-2 flex items-center justify-between gap-2"><p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-300"><span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: metric.color }} />{metric.label}</p><span className="text-xs text-slate-400">{metric.data.length > 0 ? `Current: ${formatNumber(metric.data[metric.data.length - 1][1])} ${metric.unit}` : `No ${metric.label.toLowerCase()} data`}</span></div><ReactECharts option={metricOption(metric.label, metric.unit, metric.color, metric.data)} style={{ height: 280 }} notMerge lazyUpdate /></div>)}</div>}
      </article>
    </section>
  );
}

export default LiveTelemetryModule;


