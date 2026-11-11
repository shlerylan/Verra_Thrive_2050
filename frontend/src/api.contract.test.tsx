import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api } from "./api";
import { App } from "./App";

// Use the actual client parsers: UI-only API mocks cannot catch wire-format bugs.
const legacy = {
  id: "00000000-0000-0000-0000-000000000001",
  name: "Legacy workbook collection",
  description: "Preserved uploads",
  methodology_id: null,
  methodology_version: null,
  created_at: "2026-10-24T10:00:00+00:00",
};
const stored = {
  id: "11111111-1111-4111-8111-111111111111",
  project_id: legacy.id,
  module_id: null, module_version: null, file_role: null,
  template_version: null, template_validation: null,
  original_filename: "preserved.xlsx", byte_size: 123,
  sha256: "a".repeat(64), uploaded_at: "2026-10-24T10:00:00Z",
  status: "stored", package_validation: "basic_checks_passed",
  domain_validation: "not_performed",
};

function serve(payload: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("the real client loads and selects the built-in legacy project", async () => {
  vi.stubGlobal("fetch", vi.fn(async (path: string) => {
    const payload = path === "/api/health" ? { status: "ok" }
      : path === "/api/catalogue" ? { methodologies: [], modules: [] }
      : path.startsWith("/api/projects?") ? [legacy]
      : path === `/api/projects/${legacy.id}` ? legacy : [];
    return { ok: true, json: async () => payload };
  }));
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole("option", { name: legacy.name });
  await user.selectOptions(screen.getByLabelText("Project collection"), legacy.id);
  await screen.findByRole("heading", { name: legacy.name });
  expect(await screen.findByLabelText("Methodology and version")).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
});

test("legacy project ownership is accepted in workbook lists and metadata", async () => {
  serve([stored]);
  expect(await api.list(legacy.id, 0)).toEqual([stored]);
  serve(stored);
  expect(await api.metadata(legacy.id, stored.id)).toEqual(stored);
});

test("ordinary UUID projects remain valid", async () => {
  const normal = { ...legacy, id: stored.id };
  serve([normal]);
  expect(await api.projects(0)).toEqual([normal]);
});

test.each(["invalid", "00000000-0000-0000-0000-000000000002"])(
  "invalid and unreserved nonstandard project IDs are rejected: %s", async (id) => {
    serve([{ ...legacy, id }]);
    await expect(api.projects(0)).rejects.toThrow();
  },
);

test("the reserved project ID is not accepted as a workbook ID", async () => {
  serve({ ...stored, id: legacy.id });
  await expect(api.metadata(legacy.id, legacy.id)).rejects.toThrow();
});

test("scenario requests send only stored source and changed inputs, and propagate cancellation", async () => {
  const controller = new AbortController();
  const fetchMock = vi.fn((_path: string, init: RequestInit) => new Promise((_resolve, reject) => {
    init.signal!.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
  }));
  vi.stubGlobal("fetch", fetchMock);
  const pending = api.scenarioLeakage(legacy.id, stored.id, 2023, 250.123, controller.signal);
  const rejected = expect(pending).rejects.toThrow("Aborted");
  const [path, init] = fetchMock.mock.calls[0];
  expect(path).toBe(`/api/projects/${legacy.id}/leakage/scenario`);
  expect(init.method).toBe("POST");
  expect(init.headers).toEqual({ "Content-Type": "application/json" });
  expect(JSON.parse(init.body as string)).toEqual({
    workbook_id: stored.id, year: 2023, mitigation_production: 250.123,
  });
  expect(init.signal!.aborted).toBe(false);
  controller.abort();
  expect(init.signal!.aborted).toBe(true);
  await rejected;
});
