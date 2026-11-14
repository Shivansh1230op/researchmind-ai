"use client";

import { motion } from "framer-motion";
import { ArrowRight, Rocket } from "lucide-react";

/**
 * Final call-to-action section.
 * Dramatic gradient background with strong CTA.
 */
export default function CTASection() {
  return (
    <section className="relative overflow-hidden py-32">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-midnight-800/50 to-transparent" />
      <div className="absolute left-1/2 top-1/2 h-[400px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-electric-blue opacity-10 blur-[120px]" />

      <div className="relative mx-auto max-w-3xl px-6 text-center">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7 }}
        >
          <div className="mb-6 inline-flex items-center gap-2 rounded-full glass px-4 py-1.5">
            <Rocket className="h-3.5 w-3.5 text-cyan-glow" />
            <span className="font-mono text-xs text-cyan-glow">READY TO LAUNCH</span>
          </div>

          <h2 className="font-display text-4xl font-bold tracking-tight sm:text-5xl">
            Start your research intelligence{" "}
            <span className="text-gradient">journey.</span>
          </h2>

          <p className="mx-auto mt-4 max-w-xl text-lg text-[var(--text-secondary)]">
            Upload your first document and ask a question. Get a grounded,
            answer connected to retrieved source passages.
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <a
              href="/dashboard"
              className="btn-glow flex items-center gap-2 rounded-xl px-6 py-3 text-base"
            >
              Launch Workspace
              <ArrowRight className="h-4 w-4" />
            </a>
            <a
              href="#architecture"
              className="glass glass-hover rounded-xl px-6 py-3 text-base text-[var(--text-primary)]"
            >
              Explore the workflow
            </a>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
