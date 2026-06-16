/**
 * TaxonomiaPage tests — T-5.6 taxonomy admin UI.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { TaxonomiaPage } from "../../pages/TaxonomiaPage";
import * as taxonomyApi from "../../api/taxonomy";

vi.mock("../../api/taxonomy", async (importOriginal) => {
  const actual = await importOriginal<typeof taxonomyApi>();
  return {
    ...actual,
    getErrorTaxonomy: vi.fn(),
    patchErrorCodeFamily: vi.fn(),
  };
});

const mockCatalog = {
  families: [
    { code: "AUTORIZACION_MARCA", display_name: "Autorización de marca", sort_order: 1 },
    { code: "GPSR", display_name: "GPSR / seguridad", sort_order: 2 },
    { code: "SIN_CLASIFICAR", display_name: "Sin clasificar", sort_order: 99 },
  ],
  codes: [
    {
      code: "8541",
      family_code: "SIN_CLASIFICAR",
      default_category: "ERROR",
      canonical_message: "Unknown listing error",
    },
    {
      code: "90220",
      family_code: "AUTORIZACION_MARCA",
      default_category: "ERROR",
      canonical_message: "Brand approval required",
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter>
      <TaxonomiaPage />
    </MemoryRouter>,
  );
}

describe("TaxonomiaPage", () => {
  it("loads and displays error codes with their families", async () => {
    vi.mocked(taxonomyApi.getErrorTaxonomy).mockResolvedValue(mockCatalog);

    renderPage();

    expect(await screen.findByText("8541")).toBeInTheDocument();
    expect(screen.getByText("90220")).toBeInTheDocument();
    expect(screen.getByLabelText(/familia del código 8541/i)).toHaveValue("SIN_CLASIFICAR");
    expect(screen.getByLabelText(/familia del código 90220/i)).toHaveValue("AUTORIZACION_MARCA");
  });

  it("updates family assignment when admin changes the select", async () => {
    vi.mocked(taxonomyApi.getErrorTaxonomy).mockResolvedValue(mockCatalog);
    vi.mocked(taxonomyApi.patchErrorCodeFamily).mockResolvedValue({
      code: "8541",
      family_code: "GPSR",
      default_category: "ERROR",
      canonical_message: "Unknown listing error",
    });

    renderPage();
    const user = userEvent.setup();

    const select = await screen.findByLabelText(/familia del código 8541/i);
    await user.selectOptions(select, "GPSR");

    await waitFor(() => {
      expect(taxonomyApi.patchErrorCodeFamily).toHaveBeenCalledWith("8541", {
        family_code: "GPSR",
      });
    });

    expect(await screen.findByRole("status")).toHaveTextContent(/8541.*GPSR/i);
    expect(select).toHaveValue("GPSR");
  });
});
