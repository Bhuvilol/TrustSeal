import type { ShipmentSensorStats, ShipmentStatus, TelemetryEvent } from '@/types';
import { TEMPERATURE_THRESHOLD_C } from '@/utils/constants';

export interface SensorStats {
  totalLogs: number;
  temperatureSampleCount: number;
  averageTemperature: number | null;
  minTemperature: number | null;
  maxTemperature: number | null;
  maxShock: number | null;
  lastUpdate: string | null;
  hasTemperatureBreach: boolean;
  complianceStatus: 'Valid' | 'Compromised';
}

export function sortLogsByRecordedAt(logs: TelemetryEvent[]): TelemetryEvent[] {
  return [...logs].sort(
    (left, right) => new Date(left.ts).getTime() - new Date(right.ts).getTime(),
  );
}

export function calculateSensorStats(
  logs: TelemetryEvent[],
  shipmentStatus?: ShipmentStatus,
): SensorStats {
  const sortedLogs = sortLogsByRecordedAt(logs);
  const latest = sortedLogs.at(-1) ?? null;

  const temperatureValues = sortedLogs
    .map((entry) => entry.temperature_c)
    .filter((value): value is number => typeof value === 'number');

  const shockValues = sortedLogs
    .map((entry) => entry.shock_g)
    .filter((value): value is number => typeof value === 'number');

  const averageTemperature =
    temperatureValues.length > 0
      ? temperatureValues.reduce((sum, value) => sum + value, 0) / temperatureValues.length
      : null;
  const minTemperature =
    temperatureValues.length > 0 ? temperatureValues.reduce((min, value) => Math.min(min, value), temperatureValues[0]) : null;
  const maxTemperature =
    temperatureValues.length > 0 ? temperatureValues.reduce((max, value) => Math.max(max, value), temperatureValues[0]) : null;

  const maxShock =
    shockValues.length > 0 ? shockValues.reduce((max, value) => Math.max(max, value), shockValues[0]) : null;

  const hasTemperatureBreach = temperatureValues.some((value) => value > TEMPERATURE_THRESHOLD_C);
  const shipmentCompromised = shipmentStatus === 'compromised';
  const complianceStatus = hasTemperatureBreach || shipmentCompromised ? 'Compromised' : 'Valid';

  return {
    totalLogs: sortedLogs.length,
    temperatureSampleCount: temperatureValues.length,
    averageTemperature,
    minTemperature,
    maxTemperature,
    maxShock,
    lastUpdate: latest?.ts ?? null,
    hasTemperatureBreach,
    complianceStatus,
  };
}

export function sensorStatsFromBackend(
  stats: ShipmentSensorStats,
  shipmentStatus?: ShipmentStatus,
): SensorStats {
  const shipmentCompromised = shipmentStatus === 'compromised';
  const complianceStatus = stats.has_temperature_breach || shipmentCompromised ? 'Compromised' : 'Valid';

  return {
    totalLogs: stats.total_logs,
    temperatureSampleCount: stats.temperature_sample_count,
    averageTemperature: stats.average_temperature,
    minTemperature: stats.min_temperature,
    maxTemperature: stats.max_temperature,
    maxShock: stats.max_shock,
    lastUpdate: stats.last_recorded_at,
    hasTemperatureBreach: stats.has_temperature_breach,
    complianceStatus,
  };
}
