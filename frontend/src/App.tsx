import React, { useEffect, useState } from "react";
import { api, Catalogue, Project } from "./api";
import { message } from "./format";
import { Workspace } from "./Workspace";
export function App() {
  const [connection, setConnection] = useState("loading");
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

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
    const results = await Promise.allSettled([
      api.projects(page),
      api.catalogue(),
    ]);
    if (results[0].status === "fulfilled") {
      setProjects(results[0].value);
      setOffset(page);
    } else {
      setProjects([]);
      setError(message(results[0].reason));
    }
    if (results[1].status === "fulfilled") setCatalogue(results[1].value);
    else {
      setCatalogue(null);
      setError(message(results[1].reason));
    }
    setLoading(false);
  }
  useEffect(() => {
    void refresh(0);
  }, []);

  async function select(id: string) {
    setProject(null);
    if (!id) return;
    setBusy(true);
    setError("");
    try {
      setProject(await api.project(id));
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function create(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const created = await api.createProject(name.trim(), description);
      setName("");
      setDescription("");
      await refresh(0);
      setProject(created);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header>
        <a className="brand" href="/">
          <span className="mark" aria-hidden="true">
            T
          </span>
          Thrive <strong>2050</strong>
        </a>
        <span role="status" className={`connection ${connection}`}>API {connection}</span>
      </header>
      <main>
        {!project && <div className="intro">
          <div>
            <p className="eyebrow">PROJECT WORKSPACE</p>
            <h1>Calculate agricultural leakage.</h1>
            <p className="lead">
              Select a project, then upload a sample workbook or your own Excel inputs.
            </p>
          </div>
        </div>}
        <aside className="scope">
          <strong>Calculation preview.</strong> Project eligibility and input evidence require review before verified VCS reporting.
        </aside>
        {error && (
          <p role="alert" className="notice error">
            {error}
          </p>
        )}
        {!project && <section className="card upload" aria-labelledby="projects-title">
          <div>
            <p className="eyebrow">01 / PROJECT</p>
            <h2 id="projects-title">Select your project</h2>
            <label htmlFor="project">Project collection</label>
            <select
              id="project"
              value=""
              disabled={loading || busy}
              onChange={(e) => void select(e.target.value)}
            >
              <option value="">Choose a project</option>
              {projects.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            {loading ? (
              <p role="status">Loading projects...</p>
            ) : (
              projects.length === 0 && (
                <p>No projects on this page. Create a project to begin.</p>
              )
            )}
            <div className="project-paging">
              <button
                className="secondary"
                disabled={loading || busy}
                onClick={() => void refresh()}
              >
                Refresh projects
              </button>
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
                disabled={projects.length < 50 || loading || busy}
                onClick={() => void refresh(offset + 50)}
              >
                Next
              </button>
            </div>
          </div>
          <form onSubmit={create}>
            <h2>Create a project</h2>
            <label htmlFor="name">Project name</label>
            <input
              id="name"
              required
              maxLength={160}
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={busy}
            />
            <label htmlFor="description">Description (optional)</label>
            <textarea
              id="description"
              maxLength={4000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={busy}
            />
            <button disabled={busy || !name.trim()}>
              {busy ? "Please wait..." : "Create project"}
            </button>
          </form>
        </section>}
        {project ? (
          <Workspace
            key={project.id}
            project={project}
            catalogue={catalogue}
            onChangeProject={() => setProject(null)}
            onAssignment={(updated) =>
              setProject((current) =>
                current?.id === updated.id ? updated : current,
              )
            }
          />
        ) : (
          <p className="empty" role="status">
            {busy
              ? "Selecting project..."
              : "Select or create a project to collect files."}
          </p>
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
