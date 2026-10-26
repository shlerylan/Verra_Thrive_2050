import { z } from "zod";

const workbook = z.object({
  id: z.string().uuid(),
  project_id: z.string().uuid(),
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
  id: z.string().uuid(),
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

async function request(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(`/api${path}`, {
    ...init,
    signal: AbortSignal.timeout(60000),
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
  downloadTemplate: async (projectId: string, module: ModuleDefinition) => {
    const response = await fetch(`/api/projects/${projectId}/modules/${encodeURIComponent(module.identifier)}/${encodeURIComponent(module.version)}/template`, {
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
