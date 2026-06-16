/** API client tests for run history (T-5.5). */

import { afterEach, describe, expect, it, vi } from "vitest";
import { listRuns } from "../../api/reporting";

describe("listRuns", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("requests paginated run history with page and size", async () => {
    const mockJson = vi.fn().mockResolvedValue({
      items: [],
      total: 0,
      page: 2,
      size: 10,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: mockJson,
      }),
    );

    await listRuns({ page: 2, size: 10, status: "completed" });

    expect(fetch).toHaveBeenCalledWith("/api/v1/runs?page=2&size=10&status=completed");
  });
});
