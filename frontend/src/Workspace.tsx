import React, { useEffect, useRef, useState } from "react";
import { api, Catalogue, ModuleDefinition, Project, Workbook } from "./api";
import { date, size, message, key, availability } from "./format";
export function Workspace({
  project,
  catalogue,
  onAssignment,
}: {
  project: Project;
  catalogue: Catalogue | null;
  onAssignment: (project: Project) => void;
}) {
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
      setFiles(await api.list(project.id, page));
      setOffset(page);
    } catch (e) {
      setFileError(message(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void refresh(0);
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
    try {
      const stored = await api.upload(project.id, file, module, role);
      setFile(null);
      if (input.current) input.current.value = "";
      await refresh(0);
      setSuccess(
        `${stored.original_filename}: stored and basic XLSX checks completed. Domain-input validation has not been performed.`,
      );
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

  return (
    <>
      <section className="project-context" aria-label="Selected project">
        <p className="eyebrow">SELECTED PROJECT</p>
        <h2>{project.name}</h2>
        {project.description && <p>{project.description}</p>}
        <small>Project ID: {project.id}</small>
        <p>
          Methodology:{" "}
          {project.methodology_id
            ? `${method?.name ?? project.methodology_id} / ${project.methodology_version}`
            : "Unassigned"}
        </p>
      </section>
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
      <section className="card upload" aria-labelledby="method-title">
        <div>
          <p className="eyebrow">02 / METHODOLOGY VERSION</p>
          <h2 id="method-title">Choose explicit rules when available</h2>
          <p>
            Unassigned projects can collect files. Assigning a catalogue entry
            does not establish implementation support or validate uploaded
            inputs.
          </p>
          {catalogue && catalogue.methodologies.length === 0 && (
            <p>
              No methodology versions are configured yet. Verified identifiers
              and versions must be supplied for review.
            </p>
          )}
          {method && (
            <p>
              {method.review_status === "reviewed"
                ? "Catalogue reviewed; calculation availability is separate."
                : "Unreviewed catalogue entry; not a supported calculation capability."}{" "}
              {method.note}
            </p>
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
                {item.name} / {item.version} ({item.review_status} catalogue
                entry)
              </option>
            ))}
          </select>
          <button disabled={busy || !catalogue}>Save assignment</button>
          {!catalogue && (
            <small>
              The catalogue is unavailable. Refresh projects to retry.
            </small>
          )}
        </form>
      </section>
      <section className="card module-section" aria-labelledby="module-title">
        <p className="eyebrow">03 / MODULE</p>
        <h2 id="module-title">Select a capability</h2>
        <p>
          Module versions are matched to the project's exact methodology
          version. Generic intake is a utility, not a methodology calculation.
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
          <p role="status">Loading compatible modules...</p>
        ) : (
          <>
            <label htmlFor="module">
              Module version or generic project intake
            </label>
            <select
              id="module"
              value={moduleKey}
              disabled={busy}
              onChange={(e) => {
                setModuleKey(e.target.value);
                setRole("");
              }}
            >
              <option value="">
                Generic project files / no module association
              </option>
              {modules.map((item) => (
                <option
                  key={key(item.identifier, item.version)}
                  value={key(item.identifier, item.version)}
                >
                  {item.name} / {item.version} -{" "}
                  {availability[item.availability]}
                </option>
              ))}
            </select>
            {modules.length === 0 && !moduleError && (
              <p>
                No compatible modules are configured. Generic project-level
                workbook storage remains available.
              </p>
            )}
            {!moduleError &&
              !modules.some((item) => item.kind === "calculation") && (
                <p>
                  No compatible calculation modules are configured for this
                  project.
                </p>
              )}
            {module && (
              <div className="module-summary">
                <span className="badge">
                  {module.kind === "utility" ? "Utility" : "Calculation module"}{" "}
                  / {availability[module.availability]}
                </span>
                <h3>
                  {module.name} / {module.version}
                </h3>
                <p>{module.description}</p>
                <p>{module.availability_reason}</p>
                <h3>Defined file roles</h3>
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
                <small>
                  Adapter: {module.adapter_id ?? "Not implemented"}. Input
                  contract: {module.input_contract_version ?? "Not implemented"}
                  . Expected outputs:{" "}
                  {module.expected_output_description ?? "Not defined"}.
                </small>
              </div>
            )}
          </>
        )}
      </section>
      <section className="card upload" aria-labelledby="upload-title">
        <div>
          <p className="eyebrow">04 / WORKBOOK INTAKE</p>
          <h2 id="upload-title">Preserve the original files</h2>
          <p>
            Only .xlsx files. Successful storage includes basic XLSX package
            checks, not domain-input validation or calculation readiness.
          </p>
          <p>
            Destination: <strong>{project.name}</strong>
            {module && ` / ${module.name} ${module.version}`}
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
            {busy ? "Please wait..." : "Upload to selected project"}
          </button>
          <small>
            Duplicate uploads create separate records and original files.
          </small>
        </form>
      </section>
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
                        : "Project files (no module)"}
                    </td>
                    <td>
                      <span className="badge">
                        Stored / basic XLSX checks completed
                      </span>
                      <small className="validation-note">
                        Domain inputs: not validated
                      </small>
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
              Module: selected.module_id
                ? `${selected.module_id} / ${selected.module_version}`
                : "None",
              Role: selected.file_role ?? "None",
              Storage: "Stored",
              "Package validation": "Basic XLSX checks completed",
              "Domain validation": "Not performed",
            }).map(([label, value]) => (
              <React.Fragment key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </React.Fragment>
            ))}
          </dl>
        </section>
      )}
      <section className="card future" aria-labelledby="future-title">
        <p className="eyebrow">05 / INPUTS, CALCULATION AND RESULTS</p>
        <h2 id="future-title">Implementation boundary</h2>
        <p id="future-reason">
          Input extraction, domain validation, calculation execution, and result
          viewing/downloads are unavailable. No module in this milestone
          implements these capabilities. Stored files are not calculation-ready.
        </p>
        <div className="future-actions">
          <button disabled aria-describedby="future-reason">
            Review extracted inputs - unavailable
          </button>
          <button disabled aria-describedby="future-reason">
            Run calculation - unavailable
          </button>
          <button disabled aria-describedby="future-reason">
            View / download results - unavailable
          </button>
        </div>
      </section>
    </>
  );
}
