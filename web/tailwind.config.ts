import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // ── Neural Research Laboratory Theme ────────────────────
        midnight: {
          50: "#e8eaf0",
          100: "#c5c9d9",
          200: "#8a91aa",
          300: "#565d78",
          400: "#2d3450",
          500: "#1a1f3a",
          600: "#121633",
          700: "#0c0f26",
          800: "#080a1d",
          900: "#050614",
          950: "#020310",
        },
        cyan: {
          glow: "#22d3ee",
          dim: "#0e7490",
        },
        electric: {
          blue: "#3b82f6",
          violet: "#8b5cf6",
          purple: "#a855f7",
        },
        emerald: {
          glow: "#10b981",
          dim: "#047857",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        display: ["var(--font-space-grotesk)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "monospace"],
      },
      animation: {
        "fade-in": "fadeIn 0.6s ease-out forwards",
        "fade-up": "fadeUp 0.8s cubic-bezier(0.22, 1, 0.36, 1) forwards",
        "glow-pulse": "glowPulse 3s ease-in-out infinite",
        "float": "float 6s ease-in-out infinite",
        "shimmer": "shimmer 2s linear infinite",
        "spin-slow": "spin 20s linear infinite",
        "gradient-shift": "gradientShift 8s ease infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(30px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        glowPulse: {
          "0%, 100%": { boxShadow: "0 0 20px rgba(34, 211, 238, 0.15)" },
          "50%": { boxShadow: "0 0 40px rgba(34, 211, 238, 0.3)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-20px)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        gradientShift: {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
