/**
 * Step5Progress — integration tests (T-4.6).
 *
 * Uses real timers with pollIntervalMs={10} so tests run fast without
 * fighting vi.useFakeTimers() vs waitFor.
 *
 * Covers:
 *   - Submitting state while onProcess is in-flight
 *   - Failed state when onProcess rejects
 *   - Polling state after 202 response
 *   - Completed state with metrics when status reaches "completed"
 *   - Failed state when polling sees status "failed"
 *   - onProcess called exactly once on re-renders
 */

import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Step5Progress } from "../../components/wizard/steps/Step5Progress";
import type { RunStatusResponse } from "../../types/ingestion";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const FAST_POLL = 10; // ms — overrides 2 s default so tests complete quickly

const makeStatus = (
  overrides: Partial<RunStatusResponse> = {}
): RunStatusResponse => ({
  status: "processing",
  phase: null,
  failure_reason: null,
  summary_metrics: null,
  ...overrides,
});

const completedStatus: RunStatusResponse = {
  status: "completed",
  phase: null,
  failure_reason: null,
  summary_metrics: {
    total_skus: 120,
    sent_with_error: 3,
    sent_ok: 100,
    not_sent: 17,
    desync_feed_only: 5,
    desync_amazon_only: 2,
    total_errors: 3,
  },
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Step5Progress", () => {
  it("shows submitting spinner while onProcess is pending", async () => {
    let resolveProcess!: (url: string) => void;
    const onProcess = vi.fn(
      () => new Promise<string>((res) => { resolveProcess = res; })
    );
    const onPollStatus = vi.fn().mockResolvedValue(makeStatus());

    render(
      <Step5Progress
        runId={1}
        onProcess={onProcess}
        onPollStatus={onPollStatus}
        pollIntervalMs={FAST_POLL}
      />
    );

    expect(screen.getByTestId("progress-submitting")).toBeInTheDocument();
    expect(screen.getByTestId("spinner")).toBeInTheDocument();

    resolveProcess("/api/v1/runs/1/status");
  });

  it("shows failed state when onProcess rejects", async () => {
    const onProcess = vi.fn().mockRejectedValue(new Error("Mapping incompleto"));
    const onPollStatus = vi.fn();

    render(
      <Step5Progress
        runId={2}
        onProcess={onProcess}
        onPollStatus={onPollStatus}
        pollIntervalMs={FAST_POLL}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("progress-failed")).toBeInTheDocument();
    });

    expect(screen.getByText("Mapping incompleto")).toBeInTheDocument();
  });

  it("enters polling state after successful onProcess", async () => {
    const onProcess = vi.fn().mockResolvedValue("/api/v1/runs/3/status");
    const onPollStatus = vi
      .fn()
      .mockResolvedValue(makeStatus({ phase: "Validando" }));

    render(
      <Step5Progress
        runId={3}
        onProcess={onProcess}
        onPollStatus={onPollStatus}
        pollIntervalMs={FAST_POLL}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("progress-polling")).toBeInTheDocument();
    });

    expect(screen.getByTestId("phase-stepper")).toBeInTheDocument();
  });

  it("updates active phase in stepper during polling", async () => {
    const onProcess = vi.fn().mockResolvedValue("/api/v1/runs/4/status");
    const onPollStatus = vi
      .fn()
      .mockResolvedValue(makeStatus({ phase: "Cruzando" }));

    render(
      <Step5Progress
        runId={4}
        onProcess={onProcess}
        onPollStatus={onPollStatus}
        pollIntervalMs={FAST_POLL}
      />
    );

    await waitFor(() => {
      const cruzandoStep = screen.queryByTestId("phase-cruzando");
      expect(cruzandoStep).toHaveAttribute("aria-current", "step");
    });
  });

  it("shows completed view with metrics when status becomes completed", async () => {
    const onProcess = vi.fn().mockResolvedValue("/api/v1/runs/5/status");
    const onPollStatus = vi.fn().mockResolvedValue(completedStatus);

    render(
      <Step5Progress
        runId={5}
        onProcess={onProcess}
        onPollStatus={onPollStatus}
        pollIntervalMs={FAST_POLL}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("progress-completed")).toBeInTheDocument();
    });

    expect(screen.getByTestId("metric-total-skus")).toHaveTextContent("120");
    expect(screen.getByTestId("metric-sent-ok")).toHaveTextContent("100");
    expect(screen.getByTestId("metric-sent-with-error")).toHaveTextContent("3");
    expect(screen.getByText("¡Conciliación completada!")).toBeInTheDocument();
  });

  it("shows failed state when polling returns status 'failed'", async () => {
    const onProcess = vi.fn().mockResolvedValue("/api/v1/runs/6/status");
    const onPollStatus = vi.fn().mockResolvedValue(
      makeStatus({ status: "failed", failure_reason: "SKU no encontrado" })
    );

    render(
      <Step5Progress
        runId={6}
        onProcess={onProcess}
        onPollStatus={onPollStatus}
        pollIntervalMs={FAST_POLL}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("progress-failed")).toBeInTheDocument();
    });

    expect(screen.getByText("SKU no encontrado")).toBeInTheDocument();
  });

  it("calls onProcess exactly once even on re-renders", async () => {
    const onProcess = vi.fn().mockResolvedValue("/api/v1/runs/7/status");
    const onPollStatus = vi.fn().mockResolvedValue(makeStatus());

    const { rerender } = render(
      <Step5Progress
        runId={7}
        onProcess={onProcess}
        onPollStatus={onPollStatus}
        pollIntervalMs={FAST_POLL}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("progress-polling")).toBeInTheDocument();
    });

    rerender(
      <Step5Progress
        runId={7}
        onProcess={onProcess}
        onPollStatus={onPollStatus}
        pollIntervalMs={FAST_POLL}
      />
    );

    expect(onProcess).toHaveBeenCalledTimes(1);
  });
});
