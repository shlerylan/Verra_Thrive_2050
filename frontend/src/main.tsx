import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, Workbook } from "./api";
import "./style.css";

const date = (value: string) => new Date(value).toLocaleString("en-GB");
const size = (value: number) => `${value.toLocaleString("en-GB")} bytes`;
const message = (error: unknown) =>
  error instanceof Error && error.name !== "ZodError"
    ? error.message
    : "An unexpected API response was received.";

function App() {
  const [connection, setConnection] = useState<
    "loading" | "connected" | "unavailable"
  >("loading");
  const [files, setFiles] = useState<Workbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [selected, setSelected] = useState<Workbook | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const details = useRef<HTMLElement>(null);

  async function refresh(page = offset) {
    setLoading(true);
    setError("");
    setConnection("loading");
    try {
      await api.health();
      setConnection("connected");
    } catch {
      setConnection("unavailable");
    }
    try {
      setFiles(await api.list(page));
      setOffset(page);
    } catch (e) {
      setError(message(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void refresh(0);
  }, []);

  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setUploading(true);
    setError("");
    setSuccess("");
    try {
      const result = await api.upload(file);
      setFile(null);
      if (input.current) input.current.value = "";
      await refresh(0);
      setSuccess(`${result.original_filename} was uploaded and stored.`);
    } catch (e) {
      setError(message(e));
    } finally {
      setUploading(false);
    }
  }

  async function view(id: string) {
    setDetailLoading(true);
    setError("");
    try {
      setSelected(await api.metadata(id));
      requestAnimationFrame(() => details.current?.focus());
    } catch (e) {
      setError(message(e));
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <>
      <header>
        <a className="brand" href="/" aria-label="Thrive 2050 home">
          <span className="mark" aria-hidden="true">
            T
          </span>
          Thrive <strong>2050</strong>
        </a>
        <span className="review">LOCAL REVIEW · FOUNDATION</span>
      </header>
      <main>
        <div className="intro">
          <div>
            <p className="eyebrow">WORKBOOK LIBRARY</p>
            <h1>Excel Workbooks</h1>
            <p className="lead">
              A shared starting point for understanding project workbooks.
            </p>
          </div>
          <span role="status" className={`connection ${connection}`}>
            <span aria-hidden="true">●</span> API {connection}
          </span>
        </div>
        <aside className="scope">
          <strong>Foundation first.</strong> Upload and inspect original file
          metadata. Calculation modules will be added incrementally; no carbon
          calculations or methodology validation are included yet.
        </aside>
        <section className="card upload" aria-labelledby="upload-title">
          <div>
            <p className="eyebrow">01 / ADD A WORKBOOK</p>
            <h2 id="upload-title">Keep the original. Start with context.</h2>
            <p>
              Only .xlsx files are supported. Files are checked for basic
              package structure and stored without evaluating formulas or
              refreshing links.
            </p>
          </div>
          <form onSubmit={upload}>
            <label htmlFor="workbook">Choose an Excel workbook</label>
            <input
              ref={input}
              id="workbook"
              type="file"
              accept=".xlsx"
              disabled={uploading}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <button disabled={!file || uploading}>
              {uploading ? "Uploading…" : "Upload workbook"}
              <span aria-hidden="true"> ↑</span>
            </button>
            <small>Duplicate uploads are kept as separate records.</small>
          </form>
        </section>
        {error && (
          <div role="alert" className="notice error">
            {error}
          </div>
        )}
        {success && (
          <div role="status" className="notice success">
            {success}
          </div>
        )}
        <section
          className="card library"
          aria-labelledby="library-title"
          aria-busy={loading}
        >
          <div className="section-head">
            <div>
              <p className="eyebrow">02 / UPLOADED FILES</p>
              <h2 id="library-title">Workbook library</h2>
            </div>
            <button
              className="secondary"
              disabled={loading || uploading}
              onClick={() => void refresh()}
            >
              Refresh
            </button>
          </div>
          {loading ? (
            <p role="status" className="empty">
              Loading workbooks…
            </p>
          ) : files.length === 0 ? (
            <p className="empty">
              {error
                ? "The library could not be loaded. Try Refresh."
                : offset
                  ? "No more workbooks on this page."
                  : "No workbooks yet. Upload a file to begin."}
            </p>
          ) : (
            <div className="table-scroll">
              <table>
                <caption className="sr-only">
                  Uploaded workbook metadata
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Filename</th>
                    <th scope="col">Uploaded</th>
                    <th scope="col">Size</th>
                    <th scope="col">SHA-256</th>
                    <th scope="col">Status</th>
                    <th scope="col">Details</th>
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
                        <span className="badge">Stored</span>
                      </td>
                      <td>
                        <button
                          className="text-button"
                          disabled={detailLoading}
                          onClick={() => void view(item.id)}
                          aria-label={`View metadata for ${item.original_filename}`}
                        >
                          View metadata ↗
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
              disabled={!offset || loading || uploading}
              onClick={() => void refresh(Math.max(0, offset - 50))}
            >
              Previous
            </button>
            <span>Page {Math.floor(offset / 50) + 1}</span>
            <button
              className="secondary"
              disabled={files.length < 50 || loading || uploading}
              onClick={() => void refresh(offset + 50)}
            >
              Next
            </button>
          </div>
        </section>
        {detailLoading && <p role="status">Loading metadata…</p>}
        {selected && (
          <section
            className="card metadata"
            aria-labelledby="metadata-title"
            ref={details}
            tabIndex={-1}
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
                Identifier: selected.id,
                Uploaded: date(selected.uploaded_at),
                Size: size(selected.byte_size),
                "SHA-256": selected.sha256,
                Status: selected.status,
              }).map(([key, value]) => (
                <React.Fragment key={key}>
                  <dt>{key}</dt>
                  <dd>{value}</dd>
                </React.Fragment>
              ))}
            </dl>
          </section>
        )}
        <footer>
          Thrive 2050{" "}
          <span>
            Original files. Explicit boundaries. Incremental progress.
          </span>
        </footer>
      </main>
    </>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
