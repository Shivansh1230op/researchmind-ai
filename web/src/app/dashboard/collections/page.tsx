"use client";
import { useEffect, useState } from "react";
import { FolderOpen, Plus, ArrowRight, Pencil, Trash2 } from "lucide-react";
import { fetchAPI } from "@/lib/api";

type Workspace = { id: string; name: string; documents: number };

export default function WorkspacesPage() {
  const [rows, setRows] = useState<Workspace[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState("");
  const [editName, setEditName] = useState("");

  async function refresh() { setRows(await fetchAPI<Workspace[]>("/workspaces")); }
  useEffect(() => { refresh().catch(e => setError(String(e))); }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      await fetchAPI("/workspaces", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
      setName(""); await refresh();
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  async function rename(e: React.FormEvent, id: string) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      await fetchAPI(`/workspaces/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: editName }) });
      setEditing(""); await refresh();
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  async function remove(workspace: Workspace) {
    if (!window.confirm(`Delete empty workspace “${workspace.name}”? Workspaces containing documents, reports or conversations must be emptied first.`)) return;
    setBusy(true); setError("");
    try {
      await fetchAPI(`/workspaces/${workspace.id}`, { method: "DELETE" });
      if (localStorage.getItem("researchmind-workspace") === workspace.id) {
        localStorage.removeItem("researchmind-workspace"); window.location.assign("/dashboard/collections");
      } else await refresh();
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  return <div className="page-container">
    <div className="page-heading"><div><span className="eyebrow">A SPACE FOR EVERY QUESTION</span><h1>Research workspaces</h1><p>Separate your research topics. Keep each conversation grounded in the right library.</p></div></div>
    <form onSubmit={create} className="tool-controls"><input aria-label="Workspace name" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Language model evaluation" maxLength={120} required /><button className="primary-button" disabled={busy || !name.trim()}><Plus size={15} />Create workspace</button></form>
    {error && <p role="alert" className="error-box">{error}</p>}
    <div className="workspace-grid">{rows.map(workspace => <section key={workspace.id} className="workspace-card">
      <FolderOpen size={25} className="text-[#9ab0ee]" />
      {editing === workspace.id ? <form className="mt-4 tool-controls" onSubmit={e => rename(e, workspace.id)}><input aria-label="New workspace name" value={editName} maxLength={120} onChange={e => setEditName(e.target.value)} /><button className="subtle-button" disabled={busy || !editName.trim()}>Save</button><button className="subtle-button" type="button" onClick={() => setEditing("")}>Cancel</button></form> : <h2>{workspace.name}</h2>}
      <p>{workspace.documents} documents · Private workspace</p>
      <div className="flex items-center gap-1"><button className="subtle-button mr-auto" onClick={() => { localStorage.setItem("researchmind-workspace", workspace.id); window.location.assign("/dashboard"); }}>Open workspace <ArrowRight size={13} /></button>
        <button className="icon-button" aria-label={`Rename ${workspace.name}`} disabled={busy} onClick={() => { setEditing(workspace.id); setEditName(workspace.name); }}><Pencil size={14} /></button>
        <button className="icon-button" aria-label={`Delete ${workspace.name}`} disabled={busy || workspace.documents > 0} onClick={() => remove(workspace)}><Trash2 size={14} /></button>
      </div>
    </section>)}</div>
  </div>;
}
