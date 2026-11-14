"use client";

import { motion } from "framer-motion";
import { ArrowRight, FileSearch, Sparkles, Zap } from "lucide-react";
import NeuralBackground from "./NeuralBackground";

/**
 * Hero section — the cinematic centerpiece of the landing page.
 *
 * Features:
 * - Animated neural network background (canvas)
 * - Gradient mesh overlay
 * - Headline with gradient text
 * - System status indicators
 * - CTA buttons
 * - Floating document panel preview
 */
export default function Hero() {
  const statusItems = [
    { label: "Local embeddings", status: "Sentence Transformers", color: "emerald" },
    { label: "Retrieval", status: "Vector + keyword", color: "cyan" },
    { label: "Sources", status: "Document linked", color: "violet" },
  ];

  return (
    <section className="relative flex min-h-screen items-center justify-center overflow-hidden bg-radial-glow">
      {/* Neural network background */}
      <div className="absolute inset-0 opacity-60">
        <NeuralBackground />
      </div>

      {/* Grid pattern overlay */}
      <div className="absolute inset-0 grid-pattern opacity-30" />

      {/* Gradient orbs */}
      <div className="absolute left-1/4 top-1/4 h-96 w-96 rounded-full bg-electric-blue opacity-10 blur-[120px]" />
      <div className="absolute right-1/4 top-1/3 h-80 w-80 rounded-full bg-electric-violet opacity-10 blur-[100px]" />
      <div className="absolute bottom-1/4 left-1/3 h-72 w-72 rounded-full bg-cyan-glow opacity-5 blur-[80px]" />

      {/* Content */}
      <div className="relative z-10 mx-auto max-w-5xl px-6 text-center">
        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.6 }}
          className="mb-8 inline-flex items-center gap-2 rounded-full glass px-4 py-1.5"
        >
          <span className="status-dot" />
          <span className="font-mono text-xs text-[var(--text-secondary)]">
            NEURAL RAG INFRASTRUCTURE v1.0
          </span>
        </motion.div>

        {/* Headline */}
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className="font-display text-5xl font-bold tracking-tight text-balance sm:text-6xl md:text-7xl"
        >
          Research Smarter. Discover Deeper.{" "}
          <span className="text-gradient">Think Beyond.</span>
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35, duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto mt-6 max-w-2xl text-lg text-[var(--text-secondary)] text-balance"
        >
          Transform research papers and complex documents into actionable intelligence with next-generation Generative AI.
        </motion.p>

        {/* CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.8 }}
          className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row"
        >
          <a
            href="/dashboard"
            className="btn-glow flex items-center gap-2 rounded-xl px-6 py-3 text-base"
          >
            Launch AI Workspace
            <ArrowRight className="h-4 w-4" />
          </a>
          <a
            href="#features"
            className="glass glass-hover flex items-center gap-2 rounded-xl px-6 py-3 text-base text-[var(--text-primary)]"
          >
            <Sparkles className="h-4 w-4 text-cyan-glow" />
            Explore Features
          </a>
        </motion.div>

        {/* System status indicators */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7, duration: 0.8 }}
          className="mt-16 flex flex-wrap items-center justify-center gap-6"
        >
          {statusItems.map((item, idx) => (
            <motion.div
              key={item.label}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.8 + idx * 0.1 }}
              className="flex items-center gap-2.5"
            >
              <span className="status-dot" style={{
                background:
                  item.color === "cyan"
                    ? "var(--accent-cyan)"
                    : item.color === "violet"
                    ? "var(--accent-violet)"
                    : "var(--accent-emerald)",
                boxShadow: `0 0 12px ${
                  item.color === "cyan"
                    ? "var(--accent-cyan)"
                    : item.color === "violet"
                    ? "var(--accent-violet)"
                    : "var(--accent-emerald)"
                }`,
              }} />
              <span className="font-mono text-xs text-[var(--text-tertiary)]">
                {item.label.toUpperCase()} —{" "}
                <span className="text-[var(--text-secondary)]">{item.status.toUpperCase()}</span>
              </span>
            </motion.div>
          ))}
        </motion.div>
      </div>

      {/* Floating document panel preview (bottom) */}
      <motion.div
        initial={{ opacity: 0, y: 60 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1, duration: 1 }}
        className="absolute bottom-0 left-1/2 z-5 -translate-x-1/2 translate-y-1/2"
      >
        <div className="glass flex items-center gap-3 rounded-xl px-4 py-3 shadow-2xl">
          <FileSearch className="h-5 w-5 text-cyan-glow" />
          <div className="text-left">
            <div className="font-mono text-xs text-[var(--text-secondary)]">
              QUERY → EMBED → RETRIEVE → RERANK → SYNTHESIZE → CITE
            </div>
          </div>
          <Zap className="h-4 w-4 text-electric-violet" />
        </div>
      </motion.div>
    </section>
  );
}
