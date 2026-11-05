import React, { useEffect, useRef, useState } from "react";
import { api, Catalogue, LeakagePreview, ModuleDefinition, Project, Workbook } from "./api";
import { date, size, message, key, availability } from "./format";
import { LeakageGuide } from "./LeakageGuide";
import { LeakageCharts } from "./LeakageCharts";
export function Workspace({
  project,
  catalogue,
  onAssignment,
  onChangeProject,
}: {
  project: Project;
  catalogue: Catalogue | null;
  onAssignment: (project: Project) => void;
  onChangeProject: () => void;
}) {
  const [restoring, setRestoring] = useState(true);
  const [step, setStep] = useState<2 | 3 | 4 | 5>(2);
  const [uploaded, setUploaded] = useState<Workbook | null>(null);
  const flow = useRef<HTMLDivElement>(null);
  useEffect(() => { flow.current?.focus(); }, [step]);
  const [modules, setModules] = useState<ModuleDefinition[]>([]);
  const [moduleKey, setModuleKey] = useState("");
  const [role, setRole] = useState("");
  const [moduleLoading, setModuleLoading] = useState(true);
  const [moduleError, setModuleError] = useState("");
  const [files, setFiles] = useState<Workbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fileError, setFileError] = useState("");
  const [success, setSuccess] = useState("");
  const [methodology, setMethodology] = useState(
    project.methodology_id
      ? key(project.methodology_id, project.methodology_version!)
      : "",
  );
  const [file, setFile] = useState<File | null>(null);
  const [selected, setSelected] = useState<Workbook | null>(null);
  const [preview, setPreview] = useState<LeakagePreview | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const details = useRef<HTMLElement>(null);
  const moduleRequest = useRef(0);
  const module = modules.find(
    (item) => key(item.identifier, item.version) === moduleKey,
  );
  const method = catalogue?.methodologies.find(
    (item) =>
      item.identifier === project.methodology_id &&
      item.version === project.methodology_version,
  );

  async function loadModules() {
    const request = ++moduleRequest.current;
    setModuleLoading(true);
    setModuleError("");
    setModules([]);
    setModuleKey("");
    setRole("");
    setFile(null);
    if (input.current) input.current.value = "";
    try {
      const available = await api.modules(project.id);
      if (request === moduleRequest.current) setModules(available);
    } catch (e) {
      if (request === moduleRequest.current) setModuleError(message(e));
    } finally {
      if (request === moduleRequest.current) setModuleLoading(false);
    }
  }
  useEffect(() => {
    void loadModules();
  }, [project.methodology_id, project.methodology_version]);

  async function refresh(page = offset) {
    setLoading(true);
    setError("");
    setFileError("");
    setFiles([]);
    try {
      const pageFiles = await api.list(project.id, page);
      setFiles(pageFiles);
      setOffset(page);
      return pageFiles;
    } catch (e) {
      setFileError(message(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    let active = true;
    async function restore() {
      try {
        let page = 0;
        let pageFiles = await refresh(0);
        if (project.methodology_id !== "VM0047" || project.methodology_version !== "1.0") return;
        let lastError = "";
        while (active && pageFiles) {
          for (const item of pageFiles) {
            if (item.module_id !== "leakage-single-commodity" || item.module_version !== "0.1.0"
                || item.file_role !== "leakage-input-template" || item.template_validation !== "passed"
                || !["0.2.0", "0.3.0"].includes(item.template_version ?? "")) continue;
            try {
              const result = await api.previewLeakage(project.id, item.id);
              if (!active) return;
              showSavedPreview(item, result);
              return;
            } catch (e) {
              if (!active) return;
              lastError = message(e);
            }
          }
          if (pageFiles.length < 50) break;
          page += 50;
          pageFiles = await api.list(project.id, page);
        }
        if (active && lastError) setError(`Could not reopen a saved calculation: ${lastError}`);
      } catch (e) {
        if (active) setError(`Could not find a saved calculation: ${message(e)}`);
      } finally {
        if (active) setRestoring(false);
      }
    }
    void restore();
    return () => { active = false; };
  }, []);

  async function assign(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSuccess("");
    const choice = catalogue?.methodologies.find(
      (item) => key(item.identifier, item.version) === methodology,
    );
    if (methodology && !choice) {
      setError("This methodology version is no longer configured.");
      setBusy(false);
      return;
    }
    try {
      const updated = await api.assignMethodology(
        project.id,
        choice?.identifier ?? null,
        choice?.version ?? null,
      );
      onAssignment(updated);
      setSuccess(
        "Methodology assignment saved. Existing files have not received domain-input validation.",
      );
      setUploaded(null);
      setPreview(null);
      setStep(3);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (!file || (moduleKey && !module)) return;
    setBusy(true);
    setError("");
    setSuccess("");
    setPreview(null);
    try {
      const stored = await api.upload(project.id, file, module, role);
      setUploaded(stored);
      setFile(null);
      if (input.current) input.current.value = "";
      await refresh(0);
      setSuccess(
        stored.template_validation === "passed"
          ? `${stored.original_filename}: template ${stored.template_version} validated and stored.`
          : `${stored.original_filename}: stored and basic XLSX checks completed. Domain-input validation has not been performed.`,
      );
      if (stored.module_id === "leakage-single-commodity" && stored.template_validation === "passed") {
        try {
          setPreview(await api.previewLeakage(project.id, stored.id));
          setSuccess(`${stored.original_filename}: validated and calculation preview completed.`);
          setStep(5);
        } catch (e) {
          setError(`The workbook was stored, but the preview failed: ${message(e)}`);
        }
      }
      else setStep(5);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function view(id: string) {
    setBusy(true);
    setError("");
    try {
      setSelected(await api.metadata(project.id, id));
      requestAnimationFrame(() => details.current?.focus());
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  function showSavedPreview(item: Workbook, result: LeakagePreview) {
    setPreview(result);
    setModuleKey(key(item.module_id!, item.module_version!));
    setRole(item.file_role ?? "");
    setUploaded(item);
    setStep(5);
  }
  async function previewWorkbook(item: Workbook) {
    setBusy(true);
    setError("");
    setPreview(null);
    try {
      showSavedPreview(item, await api.previewLeakage(project.id, item.id));
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  function downloadPreview() {
    if (!preview) return;
    const lines = [
      "Thrive 2050 | Leakage calculation preview", preview.methodology, preview.rule_module,
      preview.scope, `Commodity: ${preview.commodity} (${preview.production_unit})`,
      `Source workbook ID: ${preview.source_workbook_id}`,
      `Source SHA-256: ${preview.source_sha256}`, "",
      ...preview.annual_results.map((row) =>
        `${row.year}: foregone ${row.foregone_production}; mitigation ${row.leakage_mitigation}; ` +
        `subject to leakage ${row.production_subject_to_leakage}; new land ${row.new_land_area_ha} ha; ` +
        `leakage ${row.leakage_t_co2e} t CO2e`),
      "", `Sum of annual preview values: ${preview.total_leakage_t_co2e} t CO2e`, "",
      "Limitations:", ...preview.limitations.map((item) => `- ${item}`),
    ];
    const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `leakage-preview-${preview.source_workbook_id}.txt`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }
  async function downloadTemplate(example = false, blank = false) {
    if (!module || !module.template_version) return;
    setBusy(true);
    setError("");
    try {
      const blob = await api.downloadTemplate(project.id, module, example, blank);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = blank ? "leakage-blank-template-v0.3.0.xlsx"
        : !example && module.identifier === "leakage-single-commodity" ? `VCS5511-reference-sample-v${module.template_version}.xlsx`
        : `${module.identifier}-${example ? "synthetic-test-example" : "template"}-v${module.template_version}.xlsx`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="project-context" aria-label="Selected project">
        <div><h2>{project.name}</h2>
        <small>{project.methodology_id ? `${project.methodology_id} / ${project.methodology_version}` : "Methodology not assigned"}</small></div>
        <button className="secondary" disabled={busy} onClick={onChangeProject}>Change project</button>
      </section>
      <ol className="steps" aria-label="Calculation progress">
        {["Project", "Methodology", "Calculation", "Excel inputs", "Results"].map((label, index) => (
          <li key={label} aria-current={step === index + 1 ? "step" : undefined}
            className={index + 1 < step ? "complete" : ""}>
            <span>{index + 1}</span>{label}
          </li>
        ))}
      </ol>
      <div ref={flow} tabIndex={-1} className="flow-panel" aria-label={`Step ${step}`}>
      {step > 2 && <button className="secondary back" disabled={busy}
        onClick={() => { setError(""); setSuccess(""); setSelected(null); setFile(null); setStep(step === 5 ? 4 : step === 4 ? 3 : 2); }}>
        Back to {step === 5 ? "Excel inputs" : step === 4 ? "calculation selection" : "methodology"}
      </button>}
      {error && (
        <p role="alert" className="notice error">
          {error}
        </p>
      )}
      {fileError && (
        <p role="alert" className="notice error">
          {fileError}
        </p>
      )}
      {success && (
        <p role="status" className="notice success">
          {success}
        </p>
      )}
      {restoring && <p role="status">Checking for saved results...</p>}
      {step === 2 && !restoring && <section className="card upload" aria-labelledby="method-title">
        <div>
          <p className="eyebrow">02 / METHODOLOGY VERSION</p>
          <h2 id="method-title">Which methodology does your project use?</h2>
          <p>
            Choose the rules and version that apply to your project. You can also continue without a methodology to store files only.
          </p>
          {catalogue && catalogue.methodologies.length === 0 && (
            <p>
              No methodology versions are configured yet. Verified identifiers
              and versions must be supplied for review.
            </p>
          )}
          {method && (
            <details><summary>Methodology review status</summary><p>
              {method.review_status === "reviewed"
                ? "Catalogue reviewed; calculation availability is separate."
                : "Methodology review is pending; available calculations are labelled as previews."}{" "}
              {method.note}
            </p></details>
          )}
        </div>
        <form onSubmit={assign}>
          <label htmlFor="methodology">Methodology and version</label>
          <select
            id="methodology"
            value={methodology}
            disabled={busy || !catalogue}
            onChange={(e) => setMethodology(e.target.value)}
          >
            <option value="">Unassigned / gather files</option>
            {project.methodology_id && !method && (
              <option
                value={key(
                  project.methodology_id,
                  project.methodology_version!,
                )}
                disabled
              >
                {project.methodology_id} / {project.methodology_version} (no
                longer configured)
              </option>
            )}
            {catalogue?.methodologies.map((item) => (
              <option
                key={key(item.identifier, item.version)}
                value={key(item.identifier, item.version)}
              >
                {item.name} / {item.version}
              </option>
            ))}
          </select>
          <button disabled={busy || !catalogue}>Save and continue</button>
          {!catalogue && (
            <small>
              The catalogue is unavailable. Refresh projects to retry.
            </small>
          )}
        </form>
      </section>}
      {step === 3 && <section className="card module-section" aria-labelledby="module-title">
        <p className="eyebrow">03 / CALCULATION</p>
        <h2 id="module-title">What would you like to calculate?</h2>
        <p>
          Choose a calculation compatible with your methodology, or choose file storage to keep Excel files without calculating a result.
        </p>
        {moduleError && (
          <p role="alert" className="notice error">
            {moduleError}{" "}
            <button className="secondary" onClick={() => void loadModules()}>
              Retry catalogue
            </button>
          </p>
        )}
        {moduleLoading ? (
          <p role="status">Loading available calculations...</p>
        ) : (
          <>
            <label htmlFor="module">
              Calculation or file storage
            </label>
            <select
              id="module"
              value={moduleKey}
              disabled={busy}
              onChange={(e) => {
                setModuleKey(e.target.value);
                setRole("");
                setPreview(null);
                setUploaded(null);
                setFile(null);
                setSelected(null);
              }}
            >
              <option value="">
                Store project files only
              </option>
              {modules.map((item) => (
                <option
                  key={key(item.identifier, item.version)}
                  value={key(item.identifier, item.version)}
                >
                  {item.identifier === "leakage-single-commodity" ? "Agricultural Leakage" : item.identifier === "workbook-intake" ? "Excel template check (no calculation)" : item.name} -{" "}
                  {availability[item.availability]}
                </option>
              ))}
            </select>
            {modules.length === 0 && !moduleError && (
              <p>
                No compatible calculations are configured. Project-level
                workbook storage remains available.
              </p>
            )}
            {!moduleError &&
              !modules.some((item) => item.kind === "calculation") && (
                <p>
                  No compatible calculations are configured for this
                  project.
                </p>
              )}
            {module && (
              <div className="module-summary">
                <span className="badge">
                  {module.kind === "utility" ? "File storage and checks" : "Calculation"}{" "}
                  / {availability[module.availability]}
                </span>
                <h3>
                  {module.identifier === "leakage-single-commodity" ? "Agricultural Leakage" : module.name}
                </h3>
                <p>{module.description}</p>
                {module.identifier === "leakage-single-commodity" && <p className="method-reference">
                  <a href="https://verra.org/wp-content/uploads/2023/09/VMD0054_ARR-Leakage-Module_v1.0.pdf" target="_blank" rel="noopener noreferrer">
                    VMD0054 v1.0 — official Verra document (opens in a new tab)
                  </a><small>Pilot software version {module.version}</small>
                </p>}
                <details><summary>Methodology and input requirements</summary>
                <p>{module.name} / version {module.version}</p>
                <p>{module.availability_reason}</p>
                {module.file_roles.length ? (
                  <ul>
                    {module.file_roles.map((item) => (
                      <li key={item.identifier}>
                        <strong>{item.name}</strong> -{" "}
                        {item.required ? "Required" : "Optional"};{" "}
                        {item.permitted_formats.join(", ")}. {item.description}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>No file requirements have been defined for this module.</p>
                )}
                </details>
              </div>
            )}
            <div className="step-actions"><button disabled={busy || Boolean(moduleKey && (!module || module.availability === "unavailable"))}
              onClick={() => { setError(""); setSuccess(""); setStep(4); }}>
              Continue to Excel inputs
            </button></div>
          </>
        )}
      </section>}
      {step === 4 && <div className={`inputs-layout ${module?.template_version ? "with-template" : ""}`}>
                {module?.template_version && (
                  <section className="card module-section download-panel">
                  <div className="template-action">
                    <h3>Download the Excel template</h3>
                    {module.identifier === "leakage-single-commodity" ? <>
                      <p>Upload the Brazil Cerrado 1 sample, a filled test example, or your own completed template.</p>
                      <button disabled={busy} onClick={() => void downloadTemplate(false, true)}>Download blank customer template</button>
                      <div className="step-actions">
                        <button className="secondary" disabled={busy} onClick={() => void downloadTemplate(true)}>Download upload-ready test example</button>
                      </div>
                      <div className="step-actions">
                        <button className="secondary" disabled={busy} onClick={() => void downloadTemplate()}>Download Brazil Cerrado 1 sample</button>
                      </div>
                    </> : <>
                      <p>Template v{module.template_version}. Complete the Inputs sheet, then upload your saved Excel file below.</p>
                      <button className="secondary" disabled={busy} onClick={() => void downloadTemplate()}>Download Excel template</button>
                    </>}
                    {module.identifier === "leakage-single-commodity" && <LeakageGuide />}
                  </div>
                  </section>
                )}
      <section className="card upload" aria-labelledby="upload-title">
        <div>
          <p className="eyebrow">04 / UPLOAD</p>
          <h2 id="upload-title">Upload your Excel file</h2>
          <p>
            Only .xlsx files. Completed templates receive input
            checks; original workbooks receive basic XLSX package checks.
          </p>
        </div>
        <form onSubmit={upload}>
          {module && (
            <>
              <label htmlFor="role">File role</label>
              <select
                id="role"
                required
                value={role}
                disabled={busy || module.availability === "unavailable"}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="">Choose a defined file role</option>
                {module.file_roles.map((item) => (
                  <option key={item.identifier} value={item.identifier}>
                    {item.name}
                  </option>
                ))}
              </select>
            </>
          )}
          <label htmlFor="workbook">Excel workbook</label>
          <input
            id="workbook"
            ref={input}
            type="file"
            accept=".xlsx"
            disabled={busy || module?.availability === "unavailable"}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <button
            disabled={
              !file ||
              busy ||
              Boolean(
                moduleKey &&
                  (!module || module.availability === "unavailable" || !role),
              )
            }
          >
            {busy ? "Please wait..." : module?.availability === "prototype_calculation" ? "Upload and calculate preview" : "Upload to selected project"}
          </button>
          <small>
            Duplicate uploads create separate records and original files.
          </small>
        </form>
      </section>
      </div>}
      {(step === 4 || step === 5) && <details className="file-library"><summary>Project files and previous uploads</summary>
      <section
        className="card library"
        aria-labelledby="files-title"
        aria-busy={loading}
      >
        <div className="section-head">
          <div>
            <p className="eyebrow">PROJECT FILES</p>
            <h2 id="files-title">Excel Workbooks</h2>
          </div>
          <button
            className="secondary"
            disabled={loading || busy}
            onClick={() => void refresh()}
          >
            Refresh files
          </button>
        </div>
        {loading ? (
          <p role="status" className="empty">
            Loading workbooks...
          </p>
        ) : files.length === 0 ? (
          <p className="empty">
            {fileError
              ? "Files could not be loaded. Refresh to retry."
              : "No workbooks on this page. Upload to this project to begin."}
          </p>
        ) : (
          <div className="table-scroll">
            <table>
              <caption className="sr-only">
                Workbooks owned by {project.name}
              </caption>
              <thead>
                <tr>
                  {[
                    "Filename",
                    "Uploaded",
                    "Size",
                    "SHA-256",
                    "Association",
                    "Validation state",
                    "Calculation",
                    "Details",
                  ].map((label) => (
                    <th scope="col" key={label}>
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {files.map((item) => (
                  <tr key={item.id}>
                    <th scope="row">{item.original_filename}</th>
                    <td>{date(item.uploaded_at)}</td>
                    <td>{size(item.byte_size)}</td>
                    <td>
                      <code className="checksum">{item.sha256}</code>
                    </td>
                    <td>
                      {item.module_id
                        ? `${item.module_id} / ${item.module_version} / ${item.file_role}`
                        : "Project files"}
                    </td>
                    <td>
                      <span className="badge">
                        {item.template_validation === "passed" ? "Template validated / stored" : "Stored / basic XLSX checks completed"}
                      </span>
                      <small className="validation-note">
                        {item.module_id === "leakage-single-commodity" && item.template_validation === "passed"
                          ? `Template ${item.template_version}; pilot inputs checked, evidence not reviewed`
                          : item.template_validation === "passed" ? `Template ${item.template_version}; carbon inputs not validated` : "Domain inputs: not validated"}
                      </small>
                    </td>
                    <td>
                      {item.module_id === "leakage-single-commodity" && item.template_validation === "passed" ? (
                        <button className="text-button" disabled={busy} onClick={() => void previewWorkbook(item)}>
                          Calculate preview
                        </button>
                      ) : "—"}
                    </td>
                    <td>
                      <button
                        className="text-button"
                        disabled={busy}
                        onClick={() => void view(item.id)}
                        aria-label={`View metadata for ${item.original_filename}`}
                      >
                        View metadata
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="pagination">
          <button
            className="secondary"
            disabled={!offset || loading || busy}
            onClick={() => void refresh(Math.max(0, offset - 50))}
          >
            Previous
          </button>
          <span>Page {offset / 50 + 1}</span>
          <button
            className="secondary"
            disabled={files.length < 50 || loading || busy}
            onClick={() => void refresh(offset + 50)}
          >
            Next
          </button>
        </div>
      </section>
      {selected && (
        <section
          className="card metadata"
          ref={details}
          tabIndex={-1}
          aria-labelledby="metadata-title"
        >
          <div className="section-head">
            <h2 id="metadata-title">File metadata</h2>
            <button className="secondary" onClick={() => setSelected(null)}>
              Close details
            </button>
          </div>
          <dl>
            {Object.entries({
              Filename: selected.original_filename,
              "Project ID": selected.project_id,
              "File ID": selected.id,
              Uploaded: date(selected.uploaded_at),
              Size: size(selected.byte_size),
              "SHA-256": selected.sha256,
              Calculation: selected.module_id
                ? `${selected.module_id} / ${selected.module_version}`
                : "None",
              Role: selected.file_role ?? "None",
              Storage: "Stored",
              "Package validation": "Basic XLSX checks completed",
              "Domain validation": selected.module_id === "leakage-single-commodity" && selected.template_validation === "passed"
                ? "Pilot input checks passed; evidence not reviewed" : "Not performed",
              "Template version": selected.template_version ?? "Not applicable",
              "Template validation": selected.template_validation ?? "Not performed",
            }).map(([label, value]) => (
              <React.Fragment key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </React.Fragment>
            ))}
          </dl>
        </section>
      )}
      </details>}
      {step === 5 && <section className="card future" aria-labelledby="future-title">
        <p className="eyebrow">05 / CALCULATION AND REPORT</p>
        <h2 id="future-title">{preview ? "Leakage calculation preview" : "File upload complete"}</h2>
        {!preview && <p>{uploaded?.original_filename} has been stored. {uploaded?.template_validation === "passed" ? "Template checks passed." : "Basic Excel file checks passed."} No calculation result was produced for this file.</p>}
        {preview && (
          <div className="preview-report">
            <LeakageCharts key={preview.source_workbook_id} preview={preview} />
            <p><strong>{preview.commodity}</strong> / {preview.methodology} / {preview.rule_module}</p>
            <p><strong>Sum of annual preview values: {preview.total_leakage_t_co2e.toLocaleString("en-GB", { maximumFractionDigits: 3 })} t CO2e</strong></p>
            <div className="table-scroll"><table>
              <thead><tr><th>Year</th><th>Foregone production</th><th>Leakage mitigation</th><th>Production subject to leakage</th><th>New land (ha)</th><th>Leakage (t CO2e)</th></tr></thead>
              <tbody>{preview.annual_results.map((row) => (
                <tr key={row.year}><td>{row.year}</td><td>{row.foregone_production.toFixed(2)}</td>
                  <td>{row.leakage_mitigation.toFixed(2)}</td><td>{row.production_subject_to_leakage.toFixed(2)}</td>
                  <td>{row.new_land_area_ha.toFixed(2)}</td><td>{row.leakage_t_co2e.toFixed(2)}</td></tr>
              ))}</tbody>
            </table></div>
            <button className="secondary" onClick={downloadPreview}>Download preview report</button>
            <details><summary>Source file and calculation limitations</summary>
              <p>Source SHA-256: <code>{preview.source_sha256}</code></p>
              <ul>{preview.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
            </details>
          </div>
        )}
        <p id="future-reason">
          {module?.availability === "prototype_calculation"
            ? "The Leakage pilot calculates an arithmetic preview from a validated template. A verified VCS calculation requires evidence and applicability review. Formal runs are not available."
            : "File storage keeps your workbook and its upload details for later review."}
        </p>
      </section>}
      </div>
    </>
  );
}
