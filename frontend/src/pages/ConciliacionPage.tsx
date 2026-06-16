/**
 * ConciliacionPage — orchestrates the 5-step mapping + processing wizard (T-4.6).
 *
 * Owns:
 *   - All wizard state via useWizardState()
 *   - API side-effects (createRun, uploadFile, getPreview, confirmMapping,
 *                       triggerProcess, getRunStatus)
 *   - Step navigation
 *
 * Children (step components) receive state slices and callbacks; they never
 * call the API directly — all I/O is here.
 */

import { useRef, type JSX } from "react";
import { StepIndicator } from "../components/wizard/StepIndicator";
import { Step1Upload } from "../components/wizard/steps/Step1Upload";
import { Step2SheetPicker } from "../components/wizard/steps/Step2SheetPicker";
import { Step3Mapping } from "../components/wizard/steps/Step3Mapping";
import { Step4Summary } from "../components/wizard/steps/Step4Summary";
import { Step5Progress } from "../components/wizard/steps/Step5Progress";
import { Step6Dashboard } from "../components/wizard/steps/Step6Dashboard";
import { useWizardState } from "../hooks/useWizardState";
import * as api from "../api/ingestion";
import * as reportingApi from "../api/reporting";
import type { FileRole } from "../types/ingestion";

export function ConciliacionPage(): JSX.Element {
  const { state, dispatch, allFilesUploaded, allMappingsConfirmed, excelRoles } =
    useWizardState();

  /**
   * Ensures a run is created exactly once even if multiple uploads fire
   * concurrently. The promise is cached in a ref.
   */
  const runPromiseRef = useRef<Promise<number> | null>(null);

  const ensureRun = (): Promise<number> => {
    if (state.runId !== null) return Promise.resolve(state.runId);
    if (runPromiseRef.current !== null) return runPromiseRef.current;

    const p = api.createRun().then((run) => {
      dispatch({ type: "SET_RUN_ID", runId: run.id });
      return run.id;
    });
    runPromiseRef.current = p;
    return p;
  };

  // ---------------------------------------------------------------------------
  // Step 1 — upload
  // ---------------------------------------------------------------------------

  const handleFile = async (role: FileRole, file: File): Promise<void> => {
    dispatch({ type: "FILE_SELECTED", role, file });
    dispatch({ type: "FILE_UPLOADING", role });
    try {
      const runId = await ensureRun();
      const sourceFile = await api.uploadFile(runId, role, file);
      dispatch({ type: "FILE_UPLOADED", role, sourceFile });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error desconocido al subir";
      dispatch({ type: "FILE_UPLOAD_ERROR", role, error: msg });
    }
  };

  // ---------------------------------------------------------------------------
  // Step 2 — sheet selection
  // ---------------------------------------------------------------------------

  const handleSheetChange = (role: FileRole, sheet: string): void => {
    dispatch({ type: "SHEET_SELECTED", role, sheet });
  };

  // ---------------------------------------------------------------------------
  // Preview fetch (used in Step 2 and Step 3)
  // ---------------------------------------------------------------------------

  const handleFetchPreview = async (role: FileRole, sheet?: string): Promise<void> => {
    const { sourceFileId } = state.files[role];
    if (state.runId === null || sourceFileId === null) return;

    dispatch({ type: "PREVIEW_LOADING", role });
    try {
      const preview = await api.getPreview(state.runId, sourceFileId, sheet);
      dispatch({ type: "PREVIEW_LOADED", role, preview });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error al cargar la vista previa";
      dispatch({ type: "PREVIEW_ERROR", role, error: msg });
    }
  };

  // ---------------------------------------------------------------------------
  // Step 3 — mapping
  // ---------------------------------------------------------------------------

  const handleMappingChange = (
    role: FileRole,
    logicalField: string,
    columnIndex: number
  ): void => {
    dispatch({ type: "MAPPING_CHANGED", role, logicalField, columnIndex });
  };

  const handleConfirmMapping = async (role: FileRole): Promise<void> => {
    const { sourceFileId, pendingMappings, preview } = state.files[role];
    if (state.runId === null || sourceFileId === null || !preview) return;

    const mappings = Object.entries(pendingMappings).map(([logical_field, column_index]) => ({
      logical_field,
      column_index,
      was_suggested:
        preview.suggestions[logical_field]?.column_index === column_index ||
        preview.remembered_mappings?.[logical_field]?.column_index === column_index,
    }));

    try {
      const result = await api.confirmMapping(state.runId, sourceFileId, mappings);
      dispatch({ type: "MAPPING_CONFIRMED", role, warnings: result.warnings });
    } catch (err) {
      // Surface the error via PREVIEW_ERROR so the user sees it in the panel
      const msg = err instanceof Error ? err.message : "Error al confirmar mapeo";
      dispatch({ type: "PREVIEW_ERROR", role, error: msg });
    }
  };

  // ---------------------------------------------------------------------------
  // Step 4 → Step 5: trigger process and advance wizard
  // ---------------------------------------------------------------------------

  const handleProcess = (): void => {
    if (!allMappingsConfirmed || state.runId === null) return;
    dispatch({ type: "SET_STEP", step: 5 });
  };

  // ---------------------------------------------------------------------------
  // Step 5 — process API callbacks (passed as props to keep Step5 side-effect-free)
  // ---------------------------------------------------------------------------

  const handleTriggerProcess = async (): Promise<string> => {
    if (state.runId === null) throw new Error("No hay un run activo");
    const res = await api.triggerProcess(state.runId);
    return res.status_url;
  };

  const handlePollStatus = async () => {
    if (state.runId === null) throw new Error("No hay un run activo");
    return api.getRunStatus(state.runId);
  };

  const handleFetchMetrics = async () => {
    if (state.runId === null) throw new Error("No hay un run activo");
    return reportingApi.getRunMetrics(state.runId);
  };

  const handleFetchFamilies = async () => {
    if (state.runId === null) throw new Error("No hay un run activo");
    return reportingApi.getFamiliesReport(state.runId);
  };

  const handleFetchCatalog = async (query: { page?: number; page_size?: number } = {}) => {
    if (state.runId === null) throw new Error("No hay un run activo");
    return reportingApi.getCatalogHealth(state.runId, {
      page: query.page ?? 1,
      page_size: query.page_size ?? 50,
    });
  };

  const handleFetchSkusForCode = async (
    familyCode: string,
    errorCode: string,
    page = 1,
  ) => {
    if (state.runId === null) throw new Error("No hay un run activo");
    return reportingApi.getSkuDetail(state.runId, {
      family: familyCode,
      code: errorCode,
      page,
      page_size: 50,
    });
  };

  const handleExportReport = async (format: "xlsx" | "csv") => {
    if (state.runId === null) throw new Error("No hay un run activo");
    await reportingApi.exportRunReport(state.runId, format);
  };

  const handleViewDashboard = (): void => {
    dispatch({ type: "SET_STEP", step: 6 });
  };

  // ---------------------------------------------------------------------------
  // Navigation helpers
  // ---------------------------------------------------------------------------

  const goTo = (step: 1 | 2 | 3 | 4 | 5 | 6) => () =>
    dispatch({ type: "SET_STEP", step });

  const advanceToStep2 = () => {
    // If no Excel files, skip step 2 entirely
    if (excelRoles.length === 0) {
      dispatch({ type: "SET_STEP", step: 3 });
    } else {
      dispatch({ type: "SET_STEP", step: 2 });
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div style={styles.page}>
      <div style={styles.inner}>
        <StepIndicator currentStep={state.step} />

        {state.step === 1 && (
          <Step1Upload
            files={state.files}
            onFile={handleFile}
            onNext={advanceToStep2}
            allUploaded={allFilesUploaded}
          />
        )}

        {state.step === 2 && (
          <Step2SheetPicker
            files={state.files}
            excelRoles={excelRoles}
            onSheetChange={handleSheetChange}
            onNext={goTo(3)}
            onBack={goTo(1)}
            onFetchPreview={handleFetchPreview}
          />
        )}

        {state.step === 3 && (
          <Step3Mapping
            files={state.files}
            onFetchPreview={handleFetchPreview}
            onMappingChange={handleMappingChange}
            onConfirmMapping={handleConfirmMapping}
            onNext={goTo(4)}
            onBack={goTo(2)}
            allConfirmed={allMappingsConfirmed}
          />
        )}

        {state.step === 4 && (
          <Step4Summary
            runId={state.runId}
            files={state.files}
            allConfirmed={allMappingsConfirmed}
            onProcess={handleProcess}
            onBack={goTo(3)}
          />
        )}

        {state.step === 5 && state.runId !== null && (
          <Step5Progress
            runId={state.runId}
            onProcess={handleTriggerProcess}
            onPollStatus={handlePollStatus}
            onViewDashboard={handleViewDashboard}
          />
        )}

        {state.step === 6 && state.runId !== null && (
          <Step6Dashboard
            runId={state.runId}
            onFetchMetrics={handleFetchMetrics}
            onFetchFamilies={handleFetchFamilies}
            onFetchCatalog={handleFetchCatalog}
            onFetchSkusForCode={handleFetchSkusForCode}
            onExport={handleExportReport}
            onBack={goTo(5)}
          />
        )}
      </div>
    </div>
  );
}

const styles = {
  page: {
    padding: "32px",
    minHeight: "100%",
  },
  inner: {
    maxWidth: "1100px",
    margin: "0 auto",
    backgroundColor: "var(--color-surface)",
    borderRadius: "var(--radius-lg)",
    border: "1px solid var(--color-border)",
    padding: "32px",
  },
} as const;
