import { z } from "zod";

// Migration 0002 reserves this ID for preserved uploads. It is accepted by
// PostgreSQL/Pydantic but predates the UUID version/variant rules used by Zod.
const projectId = z.union([
  z.string().uuid(),
  z.literal("00000000-0000-0000-0000-000000000001"),
]);

const workbook = z.object({
  id: z.string().uuid(),
  project_id: projectId,
  module_id: z.string().nullable(),
  module_version: z.string().nullable(),
  file_role: z.string().nullable(),
  template_version: z.string().nullable(),
  template_validation: z.literal("passed").nullable(),
  original_filename: z.string(),
  byte_size: z.number().int().nonnegative(),
  sha256: z.string().regex(/^[a-f0-9]{64}$/),
  uploaded_at: z.string().datetime({ offset: true }),
  status: z.literal("stored"),
  package_validation: z.literal("basic_checks_passed"),
  domain_validation: z.literal("not_performed"),
});
export type Workbook = z.infer<typeof workbook>;

const project = z.object({
  id: projectId,
  name: z.string(),
  description: z.string(),
  methodology_id: z.string().nullable(),
  methodology_version: z.string().nullable(),
  created_at: z.string().datetime({ offset: true }),
});
const methodology = z.object({
  identifier: z.string(),
  version: z.string(),
  name: z.string(),
  review_status: z.enum(["reviewed", "unreviewed"]),
  note: z.string(),
});
const moduleDefinition = z.object({
  identifier: z.string(),
  version: z.string(),
  name: z.string(),
  description: z.string(),
  kind: z.enum(["utility", "calculation"]),
  availability: z.enum([
    "unavailable",
    "file_intake_only",
    "prototype_calculation",
    "calculation_ready",
  ]),
  availability_reason: z.string(),
  methodology_independent: z.boolean(),
  compatible_methodologies: z.array(
    z.object({ identifier: z.string(), version: z.string() }),
  ),
  file_roles: z.array(
    z.object({
      identifier: z.string(),
      name: z.string(),
      description: z.string(),
      required: z.boolean(),
      permitted_formats: z.array(z.literal(".xlsx")),
    }),
  ),
  adapter_id: z.string().nullable(),
  input_contract_version: z.string().nullable(),
  expected_output_description: z.string().nullable(),
  template_version: z.string().nullable(),
});
const catalogue = z.object({
  methodologies: z.array(methodology),
  modules: z.array(moduleDefinition),
});
export type Project = z.infer<typeof project>;
export type ModuleDefinition = z.infer<typeof moduleDefinition>;
export type Catalogue = z.infer<typeof catalogue>;

const leakageYear = z.object({
  year: z.number().int(), t: z.number().int(),
  scenario_max_mitigation_production: z.number().finite().positive(),
  zero_leakage_mitigation_production: z.number().finite().nullable(),
  monitored_project_production: z.number(), monitored_mitigation_production: z.number(),
  new_land_per_production_unit: z.number(),
  project_shortfall: z.number(),
  baseline_project_density: z.number().nullable(), monitored_project_density: z.number().nullable(),
  baseline_mitigation_density: z.number().nullable(), monitored_mitigation_density: z.number().nullable(),
  baseline_project_production: z.number(), foregone_production: z.number(),
  baseline_mitigation_production: z.number(), leakage_mitigation: z.number(),
  production_subject_to_leakage: z.number(), new_land_area_ha: z.number(),
  carbon_stock_change_t_c_per_ha: z.number(), leakage_t_co2e: z.number(),
});
export type LeakageYear = z.infer<typeof leakageYear>;
const leakageScenario = z.object({
  result: leakageYear,
  source_workbook_id: z.string().uuid(),
  source_sha256: z.string().regex(/^[a-f0-9]{64}$/),
});
const leakagePreview = z.object({
  status: z.literal("preview"), methodology: z.string(), rule_module: z.string(),
  scope: z.string(), commodity: z.string(), production_unit: z.string(),
  historical_production: z.array(z.object({ year: z.number(), project: z.number(), mitigation: z.number() })),
  project_area_ha: z.number().nullable(), mitigation_area_ha: z.number().nullable(), reference_replay: z.boolean(),
  annual_results: z.array(leakageYear), total_leakage_t_co2e: z.number(),
  limitations: z.array(z.string()), source_workbook_id: z.string().uuid(),
  source_sha256: z.string().regex(/^[a-f0-9]{64}$/),
});
export type LeakagePreview = z.infer<typeof leakagePreview>;

async function request(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(`/api${path}`, {
    ...init,
    signal: init?.signal
      ? AbortSignal.any([init.signal, AbortSignal.timeout(60000)])
      : AbortSignal.timeout(60000),
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = z
      .object({ error: z.object({ message: z.string(), details: z.array(z.object({ cell: z.string(), message: z.string() })).optional() }) })
      .safeParse(payload);
    throw new Error(
      error.success
        ? [error.data.error.message, ...(error.data.error.details ?? []).map((item) => `${item.cell}: ${item.message}`)].join(" ")
        : "The API request failed. Please try again.",
    );
  }
  return payload;
}

export const api = {
  health: async () =>
    z.object({ status: z.literal("ok") }).parse(await request("/health")),
  catalogue: async () => catalogue.parse(await request("/catalogue")),
  projects: async (offset: number) =>
    z
      .array(project)
      .parse(await request(`/projects?offset=${offset}&limit=50`)),
  project: async (id: string) =>
    project.parse(await request(`/projects/${id}`)),
  createProject: async (name: string, description: string) =>
    project.parse(
      await request("/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description }),
      }),
    ),
  assignMethodology: async (
    id: string,
    methodology_id: string | null,
    methodology_version: string | null,
  ) =>
    project.parse(
      await request(`/projects/${id}/methodology`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ methodology_id, methodology_version }),
      }),
    ),
  modules: async (id: string) =>
    z.array(moduleDefinition).parse(await request(`/projects/${id}/modules`)),
  downloadTemplate: async (projectId: string, module: ModuleDefinition, example = false, blank = false) => {
    const response = await fetch(`/api/projects/${projectId}/modules/${encodeURIComponent(module.identifier)}/${encodeURIComponent(module.version)}/template${blank ? "?blank=true" : example ? "?example=true" : ""}`, {
      signal: AbortSignal.timeout(60000),
    });
    if (!response.ok) throw new Error("The template could not be downloaded. Please try again.");
    return response.blob();
  },
  list: async (projectId: string, offset: number) =>
    z
      .array(workbook)
      .parse(
        await request(
          `/projects/${projectId}/workbooks?offset=${offset}&limit=50`,
        ),
      ),
  metadata: async (projectId: string, id: string) =>
    workbook.parse(await request(`/projects/${projectId}/workbooks/${id}`)),
  previewLeakage: async (projectId: string, workbookId: string) =>
    leakagePreview.parse(await request(`/projects/${projectId}/leakage/preview`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workbook_id: workbookId }),
    })),
  scenarioLeakage: async (projectId: string, workbookId: string, year: number,
    mitigationProduction: number, signal?: AbortSignal) =>
    leakageScenario.parse(await request(`/projects/${projectId}/leakage/scenario`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workbook_id: workbookId, year, mitigation_production: mitigationProduction }),
      signal,
    })),
  upload: async (
    projectId: string,
    file: File,
    module: ModuleDefinition | undefined,
    role: string,
  ) => {
    const data = new FormData();
    data.append("file", file);
    if (module) {
      data.append("module_id", module.identifier);
      data.append("module_version", module.version);
      data.append("file_role", role);
    }
    return workbook.parse(
      await request(`/projects/${projectId}/workbooks`, {
        method: "POST",
        body: data,
      }),
    );
  },
};
