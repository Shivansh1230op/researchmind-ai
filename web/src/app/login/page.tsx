"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Brain, ArrowRight, Loader2, Mail, ShieldCheck, ArrowLeft, Eye, EyeOff, Check } from "lucide-react";
import { fetchAPI } from "@/lib/api";

type Challenge = { challenge_id: string; email: string; expires_in: number; resend_after: number };

export default function LoginPage() {
  const [register, setRegister] = useState(false);
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [code, setCode] = useState("");
  const [cooldown, setCooldown] = useState(0);
  const [expiresAt, setExpiresAt] = useState(0);
  const [expired, setExpired] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!challenge) return;
    const interval = window.setInterval(() => {
      setCooldown(value => Math.max(0, value - 1));
      setExpired(Date.now() >= expiresAt);
    }, 1000);
    return () => window.clearInterval(interval);
  }, [challenge, expiresAt]);

  function received(result: Challenge) {
    setChallenge(result); setCode(""); setPassword(""); setCooldown(result.resend_after);
    setExpiresAt(Date.now() + result.expires_in * 1000); setExpired(false);
  }
  function openWorkspace() {
    localStorage.removeItem("researchmind-workspace"); window.location.assign("/dashboard");
  }
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); setError(""); setNotice(""); setBusy(true);
    try {
      if (challenge) {
        await fetchAPI("/auth/register/verify", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ challenge_id: challenge.challenge_id, code }) });
        openWorkspace();
      } else if (register) {
        received(await fetchAPI<Challenge>("/auth/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, email, password }) }));
      } else {
        await fetchAPI("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
        openWorkspace();
      }
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to continue. Please try again."); }
    finally { setBusy(false); }
  }
  async function resend() {
    if (!challenge || cooldown || busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      received(await fetchAPI<Challenge>("/auth/register/resend", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ challenge_id: challenge.challenge_id }) }));
      setNotice("A fresh code has been sent. Please use the latest email.");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to resend your code."); }
    finally { setBusy(false); }
  }

  return <main className="signup-layout">
    <section className="signup-story"><Link href="/" className="brand"><span className="brand-symbol"><Brain size={23} /></span>ResearchMind<span className="brand-ai">AI</span></Link>
      <div className="signup-story-content"><span className="eyebrow">YOUR NEXT DISCOVERY STARTS HERE</span><h2>A space for<br />your brightest<br /><span>ideas.</span></h2><p>Bring your papers, questions, and curiosity.<br />Build understanding you can trust.</p>
        <div className="signup-benefits">{["Your research, organized in one place", "Answers connected to your sources", "A private workspace, built around you"].map(text => <div key={text}><Check size={14} />{text}</div>)}</div>
      </div><p className="signup-story-footer">Evidence first. Discovery always.</p>
    </section>
    <section className="signup-form-side"><div className="auth-card signup-card">
      {!challenge && <div className="auth-tabs"><button type="button" className={!register ? "selected" : ""} onClick={() => { setRegister(false); setError(""); }}>Sign in</button><button type="button" className={register ? "selected" : ""} onClick={() => { setRegister(true); setError(""); }}>Sign up</button></div>}
      <div className="signup-step-icon">{challenge ? <Mail size={24} /> : <ShieldCheck size={23} />}</div>
      <h1>{challenge ? "Check your inbox." : register ? "Make room for better ideas." : "Welcome back, researcher."}</h1>
      <p>{challenge ? <>We sent a 6-digit verification code to <strong className="verified-address">{challenge.email}</strong></> : register ? "Create your account with a verified email address." : "Your papers, questions, and discoveries. All in one place."}</p>
      {register && <div className="signup-steps"><span className={!challenge ? "current" : "complete"}>1 · Account details</span><i /><span className={challenge ? "current" : ""}>2 · Verify email</span></div>}
      <form onSubmit={submit}>
        {challenge ? <><label>Verification code<input className="otp-input" name="code" aria-label="Verification code" type="text" inputMode="numeric" pattern="[0-9]{6}" autoComplete="one-time-code" autoFocus maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="000000" required disabled={busy} /></label><p className="otp-hint">{expired ? "Your code has expired. Request a new one below." : "Your code is valid for 10 minutes. Check your spam folder too."}</p></> : <>
          {register && <label>Your name<input name="name" value={name} onChange={e => setName(e.target.value)} required maxLength={100} autoComplete="name" placeholder="Full name" disabled={busy} /></label>}
          <label>Email address<input name="email" value={email} onChange={e => setEmail(e.target.value)} type="email" required autoComplete="email" placeholder="you@example.com" disabled={busy} /></label>
          <label>Password<div className="password-field"><input aria-label="Password" name="password" value={password} onChange={e => setPassword(e.target.value)} type={showPassword ? "text" : "password"} minLength={10} maxLength={128} required autoComplete={register ? "new-password" : "current-password"} placeholder={register ? "At least 10 characters" : "Enter your password"} disabled={busy} /><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></div></label>
        </>}
        {error && <p role="alert" aria-label="Signup error" className="error-box">{error}</p>}{notice && <p role="status" className="otp-notice">{notice}</p>}
        <button className="primary-button" disabled={busy || (!!challenge && (code.length !== 6 || expired))}>{busy ? <Loader2 className="animate-spin" size={17} /> : <ArrowRight size={17} />}{busy ? "Please wait…" : challenge ? "Verify email & create account" : register ? "Send verification code" : "Open my workspace"}</button>
      </form>
      {challenge ? <><div className="resend-row"><span>Didn’t receive a code?</span><button onClick={resend} disabled={busy || cooldown > 0}>{cooldown ? `Resend in ${cooldown}s` : "Resend code"}</button></div><button className="text-button inline-flex items-center gap-2" disabled={busy} onClick={() => { setChallenge(null); setCode(""); setError(""); setNotice(""); }}><ArrowLeft size={13} />Use a different email</button></> : <button className="text-button" disabled={busy} onClick={() => { setRegister(!register); setError(""); }}>{register ? "Already have an account? Sign in" : "New to ResearchMind? Create an account"}</button>}
      <div className="signup-security"><ShieldCheck size={13} />{challenge ? "Your account is created only after verification." : "Email verification helps protect your account."}</div>
    </div></section>
  </main>;
}
