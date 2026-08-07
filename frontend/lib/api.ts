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
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_BASE_URL;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
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

const ScanReportSchema = z.object({
  generated_at: z.string(),
  source_root: z.string(),
  total_files: z.number(),
  total_bytes: z.number(),
  totals_by_group: z.record(z.string(), z.number()),
  totals_by_country: z.record(z.string(), z.number()),
});
export type ScanReport = z.infer<typeof ScanReportSchema>;

async function requestJson<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${getBaseUrl()}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });

  if (!response.ok) {
    const detail = await response
      .json()
      .then((body: { detail?: string }) => body.detail)
      .catch(() => null);
    throw new ApiError(
      detail ?? `Request to ${path} failed with status ${response.status}`,
      response.status,
    );
  }

  return schema.parse(await response.json());
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

/** Subscribe to a job's live progress over SSE. Returns an unsubscribe function. */
export function subscribeJobEvents(jobId: number, onEvent: (job: Job) => void): () => void {
  const source = new EventSource(`${getBaseUrl()}/api/jobs/${jobId}/events`);

  source.onmessage = (event: MessageEvent<string>) => {
    const parsed = JobSchema.safeParse(JSON.parse(event.data));
    if (parsed.success) {
      onEvent(parsed.data);
    }
  };

  return () => source.close();
}
