"use client";

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
  type Job,
  type Scan,
  type ScanReport,
} from "@/lib/api";

type Stage =
  | "idle"
  | "scanning"
  | "scanned"
  | "classifying"
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

  const unsubscribeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      unsubscribeRef.current?.();
    };
  }, []);

  function watchJob(job: Job, onTerminal: (finalJob: Job) => void) {
    unsubscribeRef.current?.();
    unsubscribeRef.current = subscribeJobEvents(job.id, (updated) => {
      if (updated.job_type === job.job_type) {
        if (job.job_type === "scan") setScanJob(updated);
        else setClassifyJob(updated);
      }
      if (isJobTerminal(updated)) {
        unsubscribeRef.current?.();
        unsubscribeRef.current = null;
        onTerminal(updated);
      }
    });
  }

  async function handleStartScan(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setScan(null);
    setReport(null);
    setClassifyJob(null);

    try {
      const job = await startScan(sourceRoot, recursive);
      setScanJob(job);
      setStage("scanning");

      watchJob(job, async (finalJob) => {
        if (finalJob.status === "completed" && finalJob.scan_id !== null) {
          const finishedScan = await getScan(finalJob.scan_id);
          setScan(finishedScan);
          setStage("scanned");
        } else {
          setError(`Scan ended with status "${finalJob.status}".`);
          setStage("idle");
        }
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start the scan.");
      setStage("idle");
    }
  }

  async function handleClassify() {
    if (!scan) return;
    setError(null);

    try {
      const job = await startClassify(scan.id);
      setClassifyJob(job);
      setStage("classifying");

      watchJob(job, async (finalJob) => {
        if (finalJob.status === "completed") {
          const finishedReport = await getScanReport(scan.id);
          setReport(finishedReport);
          setStage("classified");
        } else {
          setError(`Classification ended with status "${finalJob.status}".`);
          setStage("scanned");
        }
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start classification.");
      setStage("scanned");
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
                <dd>{scanJob.processed}</dd>
              </div>
              {scanJob.message && (
                <div>
                  <dt>Stage</dt>
                  <dd>{scanJob.message}</dd>
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
                <dd>{classifyJob.processed}</dd>
              </div>
            </dl>
          </section>
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
          </section>
        )}
      </main>
    </div>
  );
}
