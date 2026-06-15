/**
 * useWizardState — unit tests for the wizard reducer (T-3.9).
 *
 * Covers:
 *   - Initial state
 *   - File upload lifecycle (selected → uploading → uploaded / error)
 *   - Preview lifecycle (loading → loaded with pre-filled suggestions → error)
 *   - Mapping confirmed gate (RNF-08)
 *   - RESET action
 */

import { renderHook, act } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { useWizardState } from "../../hooks/useWizardState";
import type { PreviewResponse, SourceFileResponse } from "../../types/ingestion";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockSourceFile: SourceFileResponse = {
  id: 42,
  run_id: 1,
  role: "occ_top",
  original_filename: "libro1.xlsx",
  sha256: "abc123",
  total_rows: 100,
  discarded_rows: 0,
  uploaded_at: "2026-06-15T10:00:00Z",
};

const mockPreview: PreviewResponse = {
  file_role: "occ_top",
  sheet: "Plantilla",
  available_sheets: [
    { name: "Plantilla", rows: 100 },
    { name: "Hoja2", rows: 50 },
  ],
  block: null,
  headers: [
    { index: 0, name: "SKU", technical_name: null },
    { index: 1, name: "Stock", technical_name: null },
    { index: 2, name: "Precio", technical_name: null },
  ],
  sample_rows: [
    ["SKU001", "10", "19.99"],
    ["SKU002", "5", "29.99"],
  ],
  suggestions: {
    sku: { column_index: 0, confidence: 0.95, reason: "column name exactly matches 'sku'" },
    stock: { column_index: 1, confidence: 0.95, reason: "column name exactly matches 'stock'" },
  },
  warnings: [],
  discarded_rows: 0,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useWizardState", () => {
  it("starts at step 1 with idle files", () => {
    const { result } = renderHook(() => useWizardState());
    expect(result.current.state.step).toBe(1);
    expect(result.current.state.runId).toBeNull();
    expect(result.current.state.files.occ_top.uploadStatus).toBe("idle");
    expect(result.current.state.files.wm_feed.uploadStatus).toBe("idle");
    expect(result.current.state.files.amazon_report.uploadStatus).toBe("idle");
  });

  it("allFilesUploaded is false until all three files are uploaded", () => {
    const { result } = renderHook(() => useWizardState());

    act(() => {
      result.current.dispatch({
        type: "FILE_UPLOADED",
        role: "occ_top",
        sourceFile: { ...mockSourceFile, role: "occ_top" },
      });
    });
    expect(result.current.allFilesUploaded).toBe(false);

    act(() => {
      result.current.dispatch({
        type: "FILE_UPLOADED",
        role: "wm_feed",
        sourceFile: { ...mockSourceFile, id: 43, role: "wm_feed" },
      });
    });
    expect(result.current.allFilesUploaded).toBe(false);

    act(() => {
      result.current.dispatch({
        type: "FILE_UPLOADED",
        role: "amazon_report",
        sourceFile: { ...mockSourceFile, id: 44, role: "amazon_report" },
      });
    });
    expect(result.current.allFilesUploaded).toBe(true);
  });

  it("stores upload error correctly", () => {
    const { result } = renderHook(() => useWizardState());
    act(() => {
      result.current.dispatch({
        type: "FILE_UPLOAD_ERROR",
        role: "wm_feed",
        error: "El fichero supera el límite de 50 MB",
      });
    });
    expect(result.current.state.files.wm_feed.uploadStatus).toBe("error");
    expect(result.current.state.files.wm_feed.uploadError).toBe(
      "El fichero supera el límite de 50 MB"
    );
  });

  it("PREVIEW_LOADED pre-fills pending mappings from suggestions", () => {
    const { result } = renderHook(() => useWizardState());
    act(() => {
      result.current.dispatch({ type: "PREVIEW_LOADED", role: "occ_top", preview: mockPreview });
    });
    const { pendingMappings, preview } = result.current.state.files.occ_top;
    expect(preview).not.toBeNull();
    // Pre-filled from suggestions
    expect(pendingMappings["sku"]).toBe(0);
    expect(pendingMappings["stock"]).toBe(1);
  });

  it("MAPPING_CHANGED updates a single field without affecting others", () => {
    const { result } = renderHook(() => useWizardState());
    act(() => {
      result.current.dispatch({ type: "PREVIEW_LOADED", role: "occ_top", preview: mockPreview });
    });
    act(() => {
      result.current.dispatch({ type: "MAPPING_CHANGED", role: "occ_top", logicalField: "sku", columnIndex: 2 });
    });
    expect(result.current.state.files.occ_top.pendingMappings["sku"]).toBe(2);
    expect(result.current.state.files.occ_top.pendingMappings["stock"]).toBe(1); // unchanged
  });

  it("MAPPING_CHANGED resets mappingConfirmed", () => {
    const { result } = renderHook(() => useWizardState());
    act(() => {
      result.current.dispatch({ type: "MAPPING_CONFIRMED", role: "occ_top", warnings: [] });
    });
    expect(result.current.state.files.occ_top.mappingConfirmed).toBe(true);

    act(() => {
      result.current.dispatch({ type: "MAPPING_CHANGED", role: "occ_top", logicalField: "sku", columnIndex: 2 });
    });
    // Changing a selection should unconfirm
    expect(result.current.state.files.occ_top.mappingConfirmed).toBe(false);
  });

  it("allMappingsConfirmed is false until all three files are confirmed (RNF-08)", () => {
    const { result } = renderHook(() => useWizardState());

    act(() => {
      result.current.dispatch({ type: "MAPPING_CONFIRMED", role: "occ_top", warnings: [] });
      result.current.dispatch({ type: "MAPPING_CONFIRMED", role: "wm_feed", warnings: [] });
    });
    expect(result.current.allMappingsConfirmed).toBe(false);

    act(() => {
      result.current.dispatch({
        type: "MAPPING_CONFIRMED",
        role: "amazon_report",
        warnings: [],
      });
    });
    expect(result.current.allMappingsConfirmed).toBe(true);
  });

  it("SHEET_SELECTED resets preview and mapping for that role", () => {
    const { result } = renderHook(() => useWizardState());
    act(() => {
      result.current.dispatch({ type: "PREVIEW_LOADED", role: "occ_top", preview: mockPreview });
      result.current.dispatch({ type: "MAPPING_CONFIRMED", role: "occ_top", warnings: [] });
    });
    act(() => {
      result.current.dispatch({ type: "SHEET_SELECTED", role: "occ_top", sheet: "Hoja2" });
    });
    const f = result.current.state.files.occ_top;
    expect(f.preview).toBeNull();
    expect(f.previewStatus).toBe("idle");
    expect(f.mappingConfirmed).toBe(false);
    expect(f.selectedSheet).toBe("Hoja2");
  });

  it("SET_RUN_ID stores the run id", () => {
    const { result } = renderHook(() => useWizardState());
    act(() => {
      result.current.dispatch({ type: "SET_RUN_ID", runId: 99 });
    });
    expect(result.current.state.runId).toBe(99);
  });

  it("RESET returns to initial state", () => {
    const { result } = renderHook(() => useWizardState());
    act(() => {
      result.current.dispatch({ type: "SET_RUN_ID", runId: 99 });
      result.current.dispatch({ type: "SET_STEP", step: 4 });
      result.current.dispatch({ type: "MAPPING_CONFIRMED", role: "occ_top", warnings: [] });
    });
    act(() => {
      result.current.dispatch({ type: "RESET" });
    });
    expect(result.current.state.runId).toBeNull();
    expect(result.current.state.step).toBe(1);
    expect(result.current.state.files.occ_top.mappingConfirmed).toBe(false);
  });

  it("excelRoles returns only Excel file roles", () => {
    const { result } = renderHook(() => useWizardState());
    const xlsxFile = new File([""], "libro1.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    const csvFile = new File([""], "feed.csv", { type: "text/csv" });
    const xlsmFile = new File([""], "report.xlsm", { type: "application/vnd.ms-excel.sheet.macroEnabled.12" });

    act(() => {
      result.current.dispatch({ type: "FILE_SELECTED", role: "occ_top", file: xlsxFile });
      result.current.dispatch({ type: "FILE_SELECTED", role: "wm_feed", file: csvFile });
      result.current.dispatch({ type: "FILE_SELECTED", role: "amazon_report", file: xlsmFile });
    });

    expect(result.current.excelRoles).toContain("occ_top");
    expect(result.current.excelRoles).not.toContain("wm_feed");
    expect(result.current.excelRoles).toContain("amazon_report");
  });
});
