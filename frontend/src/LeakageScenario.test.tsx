import React from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { api, LeakageYear } from "./api";
import { LeakageScenario } from "./LeakageScenario";

vi.mock("./api", () => ({ api: { scenarioLeakage: vi.fn() } }));
const projectId = "00000000-0000-4000-8000-000000000001";
const workbookId = "00000000-0000-4000-8000-000000000002";
const sha = "a".repeat(64);
const row: LeakageYear = {
  year: 2023, t: 1, monitored_project_production: 0, monitored_mitigation_production: 205,
  scenario_max_mitigation_production: 384.375, zero_leakage_mitigation_production: 307.5,
  baseline_project_production: 102.5, baseline_mitigation_production: 205,
  foregone_production: 102.5, project_shortfall: 102.5,
  baseline_project_density: null, monitored_project_density: null,
  baseline_mitigation_density: null, monitored_mitigation_density: null,
  leakage_mitigation: 0, production_subject_to_leakage: 102.5,
  new_land_per_production_unit: 0.15, new_land_area_ha: 15.375,
  carbon_stock_change_t_c_per_ha: 14, leakage_t_co2e: 789.25,
};
function response(total: number, emissions = 123) {
  return { source_workbook_id: workbookId, source_sha256: sha,
    result: { ...row, monitored_mitigation_production: total, leakage_t_co2e: emissions, new_land_area_ha: 9.87 } };
}
type ScenarioResponse = ReturnType<typeof response>;
function deferred() {
  let resolve!: (value: ScenarioResponse) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<ScenarioResponse>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function mount(props: Partial<React.ComponentProps<typeof LeakageScenario>> = {}) {
  return render(<LeakageScenario projectId={projectId} workbookId={workbookId}
    sourceSha256={sha} row={row} unit="head" {...props} />);
}
function change(value: number) {
  fireEvent.change(screen.getByRole("slider"), { target: { value: String(value) } });
}
async function advance(ms: number) {
  await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
}
beforeEach(() => { vi.useFakeTimers(); vi.resetAllMocks(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

test("moves immediately, debounces a burst for 300ms, and renders only the backend numbers", async () => {
  vi.mocked(api.scenarioLeakage).mockResolvedValue(response(250, 12.34));
  mount();
  expect(screen.getByText("789.25 t CO₂e")).toBeTruthy();
  change(210);
  await advance(150);
  change(220);
  await advance(150);
  change(250);
  expect((screen.getByRole("slider") as HTMLInputElement).value).toBe("250");
  expect(screen.getByRole("status").textContent).toContain("Calculating");
  expect(screen.getByText("Last calculated for 205 head.")).toBeTruthy();
  await advance(299);
  expect(api.scenarioLeakage).not.toHaveBeenCalled();
  await advance(1);
  expect(api.scenarioLeakage).toHaveBeenCalledTimes(1);
  expect(api.scenarioLeakage).toHaveBeenCalledWith(projectId, workbookId, 2023, 250, expect.any(AbortSignal));
  expect(screen.getByText("12.34 t CO₂e")).toBeTruthy();
  expect(screen.getByTestId("scenario-result").textContent).toContain("9.87 ha");
  expect(screen.queryByRole("status")).toBeNull();
});

test("aborts old requests and ignores their responses even when cancellation is ignored", async () => {
  const first = deferred(), second = deferred();
  vi.mocked(api.scenarioLeakage).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  mount();
  change(220);
  await advance(300);
  const oldSignal = vi.mocked(api.scenarioLeakage).mock.calls[0][4]!;
  change(230);
  expect(oldSignal.aborted).toBe(true);
  await advance(300);
  await act(async () => { second.resolve(response(230, 22)); });
  expect(screen.getByText("22 t CO₂e")).toBeTruthy();
  await act(async () => { first.resolve(response(220, 999)); });
  expect(screen.getByText("22 t CO₂e")).toBeTruthy();
  expect(screen.queryByText("999 t CO₂e")).toBeNull();
});

test("preserves the last result on failure and supports retrying unchanged inputs", async () => {
  vi.mocked(api.scenarioLeakage).mockRejectedValueOnce(new Error("Offline"))
    .mockResolvedValueOnce(response(230, 44));
  mount();
  change(230);
  await advance(300);
  expect(screen.getByRole("alert").textContent).toContain("Offline");
  expect(screen.getByText("789.25 t CO₂e")).toBeTruthy();
  expect(screen.queryByRole("status")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Retry scenario" }));
  await advance(300);
  expect(screen.getByText("44 t CO₂e")).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
});

test("reuses original and last successful inputs without requests", async () => {
  vi.mocked(api.scenarioLeakage).mockResolvedValue(response(230, 44));
  mount();
  await advance(1000);
  expect(api.scenarioLeakage).not.toHaveBeenCalled();
  change(230);
  await advance(300);
  change(240);
  await advance(100);
  change(230);
  await advance(1000);
  expect(api.scenarioLeakage).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Reset to uploaded total" }));
  await advance(1000);
  expect(screen.getByText("789.25 t CO₂e")).toBeTruthy();
  expect(api.scenarioLeakage).toHaveBeenCalledTimes(1);
});

test("resetting or switching year/workbook cancels pending work and restores source results", async () => {
  const pending = deferred();
  vi.mocked(api.scenarioLeakage).mockReturnValue(pending.promise);
  const view = mount();
  change(230);
  await advance(300);
  const signal = vi.mocked(api.scenarioLeakage).mock.calls[0][4]!;
  fireEvent.click(screen.getByRole("button", { name: "Reset to uploaded total" }));
  expect(signal.aborted).toBe(true);
  await act(async () => { pending.resolve(response(230, 999)); });
  expect(screen.getByText("789.25 t CO₂e")).toBeTruthy();
  change(250);
  view.unmount();
  mount({ row: { ...row, year: 2024, leakage_t_co2e: 800 } });
  await advance(1000);
  expect(api.scenarioLeakage).toHaveBeenCalledTimes(1);
  expect(screen.getByText("800 t CO₂e")).toBeTruthy();
});

test("supports a configurable debounce and rejects mismatched source responses", async () => {
  vi.mocked(api.scenarioLeakage).mockResolvedValue({ ...response(230), source_sha256: "b".repeat(64) });
  mount({ debounceMs: 50 });
  change(230);
  await advance(49);
  expect(api.scenarioLeakage).not.toHaveBeenCalled();
  await advance(1);
  expect(screen.getByRole("alert").textContent).toContain("did not match");
  expect(screen.getByText("789.25 t CO₂e")).toBeTruthy();
});
