"use client";

import { motion } from "framer-motion";
import {
  MessageSquare,
  Search,
  Database,
  Layers,
  Brain,
  CheckCircle2,
  FileText,
  Scan,
} from "lucide-react";

/**
 * Architecture section — visualizes the neural RAG pipeline.
 *
 * Shows the 8-step retrieval pipeline as a horizontal flow with
 * connecting lines and animated reveals.
 */

const pipelineSteps = [
  {
    icon: MessageSquare,
    label: "Query",
    description: "User asks a question in natural language",
  },
  {
    icon: Search,
    label: "Embed",
    description: "Question is converted to vector embeddings",
  },
  {
    icon: Database,
    label: "Retrieve",
    description: "Dense vector search + BM25 keyword fusion",
  },
  {
    icon: Layers,
    label: "Rerank",
    description: "Cross-encoder reranks by relevance",
  },
  {
    icon: Brain,
    label: "Synthesize",
    description: "LLM generates grounded answer with context",
  },
  {
    icon: CheckCircle2,
    label: "Verify",
    description: "Citation labels checked against retrieved source passages",
  },
];

const documentStages = [
  { icon: FileText, label: "Upload", desc: "PDF, DOCX, TXT, MD" },
  { icon: Scan, label: "Extract", desc: "Page-level text" },
  { icon: Layers, label: "Chunk", desc: "Configurable split" },
  { icon: Brain, label: "Embed", desc: "Vector encoding" },
  { icon: Database, label: "Index", desc: "ChromaDB store" },
  { icon: CheckCircle2, label: "Ready", desc: "Searchable" },
];

export default function ArchitectureSection() {
  return (
    <section id="architecture" className="relative py-32">
      {/* Background effects */}
      <div className="absolute inset-0 grid-pattern opacity-20" />
      <div className="absolute left-1/2 top-0 h-96 w-96 -translate-x-1/2 rounded-full bg-electric-blue opacity-5 blur-[120px]" />

      <div className="relative mx-auto max-w-7xl px-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.7 }}
          className="mb-20 text-center"
        >
          <div className="mb-4 inline-flex items-center gap-2 rounded-full glass px-4 py-1.5">
            <span className="font-mono text-xs text-cyan-glow">NEURAL RAG ARCHITECTURE</span>
          </div>
          <h2 className="font-display text-4xl font-bold tracking-tight sm:text-5xl">
            From document to{" "}
            <span className="text-gradient">grounded answer.</span>
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-[var(--text-secondary)]">
            A traceable retrieval workflow, from uploaded passages to source-linked answers.
          </p>
        </motion.div>

        {/* Document processing pipeline */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="mb-16"
        >
          <h3 className="mb-6 text-center font-mono text-xs text-[var(--text-tertiary)]">
            DOCUMENT INDEXING PIPELINE
          </h3>
          <div className="flex flex-wrap items-center justify-center gap-2 md:flex-nowrap">
            {documentStages.map((stage, idx) => (
              <div key={stage.label} className="flex items-center gap-2">
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: idx * 0.1 }}
                  className="glass flex flex-col items-center gap-2 rounded-xl p-4"
                >
                  <stage.icon className="h-6 w-6 text-cyan-glow" />
                  <div className="text-center">
                    <div className="text-sm font-semibold">{stage.label}</div>
                    <div className="font-mono text-xs text-[var(--text-tertiary)]">{stage.desc}</div>
                  </div>
                </motion.div>
                {idx < documentStages.length - 1 && (
                  <div className="hidden h-px w-8 bg-gradient-to-r from-cyan-glow/50 to-transparent md:block" />
                )}
              </div>
            ))}
          </div>
        </motion.div>

        {/* Query → Answer pipeline */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
        >
          <h3 className="mb-6 text-center font-mono text-xs text-[var(--text-tertiary)]">
            QUESTION ANSWERING PIPELINE
          </h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">
            {pipelineSteps.map((step, idx) => (
              <motion.div
                key={step.label}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.1, duration: 0.5 }}
                className="gradient-border relative p-5"
              >
                {/* Step number */}
                <div className="absolute right-3 top-3 font-mono text-xs text-[var(--text-tertiary)]">
                  {String(idx + 1).padStart(2, "0")}
                </div>
                <step.icon className="mb-3 h-7 w-7 text-cyan-glow" />
                <div className="mb-1 text-sm font-semibold">{step.label}</div>
                <div className="text-xs text-[var(--text-secondary)]">
                  {step.description}
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* AI accuracy principles */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7 }}
          className="mt-16 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
        >
          {[
            "Answers from retrieved evidence only",
            "Never fabricates quotations or page numbers",
            "Identifies contradictory information",
            "Clearly communicates uncertainty",
          ].map((principle, idx) => (
            <div key={idx} className="glass flex items-center gap-3 rounded-xl p-4">
              <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-glow" />
              <span className="text-sm text-[var(--text-secondary)]">{principle}</span>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
