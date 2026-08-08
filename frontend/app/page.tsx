"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import styles from "./page.module.css";
import {
  ApiError,
  getScan,
  getScanReport,
  isJobTerminal,
  startClassify,
  startScan,
  subscribeJobEvents,
  type JobConnectionState,
  type Job,
  type Scan,
  type ScanReport,
} from "@/lib/api";

type Stage =
  | "idle"
  | "scanning"
  | "scan-completed"
  | "scanned"
  | "classifying"
  | "classification-completed"
  | "classified";

export default function Dashboard() {
  const [sourceRoot, setSourceRoot] = useState("");
  const [recursive, setRecursive] = useState(true);
  const [stage, setStage] = useState<Stage>("idle");
  const [scanJob, setScanJob] = useState<Job | null>(null);
  const [classifyJob, setClassifyJob] = useState<Job | null>(null);
  const [scan, setScan] = useState<Scan | null>(null);
  const [report, setReport] = useState<ScanReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progressNotice, setProgressNotice] = useState<string | null>(null);
  const [connectionState, setConnectionState] = useState<JobConnectionState | null>(null);

  const unsubscribeRef = useRef<(() => void) | null>(null);
  const mountedRef = useRef(true);
  const mutationPendingRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      unsubscribeRef.current?.();
    };
  }, []);

  function watchJob(job: Job, onTerminal: (finalJob: Job) => Promise<void>) {
    unsubscribeRef.current?.();
    unsubscribeRef.current = subscribeJobEvents(
      job.id,
      (updated) => {
        if (!mountedRef.current) return;
        if (updated.job_type === job.job_type) {
          if (job.job_type === "scan") setScanJob(updated);
          else setClassifyJob(updated);
        }
        if (isJobTerminal(updated)) {
          mutationPendingRef.current = false;
          unsubscribeRef.current?.();
          unsubscribeRef.current = null;
          setConnectionState(null);
          setProgressNotice(null);
          void onTerminal(updated);
        }
      },
      {
        onConnectionState: (state) => {
          setConnectionState(state);
          if (state === "connected") setProgressNotice(null);
        },
        onError: setProgressNotice,
      },
    );
  }

  function jobFailureMessage(label: string, job: Job): string {
    const code = job.error_code ? ` (${job.error_code})` : "";
    const detail = job.error_message ? `: ${job.error_message}` : ".";
    return `${label} ended with status "${job.status}"${code}${detail}`;
  }

  async function loadScanSummary(scanId: number) {
    setError(null);
    setProgressNotice("Loading the completed scan summary...");
    try {
      const finishedScan = await getScan(scanId);
      if (!mountedRef.current) return;
      setScan(finishedScan);
      setStage("scanned");
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof ApiError ? err.message : "Could not load the finished scan.");
      setStage("scan-completed");
    } finally {
      if (mountedRef.current) setProgressNotice(null);
    }
  }

  async function loadClassificationReport(scanId: number) {
    setError(null);
    setProgressNotice("Loading the completed classification report...");
    try {
      const finishedReport = await getScanReport(scanId);
      if (!mountedRef.current) return;
      setReport(finishedReport);
      setStage("classified");
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof ApiError ? err.message : "Could not load group totals.");
      setStage("classification-completed");
    } finally {
      if (mountedRef.current) setProgressNotice(null);
    }
  }

  async function handleStartScan(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mutationPendingRef.current) return;
    mutationPendingRef.current = true;
    setError(null);
    setScan(null);
    setReport(null);
    setClassifyJob(null);
    setScanJob(null);
    setStage("scanning");
    setProgressNotice("Starting the local scan...");

    try {
      const job = await startScan(sourceRoot, recursive);
      if (!mountedRef.current) return;
      setScanJob(job);
      setProgressNotice(null);

      watchJob(job, async (finalJob) => {
        if (finalJob.status === "completed" && finalJob.scan_id !== null) {
          setStage("scan-completed");
          await loadScanSummary(finalJob.scan_id);
        } else {
          setError(jobFailureMessage("Scan", finalJob));
          setStage("idle");
        }
      });
    } catch (err) {
      mutationPendingRef.current = false;
      if (!mountedRef.current) return;
      setError(err instanceof ApiError ? err.message : "Could not start the scan.");
      setStage("idle");
      setProgressNotice(null);
    }
  }

  async function handleClassify() {
    if (!scan || mutationPendingRef.current) return;
    mutationPendingRef.current = true;
    setError(null);
    setClassifyJob(null);
    setStage("classifying");
    setProgressNotice("Starting classification...");

    try {
      const job = await startClassify(scan.id);
      if (!mountedRef.current) return;
      setClassifyJob(job);
      setProgressNotice(null);

      watchJob(job, async (finalJob) => {
        if (finalJob.status === "completed") {
          setStage("classification-completed");
          await loadClassificationReport(scan.id);
        } else {
          setError(jobFailureMessage("Classification", finalJob));
          setStage("scanned");
        }
      });
    } catch (err) {
      mutationPendingRef.current = false;
      if (!mountedRef.current) return;
      setError(err instanceof ApiError ? err.message : "Could not start classification.");
      setStage("scanned");
      setProgressNotice(null);
    }
  }

  const busy = stage === "scanning" || stage === "classifying";

  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <h1>Local Media Organizer</h1>
        <p className={styles.subtitle}>
          Scan a folder, watch it live, and see the classified breakdown — all local.
        </p>

        <form className={styles.form} onSubmit={handleStartScan}>
          <label className={styles.field}>
            <span>Folder to scan</span>
            <input
              type="text"
              value={sourceRoot}
              onChange={(event) => setSourceRoot(event.target.value)}
              placeholder="D:\Fotos"
              disabled={busy}
              required
            />
          </label>
          <label className={styles.checkboxField}>
            <input
              type="checkbox"
              checked={recursive}
              onChange={(event) => setRecursive(event.target.checked)}
              disabled={busy}
            />
            <span>Include subfolders</span>
          </label>
          <button
            type="submit"
            className={styles.button}
            disabled={busy || sourceRoot.trim() === ""}
          >
            {stage === "scanning" ? "Scanning…" : "Start scan"}
          </button>
        </form>

        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}

        {progressNotice && (
          <p className={styles.notice} role="status" aria-live="polite">
            {progressNotice}
          </p>
        )}

        {scanJob && (
          <section className={styles.panel}>
            <h2>Scan progress</h2>
            <dl className={styles.statusList}>
              <div>
                <dt>Status</dt>
                <dd>{scanJob.status}</dd>
              </div>
              <div>
                <dt>Files processed</dt>
                <dd>
                  {scanJob.processed}
                  {scanJob.total > 0 ? ` / ${scanJob.total}` : ""}
                </dd>
              </div>
              {scanJob.message && (
                <div>
                  <dt>Stage</dt>
                  <dd>{scanJob.message}</dd>
                </div>
              )}
              {connectionState && stage === "scanning" && (
                <div>
                  <dt>Progress connection</dt>
                  <dd>{connectionState}</dd>
                </div>
              )}
            </dl>
          </section>
        )}

        {scan && (
          <section className={styles.panel}>
            <h2>Scan summary</h2>
            <dl className={styles.statusList}>
              <div>
                <dt>Total files</dt>
                <dd>{scan.total_files}</dd>
              </div>
              <div>
                <dt>Total bytes</dt>
                <dd>{scan.total_bytes.toLocaleString()}</dd>
              </div>
            </dl>
            {stage === "scanned" && (
              <button type="button" className={styles.button} onClick={handleClassify}>
                Classify
              </button>
            )}
          </section>
        )}

        {stage === "scan-completed" && scanJob?.scan_id != null && (
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              if (scanJob.scan_id !== null) void loadScanSummary(scanJob.scan_id);
            }}
          >
            Retry loading scan summary
          </button>
        )}

        {classifyJob && (
          <section className={styles.panel}>
            <h2>Classification progress</h2>
            <dl className={styles.statusList}>
              <div>
                <dt>Status</dt>
                <dd>{classifyJob.status}</dd>
              </div>
              <div>
                <dt>Files classified</dt>
                <dd>
                  {classifyJob.processed}
                  {classifyJob.total > 0 ? ` / ${classifyJob.total}` : ""}
                </dd>
              </div>
              {classifyJob.message && (
                <div>
                  <dt>Stage</dt>
                  <dd>{classifyJob.message}</dd>
                </div>
              )}
              {connectionState && stage === "classifying" && (
                <div>
                  <dt>Progress connection</dt>
                  <dd>{connectionState}</dd>
                </div>
              )}
            </dl>
          </section>
        )}

        {stage === "classification-completed" && scan && (
          <button
            type="button"
            className={styles.button}
            onClick={() => void loadClassificationReport(scan.id)}
          >
            Retry loading classification report
          </button>
        )}

        {report && (
          <section className={styles.panel}>
            <h2>Group totals</h2>
            <ul className={styles.groupList}>
              {Object.entries(report.totals_by_group).map(([group, count]) => (
                <li key={group}>
                  <span className={styles.groupName}>{group}</span>
                  <span className={styles.groupCount}>{count}</span>
                </li>
              ))}
            </ul>
            {scan && <Link href={`/review?scanId=${scan.id}`}>Review files →</Link>}
          </section>
        )}
      </main>
    </div>
  );
}
