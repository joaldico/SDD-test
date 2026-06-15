/**
 * useWizardState — central state machine for the mapping wizard (T-3.9).
 *
 * Manages state across all 4 steps using useReducer for predictable updates.
 * All API side-effects are performed outside this hook (in ConciliacionPage)
 * and pushed in via dispatch actions.
 */

import { useReducer } from "react";
import type { FileRole, MappingResponse, PreviewResponse, SourceFileResponse } from "../types/ingestion";
export type { FileRole } from "../types/ingestion";

// ---------------------------------------------------------------------------
// Per-file state shape
// ---------------------------------------------------------------------------

export interface FileWizardState {
  /** User-selected File object from the drop zone */
  file: File | null;
  uploadStatus: "idle" | "uploading" | "uploaded" | "error";
  sourceFileId: number | null;
  uploadError: string | null;

  /** Step 2: selected sheet name (null = use backend default) */
  selectedSheet: string | null;

  /** Step 3: preview fetched from GET .../preview */
  preview: PreviewResponse | null;
  previewStatus: "idle" | "loading" | "loaded" | "error";
  previewError: string | null;

  /**
   * Step 3: current UI selection — logicalField → columnIndex.
   * Pre-filled from suggestions on preview load.
   */
  pendingMappings: Record<string, number>;

  /** Step 3: mapping confirmed via PUT .../mapping */
  mappingConfirmed: boolean;
  mappingWarnings: MappingResponse["warnings"];
}

// ---------------------------------------------------------------------------
// Global wizard state
// ---------------------------------------------------------------------------

export interface WizardState {
  step: 1 | 2 | 3 | 4;
  runId: number | null;
  files: Record<FileRole, FileWizardState>;
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

export type WizardAction =
  | { type: "SET_STEP"; step: 1 | 2 | 3 | 4 }
  | { type: "SET_RUN_ID"; runId: number }
  | { type: "FILE_SELECTED"; role: FileRole; file: File }
  | { type: "FILE_UPLOADING"; role: FileRole }
  | { type: "FILE_UPLOADED"; role: FileRole; sourceFile: SourceFileResponse }
  | { type: "FILE_UPLOAD_ERROR"; role: FileRole; error: string }
  | { type: "SHEET_SELECTED"; role: FileRole; sheet: string }
  | { type: "PREVIEW_LOADING"; role: FileRole }
  | { type: "PREVIEW_LOADED"; role: FileRole; preview: PreviewResponse }
  | { type: "PREVIEW_ERROR"; role: FileRole; error: string }
  | { type: "MAPPING_CHANGED"; role: FileRole; logicalField: string; columnIndex: number }
  | { type: "MAPPING_CONFIRMED"; role: FileRole; warnings: MappingResponse["warnings"] }
  | { type: "RESET" };

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const defaultFileState: FileWizardState = {
  file: null,
  uploadStatus: "idle",
  sourceFileId: null,
  uploadError: null,
  selectedSheet: null,
  preview: null,
  previewStatus: "idle",
  previewError: null,
  pendingMappings: {},
  mappingConfirmed: false,
  mappingWarnings: [],
};

const initialState: WizardState = {
  step: 1,
  runId: null,
  files: {
    occ_top: { ...defaultFileState },
    wm_feed: { ...defaultFileState },
    amazon_report: { ...defaultFileState },
  },
};

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------

function updateFile(
  state: WizardState,
  role: FileRole,
  patch: Partial<FileWizardState>
): WizardState {
  return {
    ...state,
    files: {
      ...state.files,
      [role]: { ...state.files[role], ...patch },
    },
  };
}

function reducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case "SET_STEP":
      return { ...state, step: action.step };

    case "SET_RUN_ID":
      return { ...state, runId: action.runId };

    case "FILE_SELECTED":
      // Reset file slot fully so re-uploads start fresh
      return updateFile(state, action.role, {
        ...defaultFileState,
        file: action.file,
      });

    case "FILE_UPLOADING":
      return updateFile(state, action.role, {
        uploadStatus: "uploading",
        uploadError: null,
      });

    case "FILE_UPLOADED":
      return updateFile(state, action.role, {
        uploadStatus: "uploaded",
        sourceFileId: action.sourceFile.id,
        uploadError: null,
      });

    case "FILE_UPLOAD_ERROR":
      return updateFile(state, action.role, {
        uploadStatus: "error",
        uploadError: action.error,
      });

    case "SHEET_SELECTED":
      return updateFile(state, action.role, {
        selectedSheet: action.sheet,
        // Reset preview + mapping when sheet changes
        preview: null,
        previewStatus: "idle",
        previewError: null,
        pendingMappings: {},
        mappingConfirmed: false,
        mappingWarnings: [],
      });

    case "PREVIEW_LOADING":
      return updateFile(state, action.role, {
        previewStatus: "loading",
        previewError: null,
      });

    case "PREVIEW_LOADED": {
      // Pre-fill pendingMappings from heuristic suggestions
      const suggestions = action.preview.suggestions;
      const preFilled = Object.fromEntries(
        Object.entries(suggestions).map(([field, s]) => [field, s.column_index])
      );
      return updateFile(state, action.role, {
        previewStatus: "loaded",
        preview: action.preview,
        selectedSheet: action.preview.sheet ?? state.files[action.role].selectedSheet,
        pendingMappings: preFilled,
        mappingConfirmed: false,
        mappingWarnings: [],
      });
    }

    case "PREVIEW_ERROR":
      return updateFile(state, action.role, {
        previewStatus: "error",
        previewError: action.error,
      });

    case "MAPPING_CHANGED":
      return updateFile(state, action.role, {
        pendingMappings: {
          ...state.files[action.role].pendingMappings,
          [action.logicalField]: action.columnIndex,
        },
        // Unconfirm when user changes a selection
        mappingConfirmed: false,
      });

    case "MAPPING_CONFIRMED":
      return updateFile(state, action.role, {
        mappingConfirmed: true,
        mappingWarnings: action.warnings,
      });

    case "RESET":
      return { ...initialState };

    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface UseWizardStateReturn {
  state: WizardState;
  dispatch: React.Dispatch<WizardAction>;
  /** True when all 3 files are uploaded (Step 1 → Step 2 gate) */
  allFilesUploaded: boolean;
  /** True when all 3 mandatory file mappings are confirmed (RNF-08) */
  allMappingsConfirmed: boolean;
  /** File roles whose uploaded file is an Excel type (need sheet selection) */
  excelRoles: FileRole[];
}

const ALL_ROLES: FileRole[] = ["occ_top", "wm_feed", "amazon_report"];
const EXCEL_EXTS = [".xlsx", ".xlsm", ".xltx", ".xltm"];

function isExcel(file: File | null): boolean {
  if (!file) return false;
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  return EXCEL_EXTS.includes(ext);
}

export function useWizardState(): UseWizardStateReturn {
  const [state, dispatch] = useReducer(reducer, initialState);

  const allFilesUploaded = ALL_ROLES.every(
    (r) => state.files[r].uploadStatus === "uploaded"
  );

  const allMappingsConfirmed = ALL_ROLES.every(
    (r) => state.files[r].mappingConfirmed
  );

  const excelRoles = ALL_ROLES.filter((r) => isExcel(state.files[r].file));

  return { state, dispatch, allFilesUploaded, allMappingsConfirmed, excelRoles };
}
