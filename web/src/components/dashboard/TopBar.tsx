"use client";
import { Search, Plus, LogOut, Sun, Moon, X, FileText } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, fetchAPI, DocumentMeta } from "@/lib/api";
type Workspace = {id: string; name: string};
export default function TopBar() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState("");
  const [search, setSearch] = useState(false); const [term, setTerm] = useState("");
  const [docs, setDocs] = useState<DocumentMeta[]>([]); const [error, setError] = useState("");
  const [light, setLight] = useState(false); const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    fetchAPI<Workspace[]>("/workspaces").then(ws => {
      setWorkspaces(ws); const stored = localStorage.getItem("researchmind-workspace");
      const id = ws.find(w => w.id === stored)?.id || ws[0]?.id || ""; setSelected(id);
      if (stored && !ws.some(w => w.id === stored)) localStorage.removeItem("researchmind-workspace");
    }).catch(e => setError(String(e)));
    const isLight = localStorage.getItem("researchmind-theme") === "light";
    setLight(isLight); document.documentElement.dataset.theme = isLight ? "light" : "dark";
    const key = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key === "k") {e.preventDefault(); setSearch(s => !s);} if (e.key === "Escape") setSearch(false); };
    window.addEventListener("keydown", key); return () => window.removeEventListener("keydown", key);
  }, []);
  useEffect(() => {if (search) {input.current?.focus(); api.listDocuments().then(r => setDocs(r.documents)).catch(e => setError(String(e)));}}, [search]);
  return <><header className="research-topbar"><div className="workspace-selector"><span className="workspace-mark">R</span><select aria-label="Active workspace" value={selected} onChange={e => {localStorage.setItem("researchmind-workspace", e.target.value); window.location.assign("/dashboard");}}>{workspaces.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}</select><span className="local-badge">RESEARCH SPACE</span></div>
    <div className="topbar-actions"><button onClick={() => setSearch(true)} className="search-trigger"><Search size={16} /><span>Search your library</span><kbd>Ctrl K</kbd></button><Link href="/dashboard/workspace?new=1" className="primary-button small"><Plus size={15} /><span>New research</span></Link><button className="icon-button" aria-label="Toggle theme" onClick={() => {setLight(!light); document.documentElement.dataset.theme = light ? "dark" : "light"; localStorage.setItem("researchmind-theme", light ? "dark" : "light");}}>{light ? <Moon size={17} /> : <Sun size={17} />}</button><button className="profile-button" title="Sign out" onClick={async () => {await fetchAPI("/auth/logout", {method: "POST"}); localStorage.removeItem("researchmind-workspace"); window.location.assign("/login");}}><LogOut size={16} /></button></div></header>
    {search && <div className="modal-backdrop" onClick={() => setSearch(false)}><section role="dialog" aria-modal="true" aria-label="Search documents" className="command-dialog" onClick={e => e.stopPropagation()}><div className="command-input"><Search size={19} /><input ref={input} placeholder="Find a document…" value={term} onChange={e => setTerm(e.target.value)} /><button aria-label="Close search" onClick={() => setSearch(false)}><X size={18} /></button></div><div className="command-results">{error && <p role="alert">{error}</p>}{docs.filter(d => d.filename.toLowerCase().includes(term.toLowerCase())).map(d => <Link key={d.id} href={`/dashboard/workspace?document=${d.id}`} onClick={() => setSearch(false)}><FileText size={17} /><span>{d.filename}</span><small>{d.file_type.toUpperCase()}</small></Link>)}{!docs.filter(d => d.filename.toLowerCase().includes(term.toLowerCase())).length && <p>No matching documents. Upload a paper to begin.</p>}</div></section></div>}</>;
}
