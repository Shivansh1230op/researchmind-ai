"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { GitCompare, FileText, Loader2, Sparkles } from "lucide-react";
import { api, DocumentMeta } from "@/lib/api";

/**
 * Compare Research page — compare multiple documents.
 * Users select 2-5 documents and choose an aspect to compare.
 */
export default function ComparePage() {
  const [documents, setDocuments] = useState<DocumentMeta[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [aspect, setAspect] = useState("general");
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listDocuments().then((data) => setDocuments(data.documents)).catch(() => {});
  }, []);

  const readyDocs = documents.filter((d) => d.status === "ready");

  const handleCompare = async () => {
    if (selected.length < 2) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.compare(selected, aspect);
      setResult(data.comparison);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl p-8">
      <h1 className="font-display text-3xl font-bold">Compare Research</h1>
      <p className="mt-1 text-[var(--text-secondary)]">
        Compare multiple documents to find similarities, differences, and research gaps.
      </p>

      {/* Document selection */}
      <div className="mt-8">
        <h3 className="mb-3 text-sm font-semibold text-[var(--text-secondary)]">
          Select 2–5 documents to compare
        </h3>
        {readyDocs.length < 2 ? (
          <div className="glass rounded-xl p-8 text-center text-[var(--text-tertiary)]">
            Upload at least 2 documents to use comparison.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {readyDocs.map((doc) => (
              <button
                key={doc.id}
                onClick={() => {
                  setSelected((prev) =>
                    prev.includes(doc.id)
                      ? prev.filter((d) => d !== doc.id)
                      : prev.length < 5
                      ? [...prev, doc.id]
                      : prev
                  );
                }}
                className={`flex items-center gap-2 rounded-xl border p-3 text-left transition-all ${
                  selected.includes(doc.id)
                    ? "border-cyan-glow/30 bg-cyan-glow/5"
                    : "border-[var(--border-subtle)] hover:border-[var(--border-strong)]"
                }`}
              >
                <FileText className={`h-4 w-4 ${selected.includes(doc.id) ? "text-cyan-glow" : "text-[var(--text-tertiary)]"}`} />
                <span className="truncate text-xs">{doc.filename}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Aspect selector */}
      <div className="mt-6">
        <h3 className="mb-3 text-sm font-semibold text-[var(--text-secondary)]">
          Comparison aspect
        </h3>
        <div className="flex flex-wrap gap-2">
          {["general", "methodology", "findings", "arguments"].map((a) => (
            <button
              key={a}
              onClick={() => setAspect(a)}
              className={`rounded-lg px-3 py-1.5 text-sm capitalize transition-all ${
                aspect === a
                  ? "bg-cyan-glow/10 text-cyan-glow"
                  : "glass text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              {a}
            </button>
          ))}
        </div>
      </div>

      {/* Compare button */}
      <button
        onClick={handleCompare}
        disabled={selected.length < 2 || loading}
        className="btn-glow mt-6 flex items-center gap-2 rounded-xl px-6 py-3 text-sm disabled:opacity-30"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <GitCompare className="h-4 w-4" />}
        {loading ? "Comparing..." : `Compare ${selected.length} documents`}
      </button>

      {error && (
        <div className="mt-4 rounded-xl bg-red-500/10 p-3 text-sm text-red-400">{error}</div>
      )}

      {/* Result */}
      {result && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass mt-6 rounded-xl p-6"
        >
          <div className="mb-3 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-cyan-glow" />
            <span className="font-display text-sm font-semibold">Comparison Analysis</span>
          </div>
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--text-primary)]">
            {result}
          </div>
        </motion.div>
      )}
    </div>
  );
}
