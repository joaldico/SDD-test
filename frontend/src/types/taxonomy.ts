/** Taxonomy admin types (T-5.6, RF-14). */

export interface ErrorFamilyItem {
  code: string;
  display_name: string;
  sort_order: number;
}

export interface ErrorCodeCatalogItem {
  code: string;
  family_code: string;
  default_category: string | null;
  canonical_message: string | null;
}

export interface ErrorTaxonomyResponse {
  families: ErrorFamilyItem[];
  codes: ErrorCodeCatalogItem[];
}

export interface ErrorCodeResponse {
  code: string;
  family_code: string;
  default_category: string | null;
  canonical_message: string | null;
}

export interface PatchErrorCodeRequest {
  family_code: string;
}
