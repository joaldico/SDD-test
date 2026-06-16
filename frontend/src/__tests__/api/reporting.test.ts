/** API client tests for reporting export and sku-detail (T-5.4). */

import { afterEach, describe, expect, it, vi } from "vitest";
import { exportRunReport, getSkuDetail } from "../../api/reporting";

describe("reporting API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getSkuDetail requests family and code filters", async () => {
    const mockJson = vi.fn().mockResolvedValue({
      run_id: 9,
      family_code: "AUTORIZACION_MARCA",
      error_code: "18299",
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: mockJson,
      }),
    );

    await getSkuDetail(9, {
      family: "AUTORIZACION_MARCA",
      code: "18299",
      page: 1,
      page_size: 50,
    });

    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/runs/9/report/sku-detail?family=AUTORIZACION_MARCA&code=18299&page=1&page_size=50",
    );
  });

  it("exportRunReport downloads the returned blob", async () => {
    const click = vi.fn();
    const remove = vi.fn();
    const appendChild = vi.fn();
    const createObjectURL = vi.fn().mockReturnValue("blob:mock");
    const revokeObjectURL = vi.fn();

    vi.stubGlobal("URL", {
      createObjectURL,
      revokeObjectURL,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        headers: {
          get: () => 'attachment; filename="informe_run_3.xlsx"',
        },
        blob: vi.fn().mockResolvedValue(new Blob(["xlsx"])),
      }),
    );

    const anchor = {
      href: "",
      download: "",
      style: { display: "" },
      click,
      remove,
    } as unknown as HTMLAnchorElement;

    vi.spyOn(document, "createElement").mockReturnValue(anchor);
    vi.spyOn(document.body, "appendChild").mockImplementation(appendChild);

    await exportRunReport(3, "xlsx");

    expect(fetch).toHaveBeenCalledWith("/api/v1/runs/3/export?format=xlsx");
    expect(anchor.download).toBe("informe_run_3.xlsx");
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock");
  });
});
