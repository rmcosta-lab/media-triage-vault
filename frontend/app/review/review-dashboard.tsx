"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { createColumnHelper, tableFeatures, useTable } from "@tanstack/react-table";
import styles from "./review.module.css";
import {
  ApiError,
  ROUTING_GROUPS,
  getApiBaseUrl,
  getScanReport,
  overrideClassification,
  type ScanReport,
  type ScanReportFile,
} from "@/lib/api";

type ConfidenceBand = "all" | "high" | "medium" | "low";

function matchesConfidenceBand(confidence: number | null, band: ConfidenceBand): boolean {
  if (band === "all") return true;
  if (confidence === null) return false;
  if (band === "high") return confidence >= 0.85;
  if (band === "medium") return confidence >= 0.6 && confidence < 0.85;
  return confidence < 0.6;
}

function thumbnailUrl(fileId: number): string {
  return `${getApiBaseUrl()}/api/files/${fileId}/thumbnail`;
}

// TanStack Table v9: features/column-helper are stable inputs, created once
// at module scope rather than per render (see the library's own "core" skill).
const tableFeatureSet = tableFeatures({});
const columnHelper = createColumnHelper<typeof tableFeatureSet, ScanReportFile>();

export default function ReviewDashboard() {
  const searchParams = useSearchParams();
  const scanId = Number(searchParams.get("scanId"));

  const invalidScanId = !Number.isFinite(scanId);

  const [report, setReport] = useState<ScanReport | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [refetchToken, setRefetchToken] = useState(0);
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [overrideError, setOverrideError] = useState<string | null>(null);

  const [groupFilter, setGroupFilter] = useState("all");
  const [confidenceFilter, setConfidenceFilter] = useState<ConfidenceBand>("all");
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [countryFilter, setCountryFilter] = useState("all");

  // Effect fetches on mount and whenever scanId/refetchToken changes; setState
  // only ever happens inside the .then()/.catch() callbacks, guarded by
  // `cancelled`, per React's documented data-fetching pattern.
  useEffect(() => {
    if (invalidScanId) return;
    let cancelled = false;
    getScanReport(scanId)
      .then((data) => {
        if (!cancelled) {
          setReport(data);
          setFetchError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setFetchError(err instanceof ApiError ? err.message : "Could not load the scan report.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [scanId, invalidScanId, refetchToken]);

  const error = invalidScanId ? "No scanId provided in the URL." : fetchError;

  const files = useMemo(() => report?.files ?? [], [report]);

  const groups = useMemo(
    () => Array.from(new Set(files.map((file) => file.routing_group))).sort(),
    [files],
  );
  const countries = useMemo(
    () =>
      Array.from(new Set(files.map((file) => file.country_code).filter((code) => code !== null)))
        .sort(),
    [files],
  );

  const filteredFiles = useMemo(() => {
    return files.filter((file) => {
      if (groupFilter !== "all" && file.routing_group !== groupFilter) return false;
      if (!matchesConfidenceBand(file.confidence, confidenceFilter)) return false;
      if (errorsOnly && file.error_code === null) return false;
      if (countryFilter !== "all" && file.country_code !== countryFilter) return false;
      return true;
    });
  }, [files, groupFilter, confidenceFilter, errorsOnly, countryFilter]);

  const columns = useMemo(
    () =>
      columnHelper.columns([
        columnHelper.display({
          id: "thumbnail",
          header: "",
          cell: ({ row }) => (
            // eslint-disable-next-line @next/next/no-img-element -- local, dynamic API-served images
            <img
              src={thumbnailUrl(row.original.media_file_id)}
              alt=""
              width={48}
              height={48}
              className={styles.thumbnail}
              loading="lazy"
            />
          ),
        }),
        columnHelper.accessor("relative_path", { header: "Name" }),
        columnHelper.accessor("media_kind", { header: "Kind" }),
        columnHelper.display({
          id: "routing_group",
          header: "Group",
          cell: ({ row }) => (
            <span>
              {row.original.routing_group}
              {row.original.manual_override && (
                <span className={styles.manualBadge}>manual</span>
              )}
            </span>
          ),
        }),
        columnHelper.display({
          id: "confidence",
          header: "Confidence",
          cell: ({ row }) =>
            row.original.confidence === null
              ? "—"
              : `${Math.round(row.original.confidence * 100)}%`,
        }),
        columnHelper.display({
          id: "country",
          header: "Country",
          cell: ({ row }) => row.original.country_name ?? row.original.country_code ?? "—",
        }),
        columnHelper.display({
          id: "error",
          header: "Error",
          cell: ({ row }) => row.original.error_code ?? "—",
        }),
      ]),
    [],
  );

  const table = useTable({
    features: tableFeatureSet,
    data: filteredFiles,
    columns,
  });

  const selectedFile = files.find((file) => file.media_file_id === selectedFileId) ?? null;

  async function handleOverride(routingGroup: string) {
    if (!selectedFile) return;
    setOverrideError(null);
    try {
      await overrideClassification(selectedFile.media_file_id, routingGroup);
      setRefetchToken((token) => token + 1);
    } catch (err) {
      setOverrideError(
        err instanceof ApiError ? err.message : "Could not save the override.",
      );
    }
  }

  if (error) {
    return (
      <main className={styles.page}>
        <p className={styles.error} role="alert">
          {error}
        </p>
      </main>
    );
  }

  if (!report) {
    return (
      <main className={styles.page}>
        <p>Loading scan report…</p>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <h1>Review — scan #{scanId}</h1>
      <Link href={`/plan?scanId=${scanId}`}>Plan move →</Link>

      <div className={styles.filters}>
        <label>
          Group
          <select value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}>
            <option value="all">All</option>
            {groups.map((group) => (
              <option key={group} value={group}>
                {group}
              </option>
            ))}
          </select>
        </label>
        <label>
          Confidence
          <select
            value={confidenceFilter}
            onChange={(event) => setConfidenceFilter(event.target.value as ConfidenceBand)}
          >
            <option value="all">All</option>
            <option value="high">High (≥85%)</option>
            <option value="medium">Medium (60-85%)</option>
            <option value="low">Low (&lt;60%)</option>
          </select>
        </label>
        <label>
          Country
          <select
            value={countryFilter}
            onChange={(event) => setCountryFilter(event.target.value)}
          >
            <option value="all">All</option>
            {countries.map((code) => (
              <option key={code} value={code ?? ""}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.checkboxLabel}>
          <input
            type="checkbox"
            checked={errorsOnly}
            onChange={(event) => setErrorsOnly(event.target.checked)}
          />
          Errors only
        </label>
      </div>

      <div className={styles.layout}>
        <table className={styles.table}>
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id}>
                    {header.isPlaceholder ? null : <table.FlexRender header={header} />}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                onClick={() => setSelectedFileId(row.original.media_file_id)}
                className={
                  row.original.media_file_id === selectedFileId ? styles.selectedRow : undefined
                }
              >
                {row.getAllCells().map((cell) => (
                  <td key={cell.id}>
                    <table.FlexRender cell={cell} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>

        {selectedFile && (
          <aside className={styles.detailPanel}>
            <h2>{selectedFile.relative_path}</h2>

            <label className={styles.field}>
              <span>Routing group</span>
              <select
                value={selectedFile.routing_group}
                onChange={(event) => void handleOverride(event.target.value)}
              >
                {ROUTING_GROUPS.map((group) => (
                  <option key={group} value={group}>
                    {group}
                  </option>
                ))}
              </select>
            </label>
            {overrideError && (
              <p className={styles.error} role="alert">
                {overrideError}
              </p>
            )}

            <dl className={styles.detailList}>
              <div>
                <dt>Source origin</dt>
                <dd>{selectedFile.source_origin ?? "—"}</dd>
              </div>
              <div>
                <dt>Image format</dt>
                <dd>{selectedFile.image_format ?? "—"}</dd>
              </div>
              <div>
                <dt>Device</dt>
                <dd>
                  {[selectedFile.make, selectedFile.model].filter(Boolean).join(" ") || "—"}
                </dd>
              </div>
              <div>
                <dt>Software</dt>
                <dd>{selectedFile.software ?? "—"}</dd>
              </div>
              <div>
                <dt>Captured</dt>
                <dd>{selectedFile.capture_datetime ?? "—"}</dd>
              </div>
              <div>
                <dt>Country</dt>
                <dd>{selectedFile.country_name ?? "—"}</dd>
              </div>
              {selectedFile.error_code && (
                <div>
                  <dt>Error</dt>
                  <dd>
                    {selectedFile.error_code}: {selectedFile.error_message}
                  </dd>
                </div>
              )}
            </dl>

            <h3>Reasons</h3>
            <ul>
              {selectedFile.reasons.map((reason, index) => (
                <li key={index}>{reason}</li>
              ))}
            </ul>
          </aside>
        )}
      </div>
    </main>
  );
}
