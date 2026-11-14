"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  FileText,
  Trash2,
  Upload,
  RefreshCw,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { api, fetchAPI, DocumentMeta } from "@/lib/api";
import { formatBytes, timeAgo } from "@/lib/utils";

/**
 * Documents page — full document management interface.
 *
 * Shows all uploaded documents with status, size, chunk count.
 * Supports upload (drag & drop), deletion, and refresh.
 */
export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");

  const refresh = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await api.listDocuments();
      setDocuments(data.documents);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!documents.some(d => d.status === "queued" || d.status === "processing")) return;
    const timer = window.setTimeout(() => refresh(true), 2000);
    return () => window.clearTimeout(timer);
  }, [documents, refresh]);

  const handleDelete = async (id: string) => {
    if (!window.confirm("Delete this document and its indexed passages?")) return;
    try {
      await api.deleteDocument(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const handleUpload = async (file: File) => {
    try {
      await api.uploadDocument(file);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  return (
    <div className="mx-auto max-w-7xl p-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold">Documents</h1>
          <p className="mt-1 text-[var(--text-secondary)]">
            Manage your uploaded research documents.
          </p>
        </div>
        <button
          onClick={() => refresh()}
          className="glass glass-hover flex items-center gap-2 rounded-lg px-4 py-2 text-sm"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl bg-red-500/10 p-3 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="tool-controls mb-5"><input aria-label="Search library" placeholder="Search documents…" value={search} onChange={e => setSearch(e.target.value)} /><select aria-label="Filter document type" value={type} onChange={e => setType(e.target.value)}><option value="">All formats</option>{["pdf","docx","txt","md"].map(t => <option value={t} key={t}>{t.toUpperCase()}</option>)}</select><a className="primary-button" href="/dashboard/workspace">Upload documents</a></div>
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 animate-pulse rounded-xl bg-[var(--bg-elevated)]/50" />
          ))}
        </div>
      ) : documents.length === 0 ? (
        <div className="glass flex flex-col items-center justify-center rounded-xl p-16 text-center">
          <Upload className="mb-4 h-12 w-12 text-[var(--text-tertiary)]" />
          <p className="text-[var(--text-secondary)]">No documents uploaded yet.</p>
          <a
            href="/dashboard/workspace"
            className="btn-glow mt-4 inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm"
          >
            <Upload className="h-4 w-4" /> Upload documents in workspace
          </a>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          {documents.filter(d => d.filename.toLowerCase().includes(search.toLowerCase()) && (!type || d.file_type === type)).map((doc, idx) => (
            <motion.div
              key={doc.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05 }}
              className="gradient-border group p-5"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-[var(--bg-elevated)] p-2.5">
                    <FileText className="h-5 w-5 text-cyan-glow" />
                  </div>
                  <div>
                    <div className="text-sm font-medium">{doc.filename}</div>
                    <div className="font-mono text-xs text-[var(--text-tertiary)]">
                      {doc.file_type.toUpperCase()} · {formatBytes(doc.file_size)}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(doc.id)}
                  aria-label={`Delete ${doc.filename}`}
                  disabled={doc.status === "queued" || doc.status === "processing"}
                  className="rounded-lg p-1.5 text-[var(--text-tertiary)] transition-all hover:text-red-500"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-4 flex flex-wrap gap-2"><a className="subtle-button" href={`/dashboard/workspace?document=${doc.id}`}>Research & preview</a><button className="subtle-button" onClick={async () => {const filename = window.prompt("Document filename (keep extension)", doc.filename); if (!filename) return; try {await fetchAPI(`/documents/${doc.id}`, {method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({filename})}); await refresh();} catch(e){setError(String(e));}}}>Rename</button>{doc.status === "error" && <button className="subtle-button" onClick={async () => {try {await fetchAPI(`/documents/${doc.id}/reprocess`, {method:"POST"}); await refresh();} catch(e){setError(String(e));}}}>Reprocess</button>}</div>

              <div className="mt-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {doc.status === "ready" ? (
                    <>
                      <CheckCircle2 className="h-4 w-4 text-emerald-glow" />
                      <span className="text-xs text-[var(--text-secondary)]">Ready</span>
                    </>
                  ) : doc.status === "processing" || doc.status === "queued" ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin text-amber-500" />
                      <span className="text-xs capitalize text-[var(--text-secondary)]">{doc.processing_stage || doc.status}</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="h-4 w-4 text-red-500" />
                      <span className="text-xs text-red-400">Error</span>
                    </>
                  )}
                  <span className="font-mono text-xs text-[var(--text-tertiary)]">
                    · {doc.total_chunks} chunks
                  </span>
                </div>
                <span className="font-mono text-xs text-[var(--text-tertiary)]">
                  {timeAgo(doc.created_at)}
                </span>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
