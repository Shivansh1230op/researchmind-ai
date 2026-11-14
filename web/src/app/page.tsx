/**
 * Landing Page — cinematic entry point for ResearchMind AI.
 *
 * Combines all landing page sections:
 * - Navbar (sticky, glassmorphic)
 * - Hero (neural network background, headline, CTAs)
 * - Features (8 capability cards with scroll reveals)
 * - Architecture (RAG pipeline visualization)
 * - CTA (final call to action)
 * - Footer
 */
import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import FeatureSection from "@/components/sections/FeatureSection";
import ArchitectureSection from "@/components/sections/ArchitectureSection";
import CTASection from "@/components/sections/CTASection";
import Footer from "@/components/Footer";
import Image from "next/image";

export default function LandingPage() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* Fixed navigation */}
      <Navbar />

      {/* Hero section */}
      <Hero />

      <section id="platform" className="mx-auto max-w-6xl px-6 pt-20 pb-10">
        <div className="mb-8 text-center"><span className="eyebrow">A CLEAR SPACE FOR COMPLEX THINKING</span><h2 className="mt-4 text-3xl tracking-tight">Your sources. Your questions. A bigger picture.</h2><p className="mt-3 text-sm text-[var(--text-secondary)]">Keep your library, research conversation, and supporting evidence side by side.</p></div>
        <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] shadow-2xl"><Image src="/research-workspace.png" alt="ResearchMind workspace with a document library, research chat, and source context panel" width={1440} height={950} sizes="(max-width: 1152px) 100vw, 1152px" /></div>
      </section>

      {/* Features */}
      <FeatureSection />

      {/* Architecture */}
      <ArchitectureSection />

      {/* Final CTA */}
      <CTASection />

      {/* Footer */}
      <Footer />
    </main>
  );
}
