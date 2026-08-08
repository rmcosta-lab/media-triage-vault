import { z } from "zod";

/**
 * Typed client for the local, read-only-until-confirmed FastAPI backend
 * (roadmap Phases 17-19). Every response is parsed through a Zod schema so a
 * client/server shape drift fails loudly at the fetch call site.
 *
 * The backend never listens anywhere but 127.0.0.1 (specs/mission.md #1);
 * this client only ever talks to that same local address.
 */

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

function getBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_BASE_URL;
  let parsed: URL;
  try {
    parsed = new URL(configured);
  } catch {
    throw new ApiError("NEXT_PUBLIC_API_BASE_URL is not a valid URL.", 0);
  }

  const isLoopback = parsed.hostname === "127.0.0.1" || parsed.hostname === "localhost";
  const hasOnlyOrigin = parsed.pathname === "/" && parsed.search === "" && parsed.hash === "";
  if (parsed.protocol !== "http:" || !isLoopback || !hasOnlyOrigin) {
    throw new ApiError(
      "NEXT_PUBLIC_API_BASE_URL must be an http://localhost or http://127.0.0.1 origin.",
      0,
    );
  }
  return parsed.origin;
}

/** The API base URL, for building a direct resource URL (e.g. an `<img src>`). */
export function getApiBaseUrl(): string {
  return getBaseUrl();
}

/** Mirrors `rules/engine.py::ROUTING_GROUPS` — stable and small enough not to fetch. */
export const ROUTING_GROUPS = [
  "video",
  "mobile_screenshot",
  "whatsapp_received",
  "iphone_raw",
  "iphone_photo",
  "other",
] as const;

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function formatApiDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail)) return null;

  const messages = detail.flatMap((entry) => {
    if (typeof entry !== "object" || entry === null || !("msg" in entry)) return [];
    const message = typeof entry.msg === "string" ? entry.msg : null;
    if (message === null) return [];
    const location =
      "loc" in entry && Array.isArray(entry.loc)
        ? entry.loc.map(String).join(".")
        : null;
    return [location ? `${location}: ${message}` : message];
  });
  return messages.length > 0 ? messages.join("; ") : null;
}

const ScanSchema = z.object({
  id: z.number(),
  source_root: z.string(),
  recursive: z.boolean(),
  status: z.string(),
  total_files: z.number(),
  processed_files: z.number(),
  total_bytes: z.number(),
  created_at: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
});
export type Scan = z.infer<typeof ScanSchema>;

const JobSchema = z.object({
  id: z.number(),
  job_type: z.string(),
  scan_id: z.number().nullable(),
  move_plan_id: z.number().nullable(),
  status: z.string(),
  total: z.number(),
  processed: z.number(),
  message: z.string().nullable(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
  created_at: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
});
export type Job = z.infer<typeof JobSchema>;

export const JOB_TERMINAL_STATUSES = ["completed", "failed", "cancelled"] as const;

export function isJobTerminal(job: Job): boolean {
  return (JOB_TERMINAL_STATUSES as readonly string[]).includes(job.status);
}

const ScanReportFileSchema = z.object({
  media_file_id: z.number(),
  relative_path: z.string(),
  media_kind: z.string().nullable(),
  extension: z.string(),
  size_bytes: z.number(),
  width: z.number().nullable(),
  height: z.number().nullable(),
  duration_seconds: z.number().nullable(),
  capture_datetime: z.string().nullable(),
  make: z.string().nullable(),
  model: z.string().nullable(),
  software: z.string().nullable(),
  lens_model: z.string().nullable(),
  routing_group: z.string(),
  source_origin: z.string().nullable(),
  image_format: z.string().nullable(),
  confidence: z.number().nullable(),
  requires_review: z.boolean(),
  reasons: z.array(z.string()),
  country_code: z.string().nullable(),
  country_name: z.string().nullable(),
  manual_override: z.boolean(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
});
export type ScanReportFile = z.infer<typeof ScanReportFileSchema>;

const ScanReportSchema = z.object({
  generated_at: z.string(),
  source_root: z.string(),
  total_files: z.number(),
  total_bytes: z.number(),
  totals_by_group: z.record(z.string(), z.number()),
  totals_by_country: z.record(z.string(), z.number()),
  files: z.array(ScanReportFileSchema),
});
export type ScanReport = z.infer<typeof ScanReportSchema>;

const ClassificationSchema = z.object({
  id: z.number(),
  media_file_id: z.number(),
  effective_routing_group: z.string(),
  manual_routing_group: z.string().nullable(),
  automatic_routing_group: z.string(),
});
export type Classification = z.infer<typeof ClassificationSchema>;

const DestinationRuleSchema = z.object({
  id: z.number(),
  scan_id: z.number(),
  routing_group: z.string(),
  destination_root: z.string(),
  country_subfolder_enabled: z.boolean(),
  enabled: z.boolean(),
});
export type DestinationRule = z.infer<typeof DestinationRuleSchema>;

const MoveOperationSchema = z.object({
  id: z.number(),
  move_plan_id: z.number(),
  media_file_id: z.number(),
  source_path: z.string(),
  planned_destination_path: z.string(),
  actual_destination_path: z.string().nullable(),
  source_size: z.number(),
  destination_size: z.number().nullable(),
  status: z.string(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
});
export type MoveOperation = z.infer<typeof MoveOperationSchema>;

const MovePlanSchema = z.object({
  id: z.number(),
  scan_id: z.number(),
  status: z.string(),
  collision_policy: z.string(),
  validation_mode: z.string(),
  created_at: z.string(),
  approved_at: z.string().nullable(),
  total_planned: z.number(),
  total_blocked: z.number(),
  total_bytes_planned: z.number(),
  by_error_code: z.record(z.string(), z.number()),
  operations: z.array(MoveOperationSchema),
});
export type MovePlan = z.infer<typeof MovePlanSchema>;

const MoveReportOperationSchema = z.object({
  media_file_id: z.number(),
  source_path: z.string(),
  planned_destination_path: z.string(),
  actual_destination_path: z.string().nullable(),
  status: z.string(),
  source_size: z.number(),
  destination_size: z.number().nullable(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
});

const MoveReportSchema = z.object({
  move_plan_id: z.number(),
  scan_id: z.number(),
  elapsed_seconds: z.number(),
  totals: z.object({
    operations: z.number(),
    completed: z.number(),
    failed: z.number(),
    skipped: z.number(),
    blocked: z.number(),
    still_planned: z.number(),
    bytes_moved: z.number(),
  }),
  by_error_code: z.record(z.string(), z.number()),
  operations: z.array(MoveReportOperationSchema),
});
export type MoveReport = z.infer<typeof MoveReportSchema>;

async function requestJson<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const method = init?.method ?? "GET";
  const isRead = method === "GET";
  const controller = isRead ? new AbortController() : null;
  const timeout = controller
    ? setTimeout(() => controller.abort(), 30_000)
    : null;
  const headers = new Headers(init?.headers);
  if (init?.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${getBaseUrl()}${path}`, {
      ...init,
      cache: isRead ? "no-store" : init?.cache,
      headers,
      signal: controller?.signal ?? init?.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The local API did not respond within 30 seconds.", 0);
    }
    if (error instanceof ApiError) throw error;
    throw new ApiError(`Could not reach the local API at ${getBaseUrl()}.`, 0);
  } finally {
    if (timeout !== null) clearTimeout(timeout);
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ApiError(
      `The local API returned invalid JSON for ${path} (status ${response.status}).`,
      response.status,
    );
  }

  if (!response.ok) {
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? (body as { detail?: unknown }).detail
        : null;
    throw new ApiError(
      formatApiDetail(detail) ?? `Request to ${path} failed with status ${response.status}`,
      response.status,
    );
  }

  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    throw new ApiError(`The local API response for ${path} has an unexpected shape.`, 502);
  }
  return parsed.data;
}

export function startScan(sourceRoot: string, recursive: boolean): Promise<Job> {
  return requestJson("/api/scans", JobSchema, {
    method: "POST",
    body: JSON.stringify({ source_root: sourceRoot, recursive }),
  });
}

export function startClassify(scanId: number): Promise<Job> {
  return requestJson(`/api/scans/${scanId}/classify`, JobSchema, { method: "POST" });
}

export function getJob(jobId: number): Promise<Job> {
  return requestJson(`/api/jobs/${jobId}`, JobSchema);
}

export function getScan(scanId: number): Promise<Scan> {
  return requestJson(`/api/scans/${scanId}`, ScanSchema);
}

export function getScanReport(scanId: number): Promise<ScanReport> {
  return requestJson(`/api/scans/${scanId}/report`, ScanReportSchema);
}

export function overrideClassification(
  fileId: number,
  routingGroup: string,
): Promise<Classification> {
  return requestJson(`/api/files/${fileId}/classification`, ClassificationSchema, {
    method: "PATCH",
    body: JSON.stringify({ routing_group: routingGroup }),
  });
}

export interface DestinationConfigInput {
  destination_root: string;
  country_subfolder_enabled: boolean;
}

export function putDestinations(
  scanId: number,
  mapping: Record<string, DestinationConfigInput>,
): Promise<DestinationRule[]> {
  return requestJson(`/api/scans/${scanId}/destinations`, z.array(DestinationRuleSchema), {
    method: "PUT",
    body: JSON.stringify(mapping),
  });
}

export function createMovePlan(scanId: number): Promise<MovePlan> {
  return requestJson(`/api/scans/${scanId}/move-plan`, MovePlanSchema, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getMovePlan(planId: number): Promise<MovePlan> {
  return requestJson(`/api/move-plans/${planId}`, MovePlanSchema);
}

export function approveMovePlan(planId: number): Promise<MovePlan> {
  return requestJson(`/api/move-plans/${planId}/approve`, MovePlanSchema, { method: "POST" });
}

export function executeMovePlan(planId: number): Promise<Job> {
  return requestJson(`/api/move-plans/${planId}/execute`, JobSchema, { method: "POST" });
}

export function getMoveRunReport(runId: number): Promise<MoveReport> {
  return requestJson(`/api/move-runs/${runId}/report`, MoveReportSchema);
}

export type JobConnectionState = "connecting" | "connected" | "polling";

interface JobSubscriptionOptions {
  onConnectionState?: (state: JobConnectionState) => void;
  onError?: (message: string) => void;
}

/** Subscribe over SSE, falling back to local polling if the stream drops. */
export function subscribeJobEvents(
  jobId: number,
  onEvent: (job: Job) => void,
  options: JobSubscriptionOptions = {},
): () => void {
  let stopped = false;
  let pollTimer: ReturnType<typeof setTimeout> | null = null;
  let pollingStarted = false;
  let pollInFlight = false;
  const source = new EventSource(`${getBaseUrl()}/api/jobs/${jobId}/events`);
  options.onConnectionState?.("connecting");

  const schedulePoll = () => {
    if (stopped || pollTimer !== null) return;
    pollTimer = setTimeout(() => {
      pollTimer = null;
      void poll();
    }, 1_000);
  };

  const poll = async () => {
    if (stopped || pollInFlight) return;
    pollInFlight = true;
    try {
      const job = await getJob(jobId);
      if (stopped) return;
      onEvent(job);
      if (!isJobTerminal(job)) schedulePoll();
    } catch (error) {
      if (stopped) return;
      options.onError?.(
        error instanceof ApiError ? error.message : "Could not refresh local job progress.",
      );
      schedulePoll();
    } finally {
      pollInFlight = false;
    }
  };

  const startPolling = (message: string) => {
    if (stopped || pollingStarted) return;
    pollingStarted = true;
    source.close();
    options.onConnectionState?.("polling");
    options.onError?.(message);
    void poll();
  };

  source.onopen = () => options.onConnectionState?.("connected");

  source.onmessage = (event: MessageEvent<string>) => {
    let payload: unknown;
    try {
      payload = JSON.parse(event.data);
    } catch {
      startPolling("The live progress stream returned invalid JSON; using polling.");
      return;
    }
    const parsed = JobSchema.safeParse(payload);
    if (parsed.success) {
      onEvent(parsed.data);
    } else {
      startPolling("The live progress stream changed shape; using polling.");
    }
  };

  source.onerror = () => {
    startPolling("Live progress disconnected; status checks will continue locally.");
  };

  return () => {
    stopped = true;
    source.close();
    if (pollTimer !== null) clearTimeout(pollTimer);
  };
}
