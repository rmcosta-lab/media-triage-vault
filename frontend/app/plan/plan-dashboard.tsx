"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import styles from "./plan.module.css";
import {
  ApiError,
  ROUTING_GROUPS,
  approveMovePlan,
  createMovePlan,
  executeMovePlan,
  getMoveRunReport,
  getScanReport,
  isJobTerminal,
  putDestinations,
  subscribeJobEvents,
  type JobConnectionState,
  type Job,
  type MovePlan,
  type MoveReport,
  type ScanReport,
} from "@/lib/api";

interface DestinationInput {
  destinationRoot: string;
  countrySubfolderEnabled: boolean;
}

interface DestinationFolderPreview {
  path: string;
  fileCount: number;
}

const WINDOWS_RESERVED_NAMES = new Set([
  "CON",
  "PRN",
  "AUX",
  "NUL",
  ...Array.from({ length: 9 }, (_, index) => `COM${index + 1}`),
  ...Array.from({ length: 9 }, (_, index) => `LPT${index + 1}`),
]);

function sanitizePreviewPathComponent(name: string): string {
  const cleaned = Array.from(name)
    .filter((character) => {
      const codePoint = character.codePointAt(0) ?? 0;
      return codePoint >= 32 && !'<>:"/\\|?*'.includes(character);
    })
    .join("")
    .replace(/[. ]+$/, "");
  const stem = cleaned.split(".", 1)[0].toUpperCase();
  return WINDOWS_RESERVED_NAMES.has(stem) ? `_${cleaned}` : cleaned;
}

function joinPreviewPath(root: string, ...components: string[]): string {
  const trimmedRoot = root.trim();
  const separator =
    trimmedRoot.lastIndexOf("\\") > trimmedRoot.lastIndexOf("/") ||
    (/^[A-Za-z]:/.test(trimmedRoot) && !trimmedRoot.includes("/"))
      ? "\\"
      : "/";
  const base = trimmedRoot.replace(/[\\/]+$/, "");
  const suffix = components.join(separator);

  if (base !== "") return `${base}${separator}${suffix}`;
  if (trimmedRoot.startsWith(separator)) return `${separator}${suffix}`;
  return suffix;
}

function buildDestinationFolderPreviews(
  scanReport: ScanReport,
  routingGroup: string,
  input: DestinationInput,
): DestinationFolderPreview[] {
  if (input.destinationRoot.trim() === "") return [];

  const groupFolder = sanitizePreviewPathComponent(routingGroup);
  if (!input.countrySubfolderEnabled) {
    return [
      {
        path: joinPreviewPath(input.destinationRoot, groupFolder),
        fileCount: scanReport.totals_by_group[routingGroup] ?? 0,
      },
    ];
  }

  const countsByCountryFolder = new Map<string, number>();
  for (const file of scanReport.files) {
    if (file.routing_group !== routingGroup) continue;
    const countryLabel = file.country_name || file.country_code || "unknown";
    const countryFolder = sanitizePreviewPathComponent(countryLabel);
    countsByCountryFolder.set(
      countryFolder,
      (countsByCountryFolder.get(countryFolder) ?? 0) + 1,
    );
  }

  return Array.from(countsByCountryFolder, ([countryFolder, fileCount]) => ({
    path: joinPreviewPath(input.destinationRoot, groupFolder, countryFolder),
    fileCount,
  })).sort((left, right) => left.path.localeCompare(right.path));
}

export default function PlanDashboard() {
  const searchParams = useSearchParams();
  const rawScanId = searchParams.get("scanId");
  const scanId = Number(rawScanId);
  const invalidScanId =
    rawScanId === null ||
    rawScanId.trim() === "" ||
    !Number.isSafeInteger(scanId) ||
    scanId <= 0;

  const [scanReport, setScanReport] = useState<ScanReport | null>(null);
  const [loadedScanId, setLoadedScanId] = useState<number | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadErrorScanId, setLoadErrorScanId] = useState<number | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [slowScanId, setSlowScanId] = useState<number | null>(null);

  const [destinations, setDestinations] = useState<Record<string, DestinationInput>>({});
  const [destinationsSaved, setDestinationsSaved] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const [plan, setPlan] = useState<MovePlan | null>(null);
  const [executeJob, setExecuteJob] = useState<Job | null>(null);
  const [moveReport, setMoveReport] = useState<MoveReport | null>(null);
  const [moveReportError, setMoveReportError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<
    "saving" | "planning" | "approving" | "executing" | null
  >(null);
  const [progressNotice, setProgressNotice] = useState<string | null>(null);
  const [connectionState, setConnectionState] = useState<JobConnectionState | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);
  const mountedRef = useRef(true);
  const currentScanIdRef = useRef(scanId);

  const activeScanReport = loadedScanId === scanId ? scanReport : null;
  const activeLoadError = loadErrorScanId === scanId ? loadError : null;

  useLayoutEffect(() => {
    currentScanIdRef.current = scanId;
  }, [scanId]);

  useEffect(() => {
    if (invalidScanId) return;
    let cancelled = false;
    const slowTimer = setTimeout(() => {
      if (!cancelled) setSlowScanId(scanId);
    }, 5_000);
    getScanReport(scanId)
      .then((data) => {
        if (cancelled) return;
        clearTimeout(slowTimer);
        setScanReport(data);
        setLoadedScanId(scanId);
        setLoadError(null);
        setLoadErrorScanId(null);
        setSlowScanId(null);
        const initial: Record<string, DestinationInput> = {};
        for (const group of ROUTING_GROUPS) {
          if ((data.totals_by_group[group] ?? 0) > 0) {
            initial[group] = { destinationRoot: "", countrySubfolderEnabled: false };
          }
        }
        setDestinations(initial);
        setDestinationsSaved(false);
        setPlan(null);
        setExecuteJob(null);
        setMoveReport(null);
        setMoveReportError(null);
        setActionError(null);
        setProgressNotice(null);
        setConnectionState(null);
        setPendingAction(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          clearTimeout(slowTimer);
          setLoadError(err instanceof ApiError ? err.message : "Could not load the scan report.");
          setLoadErrorScanId(scanId);
          setSlowScanId(null);
        }
      });
    return () => {
      cancelled = true;
      clearTimeout(slowTimer);
    };
  }, [scanId, invalidScanId, reloadToken]);

  useEffect(() => {
    return () => {
      unsubscribeRef.current?.();
      unsubscribeRef.current = null;
    };
  }, [scanId]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const groups = useMemo(
    () =>
      ROUTING_GROUPS.filter(
        (group) => (activeScanReport?.totals_by_group[group] ?? 0) > 0,
      ),
    [activeScanReport],
  );
  const unclassifiedCount = activeScanReport?.totals_by_group.unclassified ?? 0;

  async function handleSaveDestinations() {
    if (pendingAction !== null || loadedScanId !== scanId) return;
    setActionError(null);
    const mapping: Record<string, { destination_root: string; country_subfolder_enabled: boolean }> =
      {};
    for (const group of ROUTING_GROUPS) {
      const input = destinations[group];
      if (input === undefined) continue;
      if (input.destinationRoot.trim() === "") continue;
      mapping[group] = {
        destination_root: input.destinationRoot,
        country_subfolder_enabled: input.countrySubfolderEnabled,
      };
    }
    if (Object.keys(mapping).length === 0) {
      setActionError("Map at least one routing group to a destination folder.");
      return;
    }
    setPendingAction("saving");
    try {
      await putDestinations(scanId, mapping);
      if (!mountedRef.current || currentScanIdRef.current !== scanId) return;
      setDestinationsSaved(true);
      setPlan(null);
      setExecuteJob(null);
      setMoveReport(null);
    } catch (err) {
      if (!mountedRef.current || currentScanIdRef.current !== scanId) return;
      setActionError(err instanceof ApiError ? err.message : "Could not save destinations.");
    } finally {
      if (mountedRef.current && currentScanIdRef.current === scanId) setPendingAction(null);
    }
  }

  async function handleGeneratePlan() {
    if (pendingAction !== null || loadedScanId !== scanId) return;
    setActionError(null);
    setPendingAction("planning");
    setPlan(null);
    setExecuteJob(null);
    setMoveReport(null);
    setMoveReportError(null);
    try {
      const generatedPlan = await createMovePlan(scanId);
      if (!mountedRef.current || currentScanIdRef.current !== scanId) return;
      setPlan(generatedPlan);
    } catch (err) {
      if (!mountedRef.current || currentScanIdRef.current !== scanId) return;
      setActionError(err instanceof ApiError ? err.message : "Could not generate the plan.");
    } finally {
      if (mountedRef.current && currentScanIdRef.current === scanId) setPendingAction(null);
    }
  }

  async function handleApprove() {
    if (!plan || pendingAction !== null || loadedScanId !== scanId) return;
    setActionError(null);
    setPendingAction("approving");
    try {
      const approvedPlan = await approveMovePlan(plan.id);
      if (!mountedRef.current || currentScanIdRef.current !== scanId) return;
      setPlan(approvedPlan);
    } catch (err) {
      if (!mountedRef.current || currentScanIdRef.current !== scanId) return;
      setActionError(err instanceof ApiError ? err.message : "Could not approve the plan.");
    } finally {
      if (mountedRef.current && currentScanIdRef.current === scanId) setPendingAction(null);
    }
  }

  async function handleExecute() {
    if (!plan || pendingAction !== null || loadedScanId !== scanId) return;
    setActionError(null);
    setMoveReportError(null);
    setProgressNotice("Starting local execution…");
    setPendingAction("executing");
    setMoveReport(null);
    try {
      const job = await executeMovePlan(plan.id);
      if (!mountedRef.current || currentScanIdRef.current !== scanId) return;
      setExecuteJob(job);
      setPendingAction(null);
      setProgressNotice(null);
      unsubscribeRef.current?.();
      unsubscribeRef.current = subscribeJobEvents(
        job.id,
        (updated) => {
          if (!mountedRef.current || currentScanIdRef.current !== scanId) return;
          setExecuteJob(updated);
          if (isJobTerminal(updated)) {
            unsubscribeRef.current?.();
            unsubscribeRef.current = null;
            setConnectionState(null);
            setProgressNotice(null);
            if (updated.status !== "completed") {
              const code = updated.error_code ? ` (${updated.error_code})` : "";
              const detail = updated.error_message ? `: ${updated.error_message}` : ".";
              setActionError(`Execution ended with status "${updated.status}"${code}${detail}`);
            }
            getMoveRunReport(updated.id)
              .then((report) => {
                if (mountedRef.current && currentScanIdRef.current === scanId) {
                  setMoveReport(report);
                }
              })
              .catch((err: unknown) => {
                if (mountedRef.current && currentScanIdRef.current === scanId) {
                  setMoveReportError(
                    err instanceof ApiError ? err.message : "Could not load the move report.",
                  );
                }
              });
          }
        },
        {
          onConnectionState: (state) => {
            if (!mountedRef.current || currentScanIdRef.current !== scanId) return;
            setConnectionState(state);
            if (state === "connected") setProgressNotice(null);
          },
          onError: (message) => {
            if (mountedRef.current && currentScanIdRef.current === scanId) {
              setProgressNotice(message);
            }
          },
        },
      );
    } catch (err) {
      if (!mountedRef.current || currentScanIdRef.current !== scanId) return;
      setActionError(err instanceof ApiError ? err.message : "Could not start execution.");
      setPendingAction(null);
      setProgressNotice(null);
    }
  }

  function invalidatePlan() {
    setDestinationsSaved(false);
    setPlan(null);
    setExecuteJob(null);
    setMoveReport(null);
    setMoveReportError(null);
    setActionError(null);
  }

  function retryLoad() {
    setLoadError(null);
    setLoadErrorScanId(null);
    setScanReport(null);
    setLoadedScanId(null);
    setSlowScanId(null);
    setReloadToken((token) => token + 1);
  }

  if (invalidScanId) {
    return (
      <main className={styles.page}>
        <p className={styles.error} role="alert">
          No scanId provided in the URL.
        </p>
      </main>
    );
  }

  if (activeLoadError) {
    return (
      <main className={styles.page}>
        <p className={styles.error} role="alert">
          {activeLoadError}
        </p>
        <button type="button" onClick={retryLoad}>
          Retry
        </button>
      </main>
    );
  }

  if (!activeScanReport) {
    return (
      <main className={styles.page}>
        <p>Loading scan report...</p>
        {slowScanId === scanId && (
          <p className={styles.notice} role="status" aria-live="polite">
            The local backend is busy; still waiting for the report.
          </p>
        )}
      </main>
    );
  }

  const blockedOperations = plan?.operations.filter((op) => op.status === "blocked") ?? [];
  const executionActive = executeJob?.status === "queued" || executeJob?.status === "running";
  const executionCompleted = executeJob?.status === "completed";
  const destinationsLocked = executionActive || pendingAction !== null;

  return (
    <main className={styles.page}>
      <h1>Plan move — scan #{scanId}</h1>

      {actionError && (
        <p className={styles.error} role="alert">
          {actionError}
        </p>
      )}
      {progressNotice && (
        <p className={styles.notice} role="status" aria-live="polite">
          {progressNotice}
        </p>
      )}
      {moveReportError && (
        <p className={styles.error} role="alert">
          Move report: {moveReportError}
        </p>
      )}

      <section className={styles.panel}>
        <h2>1. Destinations</h2>
        <p className={styles.helpText}>
          Enter a root folder for each group. The group name is added automatically as a
          subfolder; enable country folders to add one more level.
        </p>
        {unclassifiedCount > 0 && (
          <p className={styles.notice}>
            {unclassifiedCount} unclassified file{unclassifiedCount === 1 ? " is" : "s are"}
            {" excluded from move plans."}
          </p>
        )}
        {groups.map((group) => {
          const input = destinations[group] ?? {
            destinationRoot: "",
            countrySubfolderEnabled: false,
          };
          const previews = buildDestinationFolderPreviews(activeScanReport, group, input);
          const previewId = `destination-preview-${group}`;
          const groupCount = activeScanReport.totals_by_group[group] ?? 0;

          return (
            <div key={group} className={styles.destinationCard}>
              <h3 className={styles.groupHeading}>
                <code>{group}</code>
                <span>
                  {groupCount.toLocaleString()} file{groupCount === 1 ? "" : "s"}
                </span>
              </h3>
              <div className={styles.destinationRow}>
                <label className={styles.field}>
                  <span>Root destination folder</span>
                  <input
                    type="text"
                    placeholder="D:\Organized"
                    value={input.destinationRoot}
                    disabled={destinationsLocked}
                    aria-describedby={previewId}
                    onChange={(event) => {
                      setDestinations((current) => ({
                        ...current,
                        [group]: {
                          destinationRoot: event.target.value,
                          countrySubfolderEnabled:
                            current[group]?.countrySubfolderEnabled ?? false,
                        },
                      }));
                      invalidatePlan();
                    }}
                  />
                </label>
                <label className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={input.countrySubfolderEnabled}
                    disabled={destinationsLocked}
                    aria-describedby={previewId}
                    onChange={(event) => {
                      setDestinations((current) => ({
                        ...current,
                        [group]: {
                          destinationRoot: current[group]?.destinationRoot ?? "",
                          countrySubfolderEnabled: event.target.checked,
                        },
                      }));
                      invalidatePlan();
                    }}
                  />
                  Add country subfolders
                </label>
              </div>
              <div id={previewId} className={styles.destinationPreview}>
                <span className={styles.previewLabel}>Destination preview</span>
                {previews.length === 0 ? (
                  <p>Enter a root folder to see where these files will go.</p>
                ) : (
                  <ul>
                    {previews.map((preview) => (
                      <li key={preview.path}>
                        <code>{preview.path}</code>
                        <span>
                          {preview.fileCount.toLocaleString()} file
                          {preview.fileCount === 1 ? "" : "s"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          );
        })}
        <button
          type="button"
          onClick={() => void handleSaveDestinations()}
          disabled={destinationsLocked}
        >
          {pendingAction === "saving" ? "Saving..." : "Save destinations"}
        </button>
        {destinationsSaved && <p>Destinations saved.</p>}
      </section>

      {destinationsSaved && (
        <section className={styles.panel}>
          <h2>2. Dry-run plan</h2>
          <button
            type="button"
            onClick={() => void handleGeneratePlan()}
            disabled={pendingAction !== null || executionActive}
          >
            {pendingAction === "planning" ? "Generating..." : "Generate plan"}
          </button>

          {plan && (
            <>
              <dl className={styles.statusList}>
                <div>
                  <dt>Planned</dt>
                  <dd>{plan.total_planned}</dd>
                </div>
                <div>
                  <dt>Blocked</dt>
                  <dd>{plan.total_blocked}</dd>
                </div>
                <div>
                  <dt>Total bytes</dt>
                  <dd>{plan.total_bytes_planned.toLocaleString()}</dd>
                </div>
              </dl>

              {blockedOperations.length > 0 && (
                <>
                  <h3>Conflicts &amp; alerts</h3>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Destination</th>
                        <th>Error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {blockedOperations.map((op) => (
                        <tr key={op.id}>
                          <td>{op.planned_destination_path}</td>
                          <td>
                            {op.error_code}: {op.error_message}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </>
          )}
        </section>
      )}

      {plan && (
        <section className={styles.panel}>
          <h2>3. Confirm &amp; execute</h2>
          <button
            type="button"
            onClick={() => void handleApprove()}
            disabled={!!plan.approved_at || pendingAction !== null || executionActive}
          >
            {pendingAction === "approving"
              ? "Approving..."
              : plan.approved_at
                ? "Approved"
                : "Approve plan"}
          </button>
          <button
            type="button"
            onClick={() => void handleExecute()}
            disabled={
              !plan.approved_at ||
              pendingAction !== null ||
              executionActive ||
              executionCompleted
            }
          >
            {pendingAction === "executing"
              ? "Starting..."
              : executeJob?.status === "failed" || executeJob?.status === "cancelled"
                ? "Resume execution"
                : "Execute"}
          </button>
        </section>
      )}

      {executeJob && (
        <section className={styles.panel}>
          <h2>Execution progress</h2>
          <dl className={styles.statusList}>
            <div>
              <dt>Status</dt>
              <dd>{executeJob.status}</dd>
            </div>
            <div>
              <dt>Files processed</dt>
              <dd>
                {executeJob.processed}
                {executeJob.total > 0 ? ` / ${executeJob.total}` : ""}
              </dd>
            </div>
            {connectionState && (
              <div>
                <dt>Progress connection</dt>
                <dd>{connectionState}</dd>
              </div>
            )}
            {executeJob.message && (
              <div>
                <dt>Message</dt>
                <dd>{executeJob.message}</dd>
              </div>
            )}
          </dl>
          {(executeJob.error_code || executeJob.error_message) && (
            <p className={styles.error} role="alert">
              {executeJob.error_code && `${executeJob.error_code}: `}
              {executeJob.error_message ?? "Execution failed."}
            </p>
          )}
        </section>
      )}

      {moveReport && (
        <section className={styles.panel}>
          <h2>Move report</h2>
          <dl className={styles.statusList}>
            <div>
              <dt>Completed</dt>
              <dd>{moveReport.totals.completed}</dd>
            </div>
            <div>
              <dt>Failed</dt>
              <dd>{moveReport.totals.failed}</dd>
            </div>
            <div>
              <dt>Skipped</dt>
              <dd>{moveReport.totals.skipped}</dd>
            </div>
            <div>
              <dt>Bytes moved</dt>
              <dd>{moveReport.totals.bytes_moved.toLocaleString()}</dd>
            </div>
          </dl>

          {moveReport.operations.some((op) => op.status === "failed") && (
            <>
              <h3>Failed operations</h3>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Error</th>
                  </tr>
                </thead>
                <tbody>
                  {moveReport.operations
                    .filter((op) => op.status === "failed")
                    .map((op) => (
                      <tr key={op.media_file_id}>
                        <td>{op.source_path}</td>
                        <td>
                          {op.error_code}: {op.error_message}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </>
          )}
        </section>
      )}
    </main>
  );
}
