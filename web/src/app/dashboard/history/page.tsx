"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MessageSquare, ArrowUpRight, Pencil, Trash2, Check, X } from "lucide-react";
import { fetchAPI } from "@/lib/api";

type Conversation = { id: string; title: string; updated_at: string };

export default function HistoryPage() {
  const [sessions, setSessions] = useState<Conversation[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    fetchAPI<Conversation[]>("/chat/sessions")
      .then(setSessions)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  async function rename(e: React.FormEvent, id: string) {
    e.preventDefault();
    setBusy(id); setError("");
    try {
      const renamed = await fetchAPI<{ id: string; title: string }>(`/chat/sessions/${encodeURIComponent(id)}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }),
      });
      setSessions(rows => rows.map(row => row.id === id ? { ...row, title: renamed.title } : row));
      setEditing("");
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function remove(session: Conversation) {
    if (!window.confirm(`Delete “${session.title}” and its messages?`)) return;
    setBusy(session.id); setError("");
    try {
      await fetchAPI(`/chat/sessions/${encodeURIComponent(session.id)}`, { method: "DELETE" });
      setSessions(rows => rows.filter(row => row.id !== session.id));
      const key = `researchmind-chat-${localStorage.getItem("researchmind-workspace") || "default"}`;
      if (localStorage.getItem(key) === session.id) localStorage.removeItem(key);
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  return <div className="page-container">
    <div className="page-heading"><div><span className="eyebrow">PICK UP THE THREAD</span><h1>Conversation history</h1><p>Your previous questions, sources, and discoveries.</p></div></div>
    {error && <p className="error-box" role="alert">{error}</p>}
    <div className="history-list">{sessions.map(session => <article className="history-row" key={session.id}>
      <MessageSquare size={20} className="shrink-0 text-[#94acef]" />
      {editing === session.id ? <form className="history-edit" onSubmit={e => rename(e, session.id)}>
        <input autoFocus aria-label="Conversation title" value={title} maxLength={120} onChange={e => setTitle(e.target.value)} />
        <button className="icon-button" aria-label="Save conversation title" disabled={!!busy || !title.trim()}><Check size={16} /></button>
        <button className="icon-button" type="button" aria-label="Cancel rename" onClick={() => setEditing("")}><X size={16} /></button>
      </form> : <><Link className="history-link" href={`/dashboard/workspace?session=${encodeURIComponent(session.id)}`}>
        {session.title}<small>{new Date(session.updated_at).toLocaleString()}</small>
      </Link><button className="icon-button" aria-label={`Rename ${session.title}`} disabled={!!busy} onClick={() => { setEditing(session.id); setTitle(session.title); }}><Pencil size={14} /></button>
        <button className="icon-button" aria-label={`Delete ${session.title}`} disabled={!!busy} onClick={() => remove(session)}><Trash2 size={14} /></button>
        <Link className="icon-button" href={`/dashboard/workspace?session=${encodeURIComponent(session.id)}`} aria-label={`Resume ${session.title}`}><ArrowUpRight size={15} /></Link></>}
    </article>)}</div>
    {!sessions.length && <div className="panel empty-panel">{loading ? "Loading conversations…" : "No conversations yet. Start with a question in the research workspace."}<br /><Link href="/dashboard/workspace">Start researching →</Link></div>}
  </div>;
}
