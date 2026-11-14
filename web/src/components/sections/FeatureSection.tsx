"use client";

import { motion } from "framer-motion";
import {
  Brain,
  FileSearch,
  GitCompare,
  Quote,
  Layers,
  ShieldCheck,
  Database,
  Cpu,
} from "lucide-react";

/**
 * Feature section — showcases the platform's core capabilities.
 * Uses scroll-triggered reveal animations with staggered children.
 */

const features = [
  {
    icon: Brain,
    title: "Neural Retrieval Engine",
    description:
      "Dense vector search, keyword scoring, metadata filtering, and optional cross-encoder reranking over your documents.",
    gradient: "from-cyan-glow to-electric-blue",
  },
  {
    icon: FileSearch,
    title: "Document Intelligence",
    description:
      "Upload PDF, DOCX, TXT, or Markdown files. Extract text, preserve page references, and index passages for retrieval.",
    gradient: "from-electric-blue to-electric-violet",
  },
  {
    icon: Quote,
    title: "Precision Citation Engine",
    description:
      "Inspect retrieved passages and available page references beside your answer. Open original PDFs to check the context.",
    gradient: "from-electric-violet to-electric-purple",
  },
  {
    icon: GitCompare,
    title: "Comparative Research",
    description:
      "Compare multiple research papers side by side. Identify similarities, contradictions, and research gaps automatically.",
    gradient: "from-emerald-glow to-cyan-glow",
  },
  {
    icon: Layers,
    title: "Multi-Model Intelligence",
    description:
      "Configure OpenAI-compatible APIs, Gemini, Ollama, or a local Hugging Face model on the server. No simulated AI answers.",
    gradient: "from-cyan-glow to-electric-violet",
  },
  {
    icon: ShieldCheck,
    title: "Security & Privacy",
    description:
      "Revocable login sessions, workspace ownership checks, guarded source access, and explicit handling of untrusted document text.",
    gradient: "from-electric-blue to-emerald-glow",
  },
  {
    icon: Database,
    title: "Vector Infrastructure",
    description:
      "Persistent ChromaDB vectors with local Sentence Transformers embeddings. SQLAlchemy stores document and conversation metadata.",
    gradient: "from-electric-violet to-electric-blue",
  },
  {
    icon: Cpu,
    title: "Cross-Encoder Reranking",
    description:
      "Improve retrieval precision with cross-encoder reranking. Inspect the underlying passages for context.",
    gradient: "from-emerald-glow to-electric-blue",
  },
];

export default function FeatureSection() {
  return (
    <section id="features" className="relative py-32">
      <div className="absolute inset-0 dot-pattern opacity-20" />
      <div className="relative mx-auto max-w-7xl px-6">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.7 }}
          className="mb-16 text-center"
        >
          <div className="mb-4 inline-flex items-center gap-2 rounded-full glass px-4 py-1.5">
            <span className="font-mono text-xs text-cyan-glow">PLATFORM CAPABILITIES</span>
          </div>
          <h2 className="font-display text-4xl font-bold tracking-tight sm:text-5xl">
            Built for{" "}
            <span className="text-gradient">serious research.</span>
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-[var(--text-secondary)]">
            Every component is engineered for accuracy, traceability, and scale.
          </p>
        </motion.div>

        {/* Feature grid */}
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((feature, idx) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 40 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.6, delay: idx * 0.08 }}
              className="gradient-border group relative p-6"
            >
              {/* Icon */}
              <div
                className={`mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${feature.gradient} opacity-90 transition-opacity group-hover:opacity-100`}
              >
                <feature.icon className="h-6 w-6 text-white" />
              </div>

              <h3 className="mb-2 font-display text-lg font-semibold">
                {feature.title}
              </h3>
              <p className="text-sm leading-relaxed text-[var(--text-secondary)]">
                {feature.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
