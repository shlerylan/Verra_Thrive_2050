import React from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
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
  file_roles: [
    {
      identifier: "original-workbook",
      name: "Original workbook",
      description: "Optional original.",
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
  vi.mocked(api.modules).mockResolvedValue([utility]);
  vi.mocked(api.list).mockImplementation(async (id) =>
    id === a.id ? [workbook] : [],
  );
});
afterEach(cleanup);

test("a failed library load shows a retryable error without claiming an empty library", async () => {
  const user = userEvent.setup();
  vi.mocked(api.list).mockRejectedValueOnce(
    new Error("Database unavailable. Please retry."),
  );
  render(<App />);
  await screen.findByRole("option", { name: a.name });
  await user.selectOptions(screen.getByLabelText("Project collection"), a.id);
  await screen.findByText("Database unavailable. Please retry.");
  expect(
    screen.queryByText(
      "No workbooks on this page. Upload to this project to begin.",
    ),
  ).toBeNull();
  await user.click(screen.getByRole("button", { name: "Refresh files" }));
  await screen.findByText("alpha.xlsx");
  expect(screen.queryByText("Database unavailable. Please retry.")).toBeNull();
});

test("a delayed assignment response cannot replace a newly selected project", async () => {
  const user = userEvent.setup();
  let resolveAssignment!: (project: Project) => void;
  vi.mocked(api.assignMethodology).mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveAssignment = resolve;
      }),
  );
  render(<App />);
  await screen.findByRole("option", { name: a.name });
  await user.selectOptions(screen.getByLabelText("Project collection"), a.id);
  await screen.findByRole("heading", { name: a.name });
  await user.click(screen.getByRole("button", { name: "Save assignment" }));
  await user.selectOptions(screen.getByLabelText("Project collection"), b.id);
  await screen.findByRole("heading", { name: b.name });
  await act(async () => {
    resolveAssignment(a);
  });
  expect(screen.getByRole("heading", { name: b.name })).toBeTruthy();
  expect(screen.queryByRole("heading", { name: a.name })).toBeNull();
});

test("switching projects clears files and metadata from the previous project", async () => {
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole("option", { name: a.name });
  await user.selectOptions(screen.getByLabelText("Project collection"), a.id);
  await screen.findByText("alpha.xlsx");
  vi.mocked(api.metadata).mockResolvedValue(workbook);
  await user.click(
    screen.getByRole("button", { name: "View metadata for alpha.xlsx" }),
  );
  await screen.findByRole("heading", { name: "File metadata" });
  expect(api.metadata).toHaveBeenCalledWith(a.id, workbook.id);
  await user.selectOptions(screen.getByLabelText("Project collection"), b.id);
  await screen.findByRole("heading", { name: b.name });
  await waitFor(() => expect(api.list).toHaveBeenLastCalledWith(b.id, 0));
  expect(screen.queryByText("alpha.xlsx")).toBeNull();
  expect(screen.queryByRole("heading", { name: "File metadata" })).toBeNull();
});

test("creates a project, saves unassigned methodology, and uploads with an explicit utility role", async () => {
  const user = userEvent.setup();
  vi.mocked(api.createProject).mockResolvedValue(b);
  vi.mocked(api.assignMethodology).mockResolvedValue(b);
  vi.mocked(api.upload).mockResolvedValue({
    ...workbook,
    project_id: b.id,
    original_filename: "source.xlsx",
  });
  render(<App />);
  await user.type(screen.getByLabelText("Project name"), b.name);
  await user.type(
    screen.getByLabelText("Description (optional)"),
    "Local review",
  );
  await user.click(screen.getByRole("button", { name: "Create project" }));
  await screen.findByRole("heading", { name: b.name });
  expect(api.createProject).toHaveBeenCalledWith(b.name, "Local review");
  await user.click(screen.getByRole("button", { name: "Save assignment" }));
  await waitFor(() =>
    expect(api.assignMethodology).toHaveBeenCalledWith(b.id, null, null),
  );
  await screen.findByText(/Methodology assignment saved/);
  await user.selectOptions(
    screen.getByLabelText("Module version or generic project intake"),
    JSON.stringify([utility.identifier, utility.version]),
  );
  await user.selectOptions(
    screen.getByLabelText("File role"),
    "original-workbook",
  );
  const file = new File(["UI fixture only"], "source.xlsx");
  await user.upload(screen.getByLabelText("Excel workbook"), file);
  await user.click(
    screen.getByRole("button", { name: "Upload to selected project" }),
  );
  await waitFor(() =>
    expect(api.upload).toHaveBeenCalledWith(
      b.id,
      file,
      utility,
      "original-workbook",
    ),
  );
  await screen.findByText(
    /source.xlsx: stored and basic XLSX checks completed/,
  );
  for (const name of [
    "Review extracted inputs - unavailable",
    "Run calculation - unavailable",
    "View / download results - unavailable",
  ]) {
    expect(
      (screen.getByRole("button", { name }) as HTMLButtonElement).disabled,
    ).toBe(true);
  }
  expect(
    screen.getByText(/No methodology versions are configured yet/),
  ).toBeTruthy();
});

test("unavailable module explains its status and blocks file intake", async () => {
  const user = userEvent.setup();
  const unavailable: ModuleDefinition = {
    ...utility,
    identifier: "test-only",
    kind: "calculation",
    availability: "unavailable",
    availability_reason: "Synthetic fixture: no implementation exists.",
  };
  vi.mocked(api.modules).mockResolvedValue([unavailable]);
  render(<App />);
  await screen.findByRole("option", { name: a.name });
  await user.selectOptions(screen.getByLabelText("Project collection"), a.id);
  await screen.findByLabelText("Module version or generic project intake");
  await user.selectOptions(
    screen.getByLabelText("Module version or generic project intake"),
    JSON.stringify([unavailable.identifier, unavailable.version]),
  );
  expect(screen.getByText(unavailable.availability_reason)).toBeTruthy();
  expect(
    (screen.getByLabelText("Excel workbook") as HTMLInputElement).disabled,
  ).toBe(true);
  expect(
    (
      screen.getByRole("button", {
        name: "Upload to selected project",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
});
