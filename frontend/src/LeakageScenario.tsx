import React, { useEffect, useRef, useState } from "react";
import { api, LeakageYear } from "./api";
import { message } from "./format";

export const SCENARIO_DEBOUNCE_MS = 300;
const format = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

export function LeakageScenario({ projectId, workbookId, sourceSha256, row, unit,
  debounceMs = SCENARIO_DEBOUNCE_MS }: {
  projectId: string; workbookId: string; sourceSha256: string;
  row: LeakageYear; unit: string; debounceMs?: number;
}) {
  const original = row.monitored_mitigation_production;
  const [selected, setSelected] = useState(original);
  const [result, setResult] = useState({ value: original, row });
  const lastSuccess = useRef(result);
  const [error, setError] = useState<{ value: number; message: string } | null>(null);
  const [retry, setRetry] = useState(0);
  const sequence = useRef(0);
  const displayed = selected === original ? { value: original, row } : result;
  const currentError = error?.value === selected ? error.message : "";
  const pending = displayed.value !== selected && !currentError;

  useEffect(() => {
    const requestId = ++sequence.current;
    setError(null);
    // The original result and last successful result already came from Python.
    if (selected === original || selected === lastSuccess.current.value) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      void api.scenarioLeakage(projectId, workbookId, row.year, selected, controller.signal)
        .then((response) => {
          if (controller.signal.aborted || sequence.current !== requestId) return;
          if (response.source_workbook_id !== workbookId || response.source_sha256 !== sourceSha256
              || response.result.year !== row.year
              || response.result.monitored_mitigation_production !== selected) {
            throw new Error("The scenario response did not match the selected inputs.");
          }
          const next = { value: selected, row: response.result };
          lastSuccess.current = next;
          setResult(next);
        })
        .catch((e: unknown) => {
          if (!controller.signal.aborted && sequence.current === requestId) {
            setError({ value: selected, message: message(e) });
          }
        });
    }, debounceMs);
    return () => {
      clearTimeout(timer);
      controller.abort();
      sequence.current++;
    };
  }, [projectId, workbookId, sourceSha256, row, original, selected, retry, debounceMs]);

  return (
    <>
      <h3>What if mitigation production changed?</h3>
      <label htmlFor="visual-mitigation">Mitigation total: {format.format(selected)} {unit}</label>
      <input id="visual-mitigation" type="range" min={0}
        max={row.scenario_max_mitigation_production} step="any" value={selected}
        onChange={(event) => setSelected(event.target.valueAsNumber)} />
      <div className="entry-options">
        <button type="button" className="secondary" onClick={() => setSelected(original)}>Reset to uploaded total</button>
      </div>
      {pending && <small role="status">Calculating scenario...</small>}
      {currentError && <p role="alert">
        The scenario could not be calculated. {currentError}{" "}
        <button type="button" className="secondary"
          onClick={() => { setError(null); setRetry((value) => value + 1); }}>Retry scenario</button>
      </p>}
      <div aria-busy={pending} aria-live="polite" data-testid="scenario-result">
        {displayed.value !== selected && <small>
          Last calculated for {format.format(displayed.value)} {unit}.
        </small>}
        <p><strong>{format.format(displayed.row.leakage_t_co2e)} t CO₂e</strong>
          {" "}· {format.format(displayed.row.new_land_area_ha)} ha of estimated new land.</p>
      </div>
      <p>{row.zero_leakage_mitigation_production !== null
        ? `Modelled leakage reaches zero at approximately ${format.format(row.zero_leakage_mitigation_production)} ${unit}.`
        : "Modelled leakage is zero throughout this scenario."}</p>
    </>
  );
}
