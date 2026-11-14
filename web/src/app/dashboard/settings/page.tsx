"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Settings, Cpu, Database, Brain, Shield, Bell } from "lucide-react";
import { api, fetchAPI } from "@/lib/api";

/**
 * Settings page — configure workspace and view system status.
 * Shows real backend configuration (LLM backend, embedding model, etc.)
 */
export default function SettingsPage() {
  const [config, setConfig] = useState<{chunk_size:number;chunk_overlap:number;top_k:number;hybrid_search:boolean;reranking:boolean}|null>(null);
  const [error, setError] = useState("");
  const [health, setHealth] = useState<{
    status: string;
    version: string;
    database: string;
    vector_store: string;
    embedding_model: string;
    llm_backend: string;
  } | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(e => setError(String(e)));
    fetchAPI<NonNullable<typeof config>>("/settings").then(setConfig).catch(e => setError(String(e)));
  }, []);

  const settings = [
    {
      icon: Brain,
      title: "LLM Backend",
      value: health?.llm_backend?.toUpperCase() || "—",
      description: "Active AI model provider for answer generation",
    },
    {
      icon: Cpu,
      title: "Embedding Model",
      value: health?.embedding_model || "—",
      description: "Sentence Transformers model for vector embeddings",
    },
    {
      icon: Database,
      title: "Database",
      value: health?.database || "—",
      description: "Document metadata storage status",
    },
    {
      icon: Database,
      title: "Vector Store",
      value: health?.vector_store || "—",
      description: "ChromaDB persistence status",
    },
  ];

  return (
    <div className="mx-auto max-w-4xl p-8">
      <h1 className="font-display text-3xl font-bold">Settings</h1>
      {error && <p className="error-box" role="alert">{error}</p>}
      <p className="mt-1 text-[var(--text-secondary)]">
        System configuration and status overview.
      </p>

      {/* System status */}
      <div className="mt-8">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--text-secondary)]">
          <Settings className="h-4 w-4" />
          System Status
        </h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {settings.map((setting, idx) => (
            <motion.div
              key={setting.title}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              className="glass rounded-xl p-4"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-[var(--bg-elevated)] p-2">
                  <setting.icon className="h-4 w-4 text-cyan-glow" />
                </div>
                <div className="flex-1">
                  <div className="text-xs text-[var(--text-tertiary)]">{setting.title}</div>
                  <div className="font-mono text-sm text-[var(--text-primary)]">
                    {setting.value}
                  </div>
                </div>
                <div className="status-dot" style={{
                  background: setting.value === "healthy" || setting.value === "ready" ? "var(--accent-emerald)" : "#f59e0b",
                }} />
              </div>
              <div className="mt-2 text-xs text-[var(--text-tertiary)]">
                {setting.description}
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Configuration info */}
      <div className="mt-8">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--text-secondary)]">
          <Shield className="h-4 w-4" />
          Configuration
        </h3>
        <div className="glass rounded-xl p-6">
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Version</span>
              <span className="font-mono">{health?.version || "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Status</span>
              <span className="font-mono text-emerald-glow">{health?.status || "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Chunk Size</span>
              <span className="font-mono">{config?.chunk_size ?? "—"} chars</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Chunk Overlap</span>
              <span className="font-mono">{config?.chunk_overlap ?? "—"} chars</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Default Top-K</span>
              <span className="font-mono">{config?.top_k ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Hybrid Search</span>
              <span className="font-mono">{config ? config.hybrid_search ? "Enabled" : "Disabled" : "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Cross-Encoder Reranking</span>
              <span className="font-mono">{config ? config.reranking ? "Enabled" : "Disabled" : "—"}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
