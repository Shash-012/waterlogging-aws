/* Generated from contract/schemas/ by scripts/gen-types.mjs. Do not edit by hand. */

/**
 * GET /hotspots: a JSON array of Hotspot.
 */
export type HotspotList = Hotspot[];
/**
 * GET /replays: a JSON array of ReplaySummary.
 */
export type ReplayIndex = ReplaySummary[];

export interface ContractRoot {
  alert_log?: AlertLog;
  alert_record?: AlertRecord;
  alert_request?: AlertRequest;
  alert_response?: AlertResponse;
  common?: CommonDefinitions;
  error?: Error;
  health?: Health;
  hotspot?: Hotspot;
  hotspot_list?: HotspotList;
  params?: Params;
  pump_plan?: PumpPlan;
  replay?: Replay;
  replay_index?: ReplayIndex;
  replay_summary?: ReplaySummary;
  snapshot?: Snapshot;
}
/**
 * GET /alerts?limit=N.
 */
export interface AlertLog {
  alerts: AlertRecord[];
}
/**
 * One alert in the log: the request fields, the response fields and sent_by.
 */
export interface AlertRecord {
  /**
   * e.g. DL-001
   */
  hotspot_id: string;
  /**
   * UTC ISO 8601 timestamp ending in Z.
   */
  run_id: string;
  mode: "live" | "replay";
  /**
   * Replay event_id; required when mode is replay, null for live.
   */
  event_id?: string | null;
  level: "LOW" | "WATCH" | "HIGH" | "CRITICAL";
  /**
   * Float from 0 to 1, rounded to 3 decimals.
   */
  risk: number;
  peak_at: string | null;
  alert_id: string;
  /**
   * UTC ISO 8601 timestamp ending in Z.
   */
  sent_at: string;
  duplicate: boolean;
  text_en: string;
  text_hi: string;
  deliveries: AlertDelivery[];
  sent_by: string;
}
export interface AlertDelivery {
  group: string;
  ok: boolean;
}
/**
 * POST /alerts body on the ops API (Cognito JWT required).
 */
export interface AlertRequest {
  /**
   * e.g. DL-001
   */
  hotspot_id: string;
  /**
   * UTC ISO 8601 timestamp ending in Z.
   */
  run_id: string;
  mode: "live" | "replay";
  /**
   * Replay event_id; required when mode is replay, null for live.
   */
  event_id?: string | null;
  level: "LOW" | "WATCH" | "HIGH" | "CRITICAL";
  /**
   * Float from 0 to 1, rounded to 3 decimals.
   */
  risk: number;
  peak_at: string | null;
}
/**
 * POST /alerts response.
 */
export interface AlertResponse {
  alert_id: string;
  /**
   * UTC ISO 8601 timestamp ending in Z.
   */
  sent_at: string;
  duplicate: boolean;
  text_en: string;
  text_hi: string;
  deliveries: AlertDelivery1[];
}
export interface AlertDelivery1 {
  group: string;
  ok: boolean;
}
/**
 * Shared building blocks for the WLEW contract schemas (contract/CONTRACT.md).
 */
export interface CommonDefinitions {
  [k: string]: unknown;
}
/**
 * Error body returned with any non-2xx HTTP status.
 */
export interface Error {
  error: ErrorDetail;
}
export interface ErrorDetail {
  code: string;
  message: string;
}
/**
 * GET /health on the core API.
 */
export interface Health {
  ok: boolean;
  /**
   * null before the first scoring run.
   */
  latest_run_id: string | null;
}
/**
 * One waterlogging hotspot, from GET /hotspots and GET /hotspots/{id}.
 */
export interface Hotspot {
  /**
   * e.g. DL-001
   */
  hotspot_id: string;
  name_en: string;
  name_hi: string;
  lat: number;
  lon: number;
  site_type: "underpass" | "road" | "junction" | "colony";
  ward: string | null;
  /**
   * 1.0 arterial/emergency route, 0.6 major road, 0.3 local road. Pump tie-breaker only.
   */
  importance: 1 | 0.6 | 0.3;
  elevation_m: number;
  /**
   * d in the LowLying definition (m).
   */
  relative_depth_m: number;
  catchment_km2: number;
  flood_seasons: number;
  factors: HotspotFactors;
  /**
   * Float from 0 to 1, rounded to 3 decimals.
   */
  susceptibility: number;
  avoid_en: string;
  avoid_hi: string;
  diversion_en: string;
  diversion_hi: string;
  /**
   * @minItems 1
   */
  sources: [string, ...string[]];
}
export interface HotspotFactors {
  /**
   * Float from 0 to 1, rounded to 3 decimals.
   */
  history: number;
  /**
   * Float from 0 to 1, rounded to 3 decimals.
   */
  low_lying: number;
  /**
   * Float from 0 to 1, rounded to 3 decimals.
   */
  catchment: number;
}
/**
 * Shape of model/params.json. Agent A may retune the numbers; the shape is fixed.
 */
export interface Params {
  version: string;
  rain: {
    i0_mm_h: number;
    i1_mm_h: number;
    a_sat_mm: number;
    k: number;
    window_hours: number;
  };
  susceptibility: {
    w_history: number;
    w_low_lying: number;
    w_catchment: number;
  };
  levels: {
    watch: number;
    high: number;
    critical: number;
  };
  city: {
    alert: number;
    severe: number;
  };
}
/**
 * GET /pumps?count=N (N from 0 to 50).
 */
export interface PumpPlan {
  /**
   * UTC ISO 8601 timestamp ending in Z.
   */
  run_id: string;
  pumps_available: number;
  assignments: PumpAssignment[];
  /**
   * HIGH-or-above spots left without a pump.
   */
  unassigned: PumpUnassigned[];
}
export interface PumpAssignment {
  /**
   * e.g. DL-001
   */
  hotspot_id: string;
  pumps: number;
  level: "LOW" | "WATCH" | "HIGH" | "CRITICAL";
  /**
   * Float from 0 to 1, rounded to 3 decimals.
   */
  risk: number;
}
export interface PumpUnassigned {
  /**
   * e.g. DL-001
   */
  hotspot_id: string;
  level: "HIGH" | "CRITICAL";
  /**
   * Float from 0 to 1, rounded to 3 decimals.
   */
  risk: number;
}
/**
 * GET /replays/{event_id}. Every frame is a Snapshot with mode "replay".
 */
export interface Replay {
  /**
   * Date of the storm's main rain (YYYY-MM-DD).
   */
  event_id: string;
  title_en: string;
  kind: "storm" | "dry";
  /**
   * UTC ISO 8601 timestamp ending in Z.
   */
  start: string;
  /**
   * UTC ISO 8601 timestamp ending in Z.
   */
  end: string;
  frame_count: number;
  /**
   * @minItems 1
   */
  frames: [
    Snapshot & {
      mode?: "replay";
    },
    ...(Snapshot & {
      mode?: "replay";
    })[]
  ];
  ground_truth: GroundTruthReport[];
  metrics: ReplayMetrics;
}
/**
 * GET /scores/latest, and the shape of every replay frame.
 */
export interface Snapshot {
  /**
   * UTC ISO 8601 timestamp ending in Z.
   */
  run_id: string;
  /**
   * UTC ISO 8601 timestamp ending in Z.
   */
  as_of: string;
  mode: "live" | "replay";
  params_version: string;
  city: CityState;
  hotspots: SnapshotHotspot[];
}
export interface CityState {
  status: "STANDBY" | "RAIN_WATCH" | "ALERT" | "SEVERE";
  /**
   * Float from 0 to 1, rounded to 3 decimals.
   */
  rain_trigger_max: number;
  /**
   * Spots where I > 0 (I is the max hourly intensity over the current hour and the next 6).
   */
  spots_raining: number;
}
export interface SnapshotHotspot {
  /**
   * e.g. DL-001
   */
  hotspot_id: string;
  /**
   * 1 = highest risk.
   */
  rank: number;
  level: "LOW" | "WATCH" | "HIGH" | "CRITICAL";
  /**
   * Float from 0 to 1, rounded to 3 decimals.
   */
  risk: number;
  /**
   * Float from 0 to 1, rounded to 3 decimals.
   */
  rain_trigger: number;
  /**
   * Float from 0 to 1, rounded to 3 decimals.
   */
  susceptibility: number;
  /**
   * I: highest hourly precipitation over the current hour and the next window_hours.
   */
  intensity_mm_h: number;
  /**
   * A: precipitation over the 24 h ending at the current hour.
   */
  rain_24h_mm: number;
  effective_intensity_mm_h: number;
  /**
   * Hour of the highest forecast intensity in the window; null when no rain is forecast.
   */
  peak_at: string | null;
}
export interface GroundTruthReport {
  /**
   * e.g. DL-001
   */
  hotspot_id: string;
  /**
   * UTC ISO 8601 timestamp ending in Z.
   */
  first_report_at: string;
  source_url: string;
  note: string;
  /**
   * Optional. What kind of time first_report_at is; with published, lead times are upper bounds.
   */
  time_kind?: "post" | "stated" | "published";
}
export interface ReplayMetrics {
  spots_reported: number;
  flagged_before_report: number;
  /**
   * null when no reported spot was flagged before its report.
   */
  median_lead_hours: number | null;
  unconfirmed_flags: number;
}
/**
 * One entry of GET /replays: a Replay without frames, ground_truth and metrics.
 */
export interface ReplaySummary {
  event_id: string;
  title_en: string;
  kind: "storm" | "dry";
  /**
   * UTC ISO 8601 timestamp ending in Z.
   */
  start: string;
  /**
   * UTC ISO 8601 timestamp ending in Z.
   */
  end: string;
  frame_count: number;
}
