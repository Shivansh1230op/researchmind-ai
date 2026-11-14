/**
 * Shared TypeScript types for ResearchMind AI frontend.
 */

export type ProcessingStage =
  | "uploading"
  | "extracting"
  | "chunking"
  | "embedding"
  | "indexing"
  | "ready"
  | "error";

export interface NavItem {
  label: string;
  href: string;
  icon: string;
}

export interface FeatureCard {
  icon: string;
  title: string;
  description: string;
}

export interface ArchitectureStep {
  step: number;
  label: string;
  description: string;
  icon: string;
}
