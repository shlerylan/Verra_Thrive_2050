import React from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";
import { api, ModuleDefinition, Project, Workbook } from "./api";

// These are UI fixtures only; real persistence is exercised by PostgreSQL tests.
vi.mock("./api", () => ({
  api: {
    health: vi.fn(),
    catalogue: vi.fn(),
    projects: vi.fn(),
    project: vi.fn(),
    createProject: vi.fn(),
    assignMethodology: vi.fn(),
    modules: vi.fn(),
    list: vi.fn(),
    metadata: vi.fn(),
    upload: vi.fn(),
    downloadTemplate: vi.fn(),
    previewLeakage: vi.fn(),
    scenarioLeakage: vi.fn(),
  },
}));

const a: Project = {
  id: "00000000-0000-4000-8000-000000000001",
  name: "Project Alpha",
  description: "",
  methodology_id: null,
  methodology_version: null,
  created_at: "2026-10-24T10:00:00Z",
};
const b: Project = {
  ...a,
  id: "00000000-0000-4000-8000-000000000002",
  name: "Project Beta",
};
const utility: ModuleDefinition = {
  identifier: "workbook-intake",
  version: "1.0.0",
  name: "Workbook Intake",
  kind: "utility",
  description: "Generic intake, not a calculation.",
  availability: "file_intake_only",
  availability_reason: "No calculation implementation.",
  methodology_independent: true,
  compatible_methodologies: [],
  adapter_id: null,
  input_contract_version: null,
  expected_output_description: null,
  template_version: "1.0.0",
  file_roles: [
    {
      identifier: "original-workbook",
      name: "Original workbook",
      description: "Optional original.",
      required: false,
      permitted_formats: [".xlsx"],
    },
    {
      identifier: "input-template",
      name: "Completed intake template",
      description: "Versioned intake template.",
      required: false,
      permitted_formats: [".xlsx"],
    },
  ],
};
const workbook: Workbook = {
  id: "00000000-0000-4000-8000-000000000003",
  project_id: a.id,
  module_id: null,
  module_version: null,
  file_role: null,
  template_version: null,
  template_validation: null,
  original_filename: "alpha.xlsx",
  byte_size: 5,
  sha256: "a".repeat(64),
  uploaded_at: "2026-10-24T10:00:00Z",
  status: "stored",
  package_validation: "basic_checks_passed",
  domain_validation: "not_performed",
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.health).mockResolvedValue({ status: "ok" });
  vi.mocked(api.catalogue).mockResolvedValue({
    methodologies: [],
    modules: [utility],
  });
  vi.mocked(api.projects).mockResolvedValue([a, b]);
  vi.mocked(api.project).mockImplementation(async (id) =>
    id === a.id ? a : b,
  );
  vi.mocked(api.assignMethodology).mockResolvedValue(a);
  vi.mocked(api.modules).mockResolvedValue([utility]);
  vi.mocked(api.list).mockImplementation(async (id) =>
    id === a.id ? [workbook] : [],
  );
});
afterEach(cleanup);


async function chooseProject(user: ReturnType<typeof userEvent.setup>, project = a) {
  await screen.findByRole("option", { name: project.name });
  await user.selectOptions(screen.getByLabelText("Project collection"), project.id);
  await screen.findByRole("heading", { name: project.name });
}
async function chooseTask(user: ReturnType<typeof userEvent.setup>, task = utility) {
  await user.click(await screen.findByRole("button", { name: "Save and continue" }));
  await screen.findByLabelText("Calculation or file storage");
  await user.selectOptions(screen.getByLabelText("Calculation or file storage"), JSON.stringify([task.identifier, task.version]));
}
async function inputs(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Continue to Excel inputs" }));
  await screen.findByLabelText("Excel workbook");
}
const pilot: ModuleDefinition = {
  ...utility, identifier: "leakage-single-commodity", version: "0.1.0",
  name: "VMD0054 Agricultural Leakage Pilot", kind: "calculation",
  availability: "prototype_calculation", methodology_independent: false,
  compatible_methodologies: [{ identifier: "VM0047", version: "1.0" }],
  file_roles: [{ identifier: "leakage-input-template", name: "Completed Leakage template",
    description: "Pilot input", required: true, permitted_formats: [".xlsx"] }],
  template_version: "0.1.0",
};
const source: Workbook = { ...workbook, module_id: pilot.identifier, module_version: pilot.version,
  file_role: "leakage-input-template", template_version: "0.1.0", template_validation: "passed" };
function setupPilot() {
  const project = { ...a, methodology_id: "VM0047", methodology_version: "1.0" };
  vi.mocked(api.project).mockResolvedValue(project);
  vi.mocked(api.assignMethodology).mockResolvedValue(project);
  vi.mocked(api.catalogue).mockResolvedValue({ methodologies: [{ identifier: "VM0047", version: "1.0",
    name: "ARR", review_status: "unreviewed", note: "Pilot" }], modules: [utility, pilot] });
  vi.mocked(api.modules).mockResolvedValue([utility, pilot]);
  vi.mocked(api.upload).mockResolvedValue(source);
  vi.mocked(api.previewLeakage).mockResolvedValue({
    status: "preview", methodology: "VM0047 v1.0", rule_module: "VMD0054 v1.0",
    scope: "One commodity", commodity: "Cattle", production_unit: "head",
    historical_production: [], project_area_ha: 16940.6, mitigation_area_ha: 133089.46, reference_replay: false,
    annual_results: [{ year: 2023, t: 1, scenario_max_mitigation_production: 51003.75,
      zero_leakage_mitigation_production: 30336.24, monitored_project_production: 0,
      monitored_mitigation_production: 40803, new_land_per_production_unit: 0.856, baseline_project_production: 6086.45,
      foregone_production: 6086.45, project_shortfall: 6086.45,
      baseline_project_density: 0.36, monitored_project_density: 0,
      baseline_mitigation_density: 0.18, monitored_mitigation_density: 0.31, baseline_mitigation_production: 24249.79,
      leakage_mitigation: 16553.21, production_subject_to_leakage: 0,
      new_land_area_ha: 0, carbon_stock_change_t_c_per_ha: 39.2552, leakage_t_co2e: 0 }],
    total_leakage_t_co2e: 0, limitations: ["Evidence not verified."],
    source_workbook_id: source.id, source_sha256: source.sha256,
  });
}

test("shows one step at a time and lets the user go back with their task selection", async () => {
  const user = userEvent.setup();
  render(<App />);
  expect(screen.queryByLabelText("Methodology and version")).toBeNull();
  await chooseProject(user);
  expect(screen.queryByLabelText("Project collection")).toBeNull();
  expect(screen.queryByLabelText("Calculation or file storage")).toBeNull();
  expect(screen.queryByLabelText("Excel workbook")).toBeNull();
  await chooseTask(user);
  expect(screen.getByRole("heading", { name: "What would you like to calculate?" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Download Excel template" })).toBeNull();
  await inputs(user);
  expect(screen.queryByLabelText("Calculation or file storage")).toBeNull();
  expect(screen.getByRole("button", { name: "Download Excel template" })).toBeTruthy();
  expect(screen.queryByRole("heading", { name: "File upload complete" })).toBeNull();
  await user.click(screen.getByRole("button", { name: "Back to calculation selection" }));
  expect((screen.getByLabelText("Calculation or file storage") as HTMLSelectElement).value)
    .toBe(JSON.stringify([utility.identifier, utility.version]));
});

test("a failed methodology save blocks progression and supports retry", async () => {
  const user = userEvent.setup();
  vi.mocked(api.assignMethodology).mockRejectedValueOnce(new Error("Please retry assignment."));
  render(<App />);
  await chooseProject(user);
  await user.click(await screen.findByRole("button", { name: "Save and continue" }));
  await screen.findByRole("alert");
  expect(screen.queryByLabelText("Calculation or file storage")).toBeNull();
  await chooseTask(user);
  expect(api.assignMethodology).toHaveBeenLastCalledWith(a.id, null, null);
});

test("an unavailable calculation explains its status and cannot advance", async () => {
  const user = userEvent.setup();
  const unavailable = { ...utility, identifier: "unavailable", availability: "unavailable" as const,
    availability_reason: "No implementation exists." };
  vi.mocked(api.modules).mockResolvedValue([unavailable]);
  render(<App />);
  await chooseProject(user);
  await chooseTask(user, unavailable);
  expect(screen.getByText("No implementation exists.")).toBeTruthy();
  expect((screen.getByRole("button", { name: "Continue to Excel inputs" }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByLabelText("Excel workbook")).toBeNull();
});

test("invalid uploads remain on inputs; successful storage advances without claiming a calculation", async () => {
  const user = userEvent.setup();
  vi.mocked(api.upload).mockRejectedValueOnce(new Error("Inputs!B8: required."))
    .mockResolvedValue({ ...workbook, template_validation: "passed", template_version: "1.0.0" });
  render(<App />);
  await chooseProject(user);
  await chooseTask(user);
  await inputs(user);
  await user.selectOptions(screen.getByLabelText("File role"), "input-template");
  const file = new File(["fixture"], "input.xlsx");
  await user.upload(screen.getByLabelText("Excel workbook"), file);
  await user.click(screen.getByRole("button", { name: "Upload to selected project" }));
  await screen.findByText("Inputs!B8: required.");
  expect(screen.queryByRole("heading", { name: "File upload complete" })).toBeNull();
  await user.click(screen.getByRole("button", { name: "Upload to selected project" }));
  await screen.findByRole("heading", { name: "File upload complete" });
  expect(screen.getByText(/No calculation result was produced/)).toBeTruthy();
  expect(screen.queryByLabelText("Excel workbook")).toBeNull();
  expect(api.upload).toHaveBeenLastCalledWith(a.id, file, utility, "input-template");
});

test("Leakage progresses to preview and switching tasks hides the old result", async () => {
  const user = userEvent.setup();
  setupPilot();
  render(<App />);
  await chooseProject(user);
  await chooseTask(user, pilot);
  expect(screen.getByRole("option", { name: /Agricultural Leakage/ })).toBeTruthy();
  const reference = screen.getByRole("link", { name: /official Verra document/ });
  expect(reference.getAttribute("href")).toBe("https://verra.org/wp-content/uploads/2023/09/VMD0054_ARR-Leakage-Module_v1.0.pdf");
  expect(reference.getAttribute("target")).toBe("_blank");
  await inputs(user);
  await user.click(screen.getByText("How to fill the Leakage template"));
  expect(screen.getByText(/B8 is biomass carbon loss/)).toBeTruthy();
  expect(screen.getByText(/789.25 t CO2e/)).toBeTruthy();
  await user.selectOptions(screen.getByLabelText("File role"), "leakage-input-template");
  await user.upload(screen.getByLabelText("Excel workbook"), new File(["fixture"], "leakage.xlsx"));
  await user.click(screen.getByRole("button", { name: "Upload and calculate preview" }));
  await screen.findByRole("heading", { name: "Leakage calculation preview" });
  expect(api.previewLeakage).toHaveBeenCalledWith(a.id, source.id);
  expect(screen.getByRole("heading", { name: "Annual production (head)" })).toBeTruthy();
  expect(screen.getByText("16,940.6 ha")).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Reset to uploaded total" }));
  expect(screen.getByText("Evidence not verified.")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Download preview report" })).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Back to Excel inputs" }));
  await user.click(screen.getByRole("button", { name: "Back to calculation selection" }));
  await user.selectOptions(screen.getByLabelText("Calculation or file storage"), "");
  await inputs(user);
  expect(screen.queryByRole("heading", { name: "Leakage calculation preview" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Download preview report" })).toBeNull();
});

test("preview failure stays on inputs and stored workbook can be retried", async () => {
  const user = userEvent.setup();
  setupPilot();
  vi.mocked(api.previewLeakage).mockRejectedValueOnce(new Error("Preview unavailable."));
  vi.mocked(api.list).mockResolvedValueOnce([]).mockResolvedValue([source]);
  render(<App />);
  await chooseProject(user);
  await chooseTask(user, pilot);
  await inputs(user);
  await user.selectOptions(screen.getByLabelText("File role"), "leakage-input-template");
  await user.upload(screen.getByLabelText("Excel workbook"), new File(["fixture"], "leakage.xlsx"));
  await user.click(screen.getByRole("button", { name: "Upload and calculate preview" }));
  await screen.findByText(/workbook was stored, but the preview failed/);
  expect(screen.getByLabelText("Excel workbook")).toBeTruthy();
  await user.click(screen.getByText("Project files and previous uploads"));
  await user.click(screen.getByRole("button", { name: "Calculate preview" }));
  await screen.findByRole("heading", { name: "Leakage calculation preview" });
});

test("changing projects clears prior files and metadata", async () => {
  const user = userEvent.setup();
  render(<App />);
  await chooseProject(user);
  await chooseTask(user);
  await inputs(user);
  await user.click(screen.getByText("Project files and previous uploads"));
  vi.mocked(api.metadata).mockResolvedValue(workbook);
  await user.click(screen.getByRole("button", { name: "View metadata for alpha.xlsx" }));
  await screen.findByRole("heading", { name: "File metadata" });
  await user.click(screen.getByRole("button", { name: "Change project" }));
  await chooseProject(user, b);
  expect(screen.queryByText("alpha.xlsx")).toBeNull();
  expect(screen.queryByRole("heading", { name: "File metadata" })).toBeNull();
  expect(await screen.findByLabelText("Methodology and version")).toBeTruthy();
});

test("file library errors support retry", async () => {
  const user = userEvent.setup();
  vi.mocked(api.list).mockRejectedValueOnce(new Error("Database unavailable. Please retry."));
  render(<App />);
  await chooseProject(user);
  await chooseTask(user);
  await inputs(user);
  await screen.findByText("Database unavailable. Please retry.");
  await user.click(screen.getByText("Project files and previous uploads"));
  await user.click(screen.getByRole("button", { name: "Refresh files" }));
  await screen.findByText("alpha.xlsx");
  expect(screen.queryByText("Database unavailable. Please retry.")).toBeNull();
});


test("opening a project restores its stored leakage preview without another upload", async () => {
  const user = userEvent.setup();
  setupPilot();
  vi.mocked(api.list).mockResolvedValue([{ ...source, template_version: "0.3.0" }]);
  render(<App />);
  await chooseProject(user);
  await screen.findByRole("heading", { name: "Leakage calculation preview" });
  expect(api.previewLeakage).toHaveBeenCalledWith(a.id, source.id);
  expect(api.upload).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Back to Excel inputs" }));
  expect(await screen.findByLabelText("Excel workbook")).toBeTruthy();
});
