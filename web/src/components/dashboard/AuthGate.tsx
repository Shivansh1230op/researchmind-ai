"use client";
import { useEffect, useState } from "react";
import { fetchAPI } from "@/lib/api";
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { fetchAPI("/auth/me").then(() => setReady(true)).catch(err => {
    if (String(err).includes("sign in")) window.location.assign("/login");
    else setError("Unable to reach your research server. Start the FastAPI backend and reload.");
  }); }, []);
  if (error) return <div className="auth-screen"><p role="alert">{error}</p><button className="primary-button" onClick={() => window.location.reload()}>Retry connection</button><a href="/login">Sign in</a></div>;
  if (!ready) return <div className="auth-screen"><div className="ai-orb" /><p>Opening your research workspace…</p></div>;
  return children;
}
