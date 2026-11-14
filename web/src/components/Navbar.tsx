"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Brain, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Sticky navigation bar with glassmorphic blur effect.
 * Becomes more opaque on scroll.
 */
export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const navLinks = [
    { label: "Platform", href: "#platform" },
    { label: "Features", href: "#features" },
    { label: "Architecture", href: "#architecture" },
    { label: "Documentation", href: "#faq" },
  ];

  return (
    <motion.nav
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "fixed top-0 left-0 right-0 z-50 transition-all duration-300",
        scrolled
          ? "glass border-b border-[var(--border-subtle)]"
          : "bg-transparent"
      )}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        {/* Logo */}
        <a href="/" className="flex items-center gap-2.5">
          <div className="relative">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-glow to-electric-violet">
              <Brain className="h-5 w-5 text-white" />
            </div>
            <div className="absolute inset-0 rounded-lg bg-cyan-glow opacity-20 blur-lg" />
          </div>
          <span className="font-display text-lg font-semibold tracking-tight">
            ResearchMind<span className="text-cyan-glow"> AI</span>
          </span>
        </a>

        {/* Center nav links */}
        <div className="hidden items-center gap-8 md:flex">
          {navLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              {link.label}
            </a>
          ))}
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-3">
          <a
            href="/login"
            className="hidden text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] sm:block"
          >
            Sign In
          </a>
          <a
            href="/dashboard"
            className="btn-glow flex items-center gap-1 rounded-lg px-4 py-2 text-sm"
          >
            Launch Workspace
            <ChevronRight className="h-4 w-4" />
          </a>
        </div>
      </div>
    </motion.nav>
  );
}
