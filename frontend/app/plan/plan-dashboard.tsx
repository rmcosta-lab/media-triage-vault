"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import styles from "./plan.module.css";
import {
  ApiError,
  approveMovePlan,
  createMovePlan,
  executeMovePlan,
  getMoveRunReport,
  getScanReport,
  isJobTerminal,
  putDestinations,
  subscribeJobEvents,
  type Job,
  type MovePlan,
  type MoveReport,
  type ScanReport,
} from "@/lib/api";

interface DestinationInput {
  destinationRoot: string;
  countrySubfolderEnabled: boolean;
}

export default function PlanDashboard() {
  const searchParams = useSearchParams();
  const scanId = Number(searchParams.get("scanId"));
  const invalidScanId = !Number.isFinite(scanId);

  const [scanReport, setScanReport] = useState<ScanReport | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [destinations, setDestinations] = useState<Record<string, DestinationInput>>({});
  const [destinationsSaved, setDestinationsSaved] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const [plan, setPlan] = useState<MovePlan | null>(null);
  const [executeJob, setExecuteJob] = useState<Job | null>(null);
  const [moveReport, setMoveReport] = useState<MoveReport | null>(null);

  useEffect(() => {
    if (invalidScanId) return;
    let cancelled = false;
    getScanReport(scanId)
      .then((data) => {
        if (cancelled) return;
        setScanReport(data);
        setDestinations((current) => {
          if (Object.keys(current).length > 0) return current;
          const initial: Record<string, DestinationInput> = {};
          for (const group of Object.keys(data.totals_by_group)) {
            initial[group] = { destinationRoot: "", countrySubfolderEnabled: false };
          }
          return initial;
        });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(err instanceof ApiError ? err.message : "Could not load the scan report.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [scanId, invalidScanId]);

  const groups = useMemo(
    () => Object.keys(scanReport?.totals_by_group ?? {}).sort(),
    [scanReport],
  );

  async function handleSaveDestinations() {
    setActionError(null);
    const mapping: Record<string, { destination_root: string; country_subfolder_enabled: boolean }> =
      {};
    for (const [group, input] of Object.entries(destinations)) {
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
    try {
      await putDestinations(scanId, mapping);
      setDestinationsSaved(true);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not save destinations.");
    }
  }

  async function handleGeneratePlan() {
    setActionError(null);
    try {
      setPlan(await createMovePlan(scanId));
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not generate the plan.");
    }
  }

  async function handleApprove() {
    if (!plan) return;
    setActionError(null);
    try {
      setPlan(await approveMovePlan(plan.id));
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not approve the plan.");
    }
  }

  async function handleExecute() {
    if (!plan) return;
    setActionError(null);
    try {
      const job = await executeMovePlan(plan.id);
      setExecuteJob(job);
      const unsubscribe = subscribeJobEvents(job.id, (updated) => {
        setExecuteJob(updated);
        if (isJobTerminal(updated)) {
          unsubscribe();
          getMoveRunReport(updated.id)
            .then(setMoveReport)
            .catch((err: unknown) => {
              setActionError(
                err instanceof ApiError ? err.message : "Could not load the move report.",
              );
            });
        }
      });
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not start execution.");
    }
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

  if (loadError) {
    return (
      <main className={styles.page}>
        <p className={styles.error} role="alert">
          {loadError}
        </p>
      </main>
    );
  }

  if (!scanReport) {
    return (
      <main className={styles.page}>
        <p>Loading scan report…</p>
      </main>
    );
  }

  const blockedOperations = plan?.operations.filter((op) => op.status === "blocked") ?? [];

  return (
    <main className={styles.page}>
      <h1>Plan move — scan #{scanId}</h1>

      {actionError && (
        <p className={styles.error} role="alert">
          {actionError}
        </p>
      )}

      <section className={styles.panel}>
        <h2>1. Destinations</h2>
        {groups.map((group) => (
          <div key={group} className={styles.destinationRow}>
            <label className={styles.field}>
              <span>{group}</span>
              <input
                type="text"
                placeholder="D:\Organized\..."
                value={destinations[group]?.destinationRoot ?? ""}
                onChange={(event) =>
                  setDestinations((current) => ({
                    ...current,
                    [group]: {
                      destinationRoot: event.target.value,
                      countrySubfolderEnabled: current[group]?.countrySubfolderEnabled ?? false,
                    },
                  }))
                }
              />
            </label>
            <label className={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={destinations[group]?.countrySubfolderEnabled ?? false}
                onChange={(event) =>
                  setDestinations((current) => ({
                    ...current,
                    [group]: {
                      destinationRoot: current[group]?.destinationRoot ?? "",
                      countrySubfolderEnabled: event.target.checked,
                    },
                  }))
                }
              />
              Country subfolder
            </label>
          </div>
        ))}
        <button type="button" onClick={() => void handleSaveDestinations()}>
          Save destinations
        </button>
        {destinationsSaved && <p>Destinations saved.</p>}
      </section>

      {destinationsSaved && (
        <section className={styles.panel}>
          <h2>2. Dry-run plan</h2>
          <button type="button" onClick={() => void handleGeneratePlan()}>
            Generate plan
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
          <button type="button" onClick={() => void handleApprove()} disabled={!!plan.approved_at}>
            {plan.approved_at ? "Approved" : "Approve plan"}
          </button>
          <button type="button" onClick={() => void handleExecute()} disabled={!plan.approved_at || !!executeJob}>
            Execute
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
              <dd>{executeJob.processed}</dd>
            </div>
          </dl>
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
