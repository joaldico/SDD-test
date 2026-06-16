/**
 * Step4Summary — integration tests for the RNF-08 gate (T-3.9).
 *
 * Key assertion: the "Procesar" button MUST be disabled until
 * ALL THREE mandatory file mappings are confirmed.
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { Step4Summary } from "../../components/wizard/steps/Step4Summary";
import type { FileWizardState } from "../../hooks/useWizardState";
import type { FileRole } from "../../types/ingestion";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function makeFileState(overrides: Partial<FileWizardState> = {}): FileWizardState {
  return {
    file: new File([""], "test.csv"),
    uploadStatus: "uploaded",
    sourceFileId: 1,
    uploadError: null,
    selectedSheet: null,
    preview: null,
    previewStatus: "idle",
    previewError: null,
    pendingMappings: { sku: 0, stock: 1 },
    mappingConfirmed: false,
    mappingWarnings: [],
    ...overrides,
  };
}

function makeFiles(
  allConfirmed: boolean,
  overrides: Partial<Record<FileRole, Partial<FileWizardState>>> = {}
): Record<FileRole, FileWizardState> {
  return {
    occ_top: makeFileState({
      mappingConfirmed: allConfirmed,
      file: new File([""], "libro1.xlsx"),
      ...overrides.occ_top,
    }),
    wm_feed: makeFileState({
      mappingConfirmed: allConfirmed,
      file: new File([""], "feed.csv"),
      ...overrides.wm_feed,
    }),
    amazon_report: makeFileState({
      mappingConfirmed: allConfirmed,
      file: new File([""], "report.xlsm"),
      ...overrides.amazon_report,
    }),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Step4Summary — RNF-08 gate", () => {
  const onProcess = vi.fn();
  const onBack = vi.fn();

  beforeEach(() => {
    onProcess.mockClear();
    onBack.mockClear();
  });

  it("disables Procesar button when NO mapping is confirmed", () => {
    render(
      <Step4Summary
        runId={1}
        files={makeFiles(false)}
        allConfirmed={false}
        onProcess={onProcess}
        onBack={onBack}
      />
    );

    const btn = screen.getByTestId("process-button");
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-disabled", "true");
  });

  it("shows the gate banner when mapping is incomplete", () => {
    render(
      <Step4Summary
        runId={1}
        files={makeFiles(false)}
        allConfirmed={false}
        onProcess={onProcess}
        onBack={onBack}
      />
    );
    expect(screen.getByTestId("gate-banner")).toBeInTheDocument();
  });

  it("disables Procesar button when only two of three files are confirmed", () => {
    const files = makeFiles(false, {
      occ_top: { mappingConfirmed: true },
      wm_feed: { mappingConfirmed: true },
      // amazon_report: false (default)
    });
    render(
      <Step4Summary
        runId={1}
        files={files}
        allConfirmed={false} // allMappingsConfirmed from the hook = false
        onProcess={onProcess}
        onBack={onBack}
      />
    );

    const btn = screen.getByTestId("process-button");
    expect(btn).toBeDisabled();
  });

  it("enables Procesar button when ALL three files are confirmed (RNF-08 satisfied)", () => {
    render(
      <Step4Summary
        runId={1}
        files={makeFiles(true)}
        allConfirmed={true}
        onProcess={onProcess}
        onBack={onBack}
      />
    );

    const btn = screen.getByTestId("process-button");
    expect(btn).not.toBeDisabled();
    expect(btn).toHaveAttribute("aria-disabled", "false");
  });

  it("hides gate banner when all confirmed", () => {
    render(
      <Step4Summary
        runId={1}
        files={makeFiles(true)}
        allConfirmed={true}
        onProcess={onProcess}
        onBack={onBack}
      />
    );
    expect(screen.queryByTestId("gate-banner")).not.toBeInTheDocument();
  });

  it("calls onProcess when Procesar is clicked and all are confirmed", () => {
    render(
      <Step4Summary
        runId={1}
        files={makeFiles(true)}
        allConfirmed={true}
        onProcess={onProcess}
        onBack={onBack}
      />
    );

    fireEvent.click(screen.getByTestId("process-button"));
    expect(onProcess).toHaveBeenCalledOnce();
  });

  it("does NOT call onProcess when button is disabled", () => {
    render(
      <Step4Summary
        runId={1}
        files={makeFiles(false)}
        allConfirmed={false}
        onProcess={onProcess}
        onBack={onBack}
      />
    );

    fireEvent.click(screen.getByTestId("process-button"));
    expect(onProcess).not.toHaveBeenCalled();
  });

  it("shows processing state when processing=true", () => {
    render(
      <Step4Summary
        runId={1}
        files={makeFiles(true)}
        allConfirmed={true}
        onProcess={onProcess}
        onBack={onBack}
        processing={true}
      />
    );

    expect(screen.getByTestId("process-button")).toBeDisabled();
    expect(screen.getByTestId("process-button")).toHaveTextContent("Procesando…");
  });

  it("renders summary cards for all three roles", () => {
    render(
      <Step4Summary
        runId={42}
        files={makeFiles(true)}
        allConfirmed={true}
        onProcess={onProcess}
        onBack={onBack}
      />
    );

    expect(screen.getByTestId("summary-card-occ_top")).toBeInTheDocument();
    expect(screen.getByTestId("summary-card-wm_feed")).toBeInTheDocument();
    expect(screen.getByTestId("summary-card-amazon_report")).toBeInTheDocument();
  });

  it("calls onBack when Atrás is clicked", () => {
    render(
      <Step4Summary
        runId={1}
        files={makeFiles(true)}
        allConfirmed={true}
        onProcess={onProcess}
        onBack={onBack}
      />
    );

    fireEvent.click(screen.getByText("← Atrás"));
    expect(onBack).toHaveBeenCalledOnce();
  });
});
