"use client";

import { useEffect, useState } from "react";
import { FileText, Sparkles, Loader2, Download, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, apiBase, fetchAPI, DocumentMeta } from "@/lib/api";

const modes = [
  ["short", "Short summary"], ["comprehensive", "Detailed summary"],
  ["executive", "Executive summary"], ["bullet_points", "Bullet-point summary"],
  ["academic", "Academic summary"], ["chapters", "Chapter-by-chapter summary"],
  ["key_points", "Key findings"], ["beginner", "Beginner-friendly explanation"],
  ["definitions", "Concepts & definitions"],
] as const;

type Passage = { document_id: string; document_name: string; page_number: number | null; chunk_index: number; content: string };
type Summary = { document_id: string; document_name: string; summary: string; truncated: boolean; sources: Passage[] };

export default function Summarizer() {
  const [documents, setDocuments] = useState<DocumentMeta[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [mode, setMode] = useState("comprehensive");
  const [length, setLength] = useState("medium");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [passage, setPassage] = useState<Passage | null>(null);

  useEffect(() => {
    api.listDocuments().then(result => setDocuments(result.documents.filter(doc => doc.status === "ready")))
      .catch(e => setError(String(e))).finally(() => setLoading(false));
  }, []);

  async function generate() {
    setBusy(true); setError("");
    try {
      const result = await fetchAPI<{ summaries: Summary[] }>("/research/summarize", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_ids: selected, summary_type: mode, length }),
      });
      setSummaries(result.summaries);
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  function exportSummaries() {
    const text = summaries.map(summary => `# ${summary.document_name}\n\n${summary.summary}\n\n${summary.truncated ? "Note: source input was truncated.\n\n" : ""}## Source passages\n\n${summary.sources.map(source => `- Page ${source.page_number || "unavailable"}, passage ${source.chunk_index}: ${source.content}`).join("\n\n")}`).join("\n\n---\n\n");
    const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = "research-summaries.md"; anchor.click();
    URL.revokeObjectURL(url);
  }

  return <div className="page-container">
    <div className="page-heading"><div><span className="eyebrow">SEE THE ESSENTIALS</span><h1>AI summarizer</h1><p>Select your papers, choose a perspective, and keep the source passages close.</p></div></div>
    <section className="panel panel-padding">
      <div className="section-title"><h2>Select source documents</h2><span className="eyebrow">{selected.length} / 10 SELECTED</span></div>
      <div className="document-checklist">{documents.map(document => <label key={document.id}>
        <input type="checkbox" checked={selected.includes(document.id)} disabled={busy || (!selected.includes(document.id) && selected.length >= 10)} onChange={() => setSelected(ids => ids.includes(document.id) ? ids.filter(id => id !== document.id) : [...ids, document.id])} />
        <FileText size={16} />{document.filename}
      </label>)}</div>
      {loading && <p className="text-xs text-[var(--text-secondary)]" role="status">Opening your library…</p>}
      {!loading && !documents.length && <p className="mb-5 text-xs text-[var(--text-secondary)]">No indexed documents in this workspace. <a className="text-[#a6baff]" href="/dashboard/workspace">Upload a document →</a></p>}
      <div className="tool-controls">
        <select aria-label="Summary type" value={mode} disabled={busy} onChange={e => setMode(e.target.value)}>{modes.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>
        <select aria-label="Summary length" value={length} disabled={busy} onChange={e => setLength(e.target.value)}><option value="short">Brief · up to 180 words</option><option value="medium">Balanced · up to 400 words</option><option value="long">Extended · up to 900 words</option></select>
        <button className="primary-button" onClick={generate} disabled={busy || !selected.length}>{busy ? <Loader2 className="animate-spin" size={15} /> : <Sparkles size={15} />}{busy ? "Summarizing your sources…" : "Generate summaries"}</button>
      </div>
      <p className="mt-4 text-[10px] leading-6 text-[var(--text-tertiary)]">Each selected document receives its own summary. Lengths are generation targets; review the source material before using a summary as evidence.</p>
    </section>
    {error && <p className="error-box" role="alert">{error}</p>}
    {!!summaries.length && <div className="section-title mt-7"><h2>{summaries.length} document summaries</h2><button className="subtle-button" onClick={exportSummaries}><Download size={13} />Export Markdown</button></div>}
    {summaries.map(summary => <article className="tool-output" key={summary.document_id}>
      <div className="section-title"><h2>{summary.document_name}</h2><a className="subtle-button" href={`/dashboard/workspace?document=${summary.document_id}`}>Research this paper</a></div>
      {summary.truncated && <p role="status" className="error-box">This summary uses the beginning of a long document. Source input was limited to 50,000 characters.</p>}
      <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}>{summary.summary}</ReactMarkdown></div>
      <details className="summary-evidence"><summary>Inspect source passages ({summary.sources.length})</summary><p>These passages come from the document being summarized. Check the full source for the context of each claim.</p>
        {summary.sources.map((source, index) => <button key={index} className="source-card mt-3" onClick={() => setPassage(source)}><small>PAGE {source.page_number || "UNAVAILABLE"} · PASSAGE {source.chunk_index}</small><p>{source.content}</p><span className="source-action">Open source passage →</span></button>)}
      </details>
    </article>)}
    {passage && <div className="modal-backdrop" onClick={() => setPassage(null)}><section className="source-dialog" role="dialog" aria-modal="true" aria-label="Summary source passage" onClick={e => e.stopPropagation()}><header><h3>{passage.document_name}</h3><button className="icon-button" aria-label="Close source" onClick={() => setPassage(null)}><X size={17} /></button></header><blockquote>{passage.content}</blockquote>{passage.document_name.toLowerCase().endsWith(".pdf") && <iframe title="Source PDF" src={`${apiBase}/documents/${passage.document_id}/file#page=${passage.page_number || 1}`} />}<a className="subtle-button mt-4" href={`/dashboard/workspace?document=${passage.document_id}`}>Open document workspace</a></section></div>}
  </div>;
}
