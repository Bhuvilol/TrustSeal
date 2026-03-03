import type { Device } from '@/types';

export type TelemetryMetricKey = 'temperature' | 'humidity' | 'shock' | 'tilt';
export type DeviceRiskLevel = 'low' | 'medium' | 'high';
export type DeviceLogSeverity = 'info' | 'warning' | 'critical';
export type DeviceLogCategory = 'telemetry' | 'system';

export interface DeviceTelemetryPoint {
  label: string;
  timestamp: string;
  temperature: number;
  humidity: number;
  shock: number;
  tilt: number;
}

export interface DeviceMetricSummary {
  key: TelemetryMetricKey;
  label: string;
  unit: string;
  value: number;
  warningThreshold: number;
  criticalThreshold: number;
  trend: number[];
  isWarning: boolean;
  isCritical: boolean;
}

export interface DeviceLogEntry {
  id: string;
  type: string;
  description: string;
  timestamp: string;
  severity: DeviceLogSeverity;
  category: DeviceLogCategory;
}

export interface DeviceIntelligenceSnapshot {
  healthScore: number;
  batteryPercent: number;
  signalPercent: number;
  currentSpeedKmh: number;
  riskLevel: DeviceRiskLevel;
  hasRecentAnomaly: boolean;
  latestTimestamp: string;
  metrics: DeviceMetricSummary[];
  timeline: DeviceTelemetryPoint[];
  logs: DeviceLogEntry[];
}

export type DeviceOperationalStatus = 'active' | 'warning' | 'offline';

export interface DeviceOverviewSnapshot {
  batteryPercent: number;
  signalPercent: number;
  riskLevel: DeviceRiskLevel;
  operationalStatus: DeviceOperationalStatus;
}

function hashString(source: string): number {
  let hash = 0;
  for (let index = 0; index < source.length; index += 1) {
    hash = (hash << 5) - hash + source.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash);
}

function seededRandom(seed: number): () => number {
  let state = seed % 2147483647;
  if (state <= 0) {
    state += 2147483646;
  }

  return () => {
    state = (state * 16807) % 2147483647;
    return (state - 1) / 2147483646;
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function formatShortTimestamp(timestamp: Date): string {
  return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

const THRESHOLDS: Record<
  TelemetryMetricKey,
  { warning: number; critical: number; label: string; unit: string }
> = {
  temperature: { warning: 7.4, critical: 8, label: 'Temperature', unit: 'C' },
  humidity: { warning: 65, critical: 75, label: 'Humidity', unit: '%' },
  shock: { warning: 1.5, critical: 2.2, label: 'Shock', unit: 'g' },
  tilt: { warning: 24, critical: 34, label: 'Tilt', unit: 'deg' },
};

export function buildDeviceIntelligence(device: Device): DeviceIntelligenceSnapshot {
  const seed = hashString(device.id + device.device_uid + device.firmware_version);
  const random = seededRandom(seed);
  const now = Date.now();

  const baseTemp = device.status === 'active' ? 5.8 : device.status === 'maintenance' ? 7 : 4.8;
  const baseHumidity = device.status === 'active' ? 51 : device.status === 'maintenance' ? 63 : 47;
  const baseShock = device.status === 'active' ? 0.85 : device.status === 'maintenance' ? 1.3 : 0.52;
  const baseTilt = device.status === 'active' ? 8 : device.status === 'maintenance' ? 16 : 5;

  const timeline: DeviceTelemetryPoint[] = Array.from({ length: 22 }).map((_, index) => {
    const progress = index / 21;
    const jitter = (random() - 0.5) * 0.8;
    const timestamp = new Date(now - (21 - index) * 5 * 60 * 1000);

    const anomalyWindow = index > 17 && random() > 0.72;

    const temperature =
      baseTemp + Math.sin(progress * Math.PI * 2.5) * 0.9 + jitter + (anomalyWindow ? 1.9 : 0);
    const humidity =
      baseHumidity + Math.cos(progress * Math.PI * 2.1) * 6.2 + jitter * 4 + (anomalyWindow ? 8.6 : 0);
    const shock =
      baseShock + Math.abs(Math.sin(progress * Math.PI * 3.6)) * 0.9 + random() * 0.22 + (anomalyWindow ? 1.05 : 0);
    const tilt =
      baseTilt + Math.abs(Math.cos(progress * Math.PI * 2.4)) * 8.4 + random() * 2 + (anomalyWindow ? 10.8 : 0);

    return {
      label: formatShortTimestamp(timestamp),
      timestamp: timestamp.toISOString(),
      temperature: Number(temperature.toFixed(2)),
      humidity: Number(humidity.toFixed(2)),
      shock: Number(shock.toFixed(3)),
      tilt: Number(tilt.toFixed(2)),
    };
  });

  const latest = timeline[timeline.length - 1];

  const metrics: DeviceMetricSummary[] = (Object.keys(THRESHOLDS) as TelemetryMetricKey[]).map((key) => {
    const config = THRESHOLDS[key];
    const trend = timeline.map((point) => point[key]);
    const value = latest[key];

    return {
      key,
      label: config.label,
      unit: config.unit,
      value,
      warningThreshold: config.warning,
      criticalThreshold: config.critical,
      trend,
      isWarning: value > config.warning,
      isCritical: value > config.critical,
    };
  });

  const telemetryLogs: DeviceLogEntry[] = [];

  timeline.forEach((point, index) => {
    if (point.temperature > THRESHOLDS.temperature.critical) {
      telemetryLogs.push({
        id: `${device.id}-temp-critical-${index}`,
        type: 'Temperature threshold exceeded',
        description: `Temperature reached ${point.temperature.toFixed(1)} C. Cold-chain policy breached.`,
        timestamp: point.timestamp,
        severity: 'critical',
        category: 'telemetry',
      });
    } else if (point.temperature > THRESHOLDS.temperature.warning && random() > 0.55) {
      telemetryLogs.push({
        id: `${device.id}-temp-warning-${index}`,
        type: 'Temperature drift detected',
        description: `Temperature increased to ${point.temperature.toFixed(1)} C. Monitor cooling cycle.`,
        timestamp: point.timestamp,
        severity: 'warning',
        category: 'telemetry',
      });
    }

    if (point.shock > THRESHOLDS.shock.warning && random() > 0.58) {
      const severity: DeviceLogSeverity = point.shock > THRESHOLDS.shock.critical ? 'critical' : 'warning';
      telemetryLogs.push({
        id: `${device.id}-shock-${index}`,
        type: 'Shock event detected',
        description: `Accelerometer captured ${point.shock.toFixed(2)} g impact.`,
        timestamp: point.timestamp,
        severity,
        category: 'telemetry',
      });
    }

    if (point.humidity > THRESHOLDS.humidity.warning && random() > 0.62) {
      telemetryLogs.push({
        id: `${device.id}-humidity-${index}`,
        type: 'Humidity spike',
        description: `Humidity moved to ${point.humidity.toFixed(1)}%. Ventilation check recommended.`,
        timestamp: point.timestamp,
        severity: point.humidity > THRESHOLDS.humidity.critical ? 'critical' : 'warning',
        category: 'telemetry',
      });
    }

    if (point.tilt > THRESHOLDS.tilt.warning && random() > 0.66) {
      telemetryLogs.push({
        id: `${device.id}-tilt-${index}`,
        type: 'Accelerometer alert',
        description: `Tilt angle reached ${point.tilt.toFixed(1)} deg. Handling instability suspected.`,
        timestamp: point.timestamp,
        severity: point.tilt > THRESHOLDS.tilt.critical ? 'critical' : 'warning',
        category: 'telemetry',
      });
    }
  });

  const systemLogs: DeviceLogEntry[] = [
    {
      id: `${device.id}-restart`,
      type: 'Device restarted',
      description: 'Power cycle completed and telemetry stream resumed.',
      timestamp: new Date(now - (35 + Math.floor(random() * 30)) * 60 * 1000).toISOString(),
      severity: 'info',
      category: 'system',
    },
    {
      id: `${device.id}-firmware`,
      type: 'Firmware updated',
      description: `Firmware ${device.firmware_version} passed integrity verification.`,
      timestamp: new Date(now - (8 + Math.floor(random() * 5)) * 60 * 60 * 1000).toISOString(),
      severity: 'info',
      category: 'system',
    },
  ];

  const logs = [...telemetryLogs, ...systemLogs]
    .sort((left, right) => right.timestamp.localeCompare(left.timestamp))
    .slice(0, 14);

  const criticalCount = logs.filter((entry) => entry.severity === 'critical').length;
  const warningCount = logs.filter((entry) => entry.severity === 'warning').length;

  const healthPenalty = criticalCount * 12 + warningCount * 4 + (device.status === 'maintenance' ? 10 : 0);
  const healthScore = clamp(Math.round(96 - healthPenalty), 34, 99);

  const batteryCapacity = device.battery_capacity_mAh ?? 5400;
  const batteryPercent = clamp(Math.round((batteryCapacity / 7000) * 100 - random() * 12), 18, 99);
  const signalPercent = clamp(Math.round(74 + random() * 25 - (device.status === 'maintenance' ? 12 : 0)), 32, 99);
  const currentSpeedKmh = clamp(Math.round(34 + random() * 50), 8, 98);

  const riskLevel: DeviceRiskLevel =
    criticalCount > 0 || healthScore < 60 ? 'high' : warningCount > 1 || healthScore < 78 ? 'medium' : 'low';

  return {
    healthScore,
    batteryPercent,
    signalPercent,
    currentSpeedKmh,
    riskLevel,
    hasRecentAnomaly: logs.some((entry) => entry.severity !== 'info'),
    latestTimestamp: latest.timestamp,
    metrics,
    timeline,
    logs,
  };
}

export function buildDeviceOverview(device: Device): DeviceOverviewSnapshot {
  const seed = hashString(`${device.id}:${device.device_uid}:overview`);
  const random = seededRandom(seed);

  const batteryCapacity = device.battery_capacity_mAh ?? 5400;
  const batteryPercent = clamp(Math.round((batteryCapacity / 7000) * 100 - random() * 12), 12, 99);
  const signalBase = device.status === 'inactive' ? 32 : device.status === 'maintenance' ? 58 : 82;
  const signalPercent = clamp(Math.round(signalBase + random() * 18 - (batteryPercent < 25 ? 10 : 0)), 8, 99);

  let operationalStatus: DeviceOperationalStatus = 'active';
  if (device.status === 'inactive') {
    operationalStatus = 'offline';
  } else if (device.status === 'maintenance' || batteryPercent < 28 || signalPercent < 35) {
    operationalStatus = 'warning';
  }

  const riskLevel: DeviceRiskLevel =
    operationalStatus === 'offline'
      ? 'high'
      : operationalStatus === 'warning'
        ? signalPercent < 30 || batteryPercent < 20
          ? 'high'
          : 'medium'
        : 'low';

  return {
    batteryPercent,
    signalPercent,
    riskLevel,
    operationalStatus,
  };
}
