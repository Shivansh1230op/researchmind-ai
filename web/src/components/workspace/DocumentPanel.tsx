"use client";

import { useRef, useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload,
  FileText,
  Trash2,
  RefreshCw,
  CheckCircle2,
  Loader2,
  AlertCircle,
  File,
} from "lucide-react";
import { api, DocumentMeta } from "@/lib/api";
import { formatBytes, cn } from "@/lib/utils";

/**
 * DocumentPanel — left panel of the research workspace.
 *
 * Features:
 * - Drag-and-drop or click-to-upload
 * - Upload progress bar
 * - Document list with selection checkboxes
 * - Processing status indicators
 * - Delete documents
 * - Auto-refresh after operations
 */

interface Props {
  documents: DocumentMeta[];
  selectedDocIds: string[];
  onToggleSelect: (id: string) => void;
  onRefresh: () => void;
}

export default function DocumentPanel({
  documents,
  selectedDocIds,
  onToggleSelect,
  onRefresh,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    onRefresh();
  }, [onRefresh]);

  useEffect(() => {
    if (!documents.some(d => d.status === "queued" || d.status === "processing")) return;
    const poll = window.setTimeout(onRefresh, 2000);
    return () => window.clearTimeout(poll);
  }, [documents, onRefresh]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setProgress(0);
    setError(null);

    try {
      await api.uploadDocument(file, (pct) => setProgress(pct));
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      setProgress(0);
    }
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0 || uploading) return;
    for (const file of Array.from(files)) await handleUpload(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    handleFiles(e.dataTransfer.files);
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Delete this document and its indexed passages?")) return;
    try {
      await api.deleteDocument(id);
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  return (
    <div className="flex h-full flex-col bg-[var(--bg-surface)]/30">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-4 py-3">
        <h3 className="font-display text-sm font-semibold">Document Library</h3>
        <button
          onClick={onRefresh}
          className="rounded-md p-1.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Upload area */}
      <div className="p-3">
        <div
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          className={cn(
            "relative cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition-all",
            dragActive
              ? "border-cyan-glow bg-cyan-glow/5"
              : "border-[var(--border-strong)] hover:border-[var(--border-glow)]"
          )}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.md"
            onChange={(e) => handleFiles(e.target.files)}
            className="hidden"
          />
          <Upload className="mx-auto mb-2 h-6 w-6 text-[var(--text-tertiary)]" />
          <p className="text-xs text-[var(--text-secondary)]">
            Drop files or click to upload
          </p>
          <p className="mt-1 font-mono text-[10px] text-[var(--text-tertiary)]">
            PDF · DOCX · TXT · MD
          </p>

          {/* Upload progress */}
          {uploading && (
            <div className="mt-3">
              <div className="flex items-center gap-2">
                <Loader2 className="h-3 w-3 animate-spin text-cyan-glow" />
                <span className="font-mono text-xs text-cyan-glow">{progress < 100 ? `Uploading ${progress}%` : "Processing document on server…"}</span>
              </div>
              <div className="mt-1 h-1 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
                <motion.div
                  className="h-full bg-gradient-to-r from-cyan-glow to-electric-blue"
                  animate={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Error message */}
        {error && (
          <div className="mt-2 flex items-center gap-2 rounded-lg bg-red-500/10 p-2 text-xs text-red-400">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            {error}
          </div>
        )}
      </div>

      {/* Document list */}
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <File className="mb-2 h-8 w-8 text-[var(--text-tertiary)]" />
            <p className="text-xs text-[var(--text-tertiary)]">No documents yet</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            <AnimatePresence>
              {documents.map((doc) => (
                <motion.div
                  key={doc.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className={cn(
                    "group flex items-center gap-2 rounded-lg border p-2.5 transition-all",
                    selectedDocIds.includes(doc.id)
                      ? "border-cyan-glow/30 bg-cyan-glow/5"
                      : "border-[var(--border-subtle)] bg-[var(--bg-elevated)]/30 hover:border-[var(--border-strong)]"
                  )}
                >
                  {/* Checkbox */}
                  {doc.status === "ready" && (
                    <button
                      onClick={() => onToggleSelect(doc.id)}
                      className={cn(
                        "flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-all",
                        selectedDocIds.includes(doc.id)
                          ? "border-cyan-glow bg-cyan-glow/20"
                          : "border-[var(--border-strong)]"
                      )}
                    >
                      {selectedDocIds.includes(doc.id) && (
                        <CheckCircle2 className="h-3 w-3 text-cyan-glow" />
                      )}
                    </button>
                  )}

                  {/* File info */}
                  <div className="flex min-w-0 flex-1 items-center gap-2">
                    <FileText className="h-4 w-4 shrink-0 text-[var(--text-tertiary)]" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-xs font-medium">{doc.filename}</div>
                      <div className="font-mono text-[10px] text-[var(--text-tertiary)]">
                        {doc.total_chunks} chunks · {formatBytes(doc.file_size)}
                      </div>
                      {doc.processing_stage && doc.status !== "ready" && <div className="mt-1 text-[10px] capitalize text-amber-300" role="status">{doc.processing_stage}</div>}
                    </div>
                  </div>

                  {/* Status */}
                  {(doc.status === "processing" || doc.status === "queued") && (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-500" />
                  )}
                  {doc.status === "ready" && (
                    <div className="h-2 w-2 rounded-full bg-emerald-glow shadow-[0_0_8px_var(--accent-emerald)]" />
                  )}
                  {doc.status === "error" && (
                    <AlertCircle className="h-3.5 w-3.5 text-red-500" />
                  )}

                  {/* Delete button */}
                  <button
                    onClick={() => handleDelete(doc.id)}
                    disabled={doc.status === "queued" || doc.status === "processing"}
                    aria-label={`Delete ${doc.filename}`}
                    className="rounded p-1 text-[var(--text-tertiary)] transition-all hover:text-red-500"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}
