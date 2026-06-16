/** API client tests for taxonomy admin (T-5.6). */

import { afterEach, describe, expect, it, vi } from "vitest";
import { getErrorTaxonomy, patchErrorCodeFamily } from "../../api/taxonomy";

describe("taxonomy API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getErrorTaxonomy fetches the catalog endpoint", async () => {
    const mockJson = vi.fn().mockResolvedValue({
      families: [{ code: "GPSR", display_name: "GPSR", sort_order: 2 }],
      codes: [{ code: "8541", family_code: "SIN_CLASIFICAR", default_category: "ERROR", canonical_message: null }],
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: mockJson }),
    );

    const result = await getErrorTaxonomy();

    expect(fetch).toHaveBeenCalledWith("/api/v1/error-families");
    expect(result.codes[0].code).toBe("8541");
  });

  it("patchErrorCodeFamily sends PATCH with family_code", async () => {
    const mockJson = vi.fn().mockResolvedValue({
      code: "8541",
      family_code: "GPSR",
      default_category: "ERROR",
      canonical_message: null,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: mockJson }),
    );

    const result = await patchErrorCodeFamily("8541", { family_code: "GPSR" });

    expect(fetch).toHaveBeenCalledWith("/api/v1/error-codes/8541", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ family_code: "GPSR" }),
    });
    expect(result.family_code).toBe("GPSR");
  });

  it("patchErrorCodeFamily throws on 403", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: vi.fn().mockResolvedValue({ detail: "Insufficient permissions" }),
      }),
    );

    await expect(
      patchErrorCodeFamily("8541", { family_code: "GPSR" }),
    ).rejects.toThrow(/Insufficient permissions/i);
  });
});
