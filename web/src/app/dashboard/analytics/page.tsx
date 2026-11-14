"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { BarChart3, FileText, Brain, MessageSquare } from "lucide-react";
import { api, DocumentMeta } from "@/lib/api";

/**
 * Analytics page — workspace statistics and insights.
 * Shows real data from the backend, no fabricated metrics.
 */
export default function AnalyticsPage() {
  const [documents, setDocuments] = useState<DocumentMeta[]>([]);

  useEffect(() => {
    api.listDocuments()
      .then((data) => setDocuments(data.documents))
      .catch(() => {});
  }, []);

  const totalChunks = documents.reduce((s, d) => s + d.total_chunks, 0);
  const totalSize = documents.reduce((s, d) => s + d.file_size, 0);
  const byType = documents.reduce((acc, d) => {
    acc[d.file_type] = (acc[d.file_type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const stats = [
    { label: "Total Documents", value: documents.length, icon: FileText, color: "text-cyan-glow" },
    { label: "Total Chunks", value: totalChunks, icon: Brain, color: "text-electric-violet" },
    { label: "Storage Used", value: `${(totalSize / 1024 / 1024).toFixed(1)} MB`, icon: BarChart3, color: "text-emerald-glow" },
    { label: "File Types", value: Object.keys(byType).length, icon: MessageSquare, color: "text-electric-blue" },
  ];

  return (
    <div className="mx-auto max-w-7xl p-8">
      <h1 className="font-display text-3xl font-bold">Analytics</h1>
      <p className="mt-1 text-[var(--text-secondary)]">
        Workspace statistics and document insights.
      </p>

      {/* Stats */}
      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat, idx) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.1 }}
            className="gradient-border p-5"
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="text-sm text-[var(--text-secondary)]">{stat.label}</div>
                <div className="mt-2 font-display text-2xl font-bold">{stat.value}</div>
              </div>
              <div className="rounded-lg bg-[var(--bg-elevated)] p-2.5">
                <stat.icon className={`h-5 w-5 ${stat.color}`} />
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Document type breakdown */}
      <div className="mt-8">
        <h3 className="mb-4 text-sm font-semibold text-[var(--text-secondary)]">
          Documents by Type
        </h3>
        <div className="glass rounded-xl p-6">
          {Object.entries(byType).length === 0 ? (
            <p className="text-center text-[var(--text-tertiary)]">No documents uploaded.</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(byType).map(([type, count]) => (
                <div key={type} className="flex items-center gap-3">
                  <span className="w-12 font-mono text-xs uppercase text-[var(--text-secondary)]">{type}</span>
                  <div className="h-6 flex-1 overflow-hidden rounded-lg bg-[var(--bg-elevated)]">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${(count / documents.length) * 100}%` }}
                      transition={{ duration: 0.5 }}
                      className="h-full bg-gradient-to-r from-cyan-glow to-electric-blue"
                    />
                  </div>
                  <span className="w-8 text-right font-mono text-sm">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
