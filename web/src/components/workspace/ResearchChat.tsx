"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowUp, Square, Sparkles, FileText, Copy, Download, RotateCcw, Plus, PanelLeft, BookOpen, X, Check } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, apiBase, workspaceHeaders, fetchAPI, DocumentMeta, ChatMessage, SourceCitation } from "@/lib/api";
import DocumentPanel from "./DocumentPanel";
import { useCallback } from "react";

function download(text: string, name: string) { const url = URL.createObjectURL(new Blob([text], {type: "text/markdown"})); const a = document.createElement("a"); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url); }
export default function ResearchChat() {
  const [documents, setDocuments] = useState<DocumentMeta[]>([]); const [selected, setSelected] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]); const [sources, setSources] = useState<SourceCitation[]>([]);
  const [session, setSession] = useState(""); const [mode, setMode] = useState("quick"); const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false); const [stage, setStage] = useState(""); const [error, setError] = useState("");
  const [mobilePanel, setMobilePanel] = useState(""); const [preview, setPreview] = useState<SourceCitation | null>(null);
  const [previewText, setPreviewText] = useState(""); const [copied, setCopied] = useState(-1);
  const controller = useRef<AbortController | null>(null); const bottom = useRef<HTMLDivElement>(null);
  const refresh = useCallback(async () => { try { const data = await api.listDocuments(); setDocuments(data.documents); } catch(e) {setError(String(e));} }, []);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const key = `researchmind-chat-${localStorage.getItem("researchmind-workspace") || "default"}`;
    const id = params.get("session") || (params.has("new") ? null : localStorage.getItem(key)) || crypto.randomUUID();
    setSession(id); localStorage.setItem(key, id);
    const doc = params.get("document"); if (doc) setSelected([doc]);
    api.getHistory(id).then(r => {setMessages(r.messages); setSources(r.messages.filter(m => m.sources?.length).at(-1)?.sources || []);}).catch(e => setError(String(e)));
    return () => controller.current?.abort();
  }, []);
  useEffect(() => {if (messages.length) bottom.current?.scrollIntoView({behavior: "auto"});}, [messages, stage]);
  async function openSource(source: SourceCitation) {
    setPreview(source); setPreviewText("");
    try {const r = await fetchAPI<{text: string}>(`/documents/${source.document_id}/preview`); setPreviewText(r.text || "No text preview available.");} catch(e) {setPreviewText(String(e));}
  }
  async function ask(question: string) {
    if (!question.trim() || busy || !session) return;
    setInput(""); setBusy(true); setError(""); setSources([]); setStage("Connecting to research engine");
    setMessages(m => [...m, {role: "user", content: question, timestamp: new Date().toISOString()}, {role: "assistant", content: "", timestamp: new Date().toISOString()}]);
    controller.current = new AbortController();
    let answer = ""; let finished = false;
    try {
      const response = await fetch(`${apiBase}/chat/stream`, {method: "POST", credentials: "include", headers: {"Content-Type": "application/json", ...workspaceHeaders()}, body: JSON.stringify({question, session_id: session, document_ids: selected.length ? selected : undefined, mode}), signal: controller.current.signal});
      if (!response.ok) {const e = await response.json(); throw new Error(e.detail || "Research request failed");}
      if (!response.body) throw new Error("Streaming is unavailable in this browser.");
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
      while (true) {
        const {done, value} = await reader.read(); if (done) break;
        buffer += decoder.decode(value, {stream: true}).replace(/\r\n/g, "\n");
        let boundary;
        while ((boundary = buffer.indexOf("\n\n")) >= 0) {
          const block = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
          const kind = block.match(/^event: (.+)$/m)?.[1]; const data = block.match(/^data: (.+)$/m)?.[1]; if (!data) continue;
          const payload = JSON.parse(data);
          if (kind === "status") setStage(payload.stage);
          if (kind === "sources") setSources(payload);
          if (kind === "error") throw new Error(payload.message);
          if (kind === "token") { answer += payload.text; setMessages(m => m.map((msg, i) => i === m.length - 1 ? {...msg, content: answer} : msg)); }
          if (kind === "done") {finished = true; setMessages(m => m.map((msg, i) => i === m.length - 1 ? {...msg, content: payload.answer, sources: payload.sources} : msg));}
        }
      }
      if (!finished) throw new Error("The response ended early. Please retry.");
    } catch(e) {
      if (e instanceof Error && e.name === "AbortError") {setStage("Stopped"); setError("Generation stopped. Partial output has not been saved.");}
      else setError(e instanceof Error ? e.message : "Research failed");
    } finally {setBusy(false);}
  }
  return <div className="research-room">
    <aside className={`document-rail ${mobilePanel === "documents" ? "mobile-open" : ""}`}><DocumentPanel documents={documents} selectedDocIds={selected} onToggleSelect={id => setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id])} onRefresh={refresh} /><button className="mobile-close" onClick={() => setMobilePanel("")}>Done</button></aside>
    <section className="chat-workbench"><header className="chat-toolbar"><div><span className="live-dot" /><strong>Research assistant</strong><small>GROUNDED IN YOUR LIBRARY</small></div><div className="flex gap-2"><button className="icon-button mobile-tool" aria-label="Documents" onClick={() => setMobilePanel("documents")}><PanelLeft size={17} /></button><button className="icon-button" title="Export conversation" onClick={() => download(messages.map(m => `## ${m.role}\n\n${m.content}\n\n${(m.sources || []).map((s,i) => `[${i+1}] ${s.document_name}, page ${s.page_number || "N/A"}: ${s.content}`).join("\n")}`).join("\n\n"), "research-conversation.md")}><Download size={16} /></button><a className="icon-button" href="?new=1" title="New conversation"><Plus size={17} /></a><button className="icon-button mobile-tool" aria-label="Sources" onClick={() => setMobilePanel("sources")}><BookOpen size={17} /></button></div></header>
      <div className="chat-scroll">{!messages.length ? <div className="chat-welcome"><div className="ai-orb"><Sparkles size={28} /></div><span className="eyebrow">FROM INFORMATION TO UNDERSTANDING</span><h1>Big questions.<br /><span>Grounded answers.</span></h1><p>Connect the dots across your research.<br />Every answer begins with your sources.</p><div className="suggestion-grid">{["What are the key findings?", "Explain the main methodology", "What limitations are discussed?", "Summarize the research objectives"].map((q,i) => <button key={q} disabled={!documents.some(d => d.status === "ready")} onClick={() => ask(q)}><span>0{i+1}</span>{q}<ArrowUp size={14} /></button>)}</div></div> : messages.map((m,i) => <article key={i} className={`research-message ${m.role}`}><div className="message-byline">{m.role === "user" ? "YOU" : <><Sparkles size={14} /> RESEARCHMIND</>}{m.role === "assistant" && m.content && <button title="Copy answer" onClick={async () => {await navigator.clipboard.writeText(m.content); setCopied(i);}}>{copied === i ? <Check size={14} /> : <Copy size={14} />}</button>}</div><div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown></div>{m.sources && <div className="inline-sources">{m.sources.map((s,j) => <button key={j} onClick={() => openSource(s)}>[{j+1}] {s.document_name}{s.page_number ? ` · p. ${s.page_number}` : ""}</button>)}</div>}</article>)}{busy && <div className="processing-label" role="status"><span className="live-dot" />{stage}</div>}<div ref={bottom} /></div>
      <div className="composer-wrap">{error && <p role="alert" className="error-box">{error}</p>}<form className="research-composer" onSubmit={e => {e.preventDefault(); ask(input);}}><textarea aria-label="Research question" value={input} onChange={e => setInput(e.target.value)} placeholder="Ask a question. Discover a connection." rows={2} maxLength={2000} onKeyDown={e => {if (e.key === "Enter" && !e.shiftKey) {e.preventDefault(); ask(input);}}} /><div className="composer-bottom"><select aria-label="Research mode" value={mode} onChange={e => setMode(e.target.value)}>{[["quick","Quick answer"],["deep","Deep research"],["compare","Compare papers"],["simple","Explain simply"],["critical","Critical analysis"],["summary","Research summary"]].map(([v,l]) => <option key={v} value={v}>{l}</option>)}</select><span>{selected.length || documents.filter(d => d.status === "ready").length} documents in context</span>{busy ? <button type="button" className="send-button" title="Stop generation" onClick={() => controller.current?.abort()}><Square size={15} /></button> : <button className="send-button" title="Send question" disabled={!input.trim() || !documents.some(d => d.status === "ready")}><ArrowUp size={18} /></button>}</div></form><p className="composer-footnote">AI can make mistakes. Follow the sources. <button disabled={busy || !messages.some(m => m.role === "user")} onClick={() => ask(messages.filter(m => m.role === "user").at(-1)?.content || "")}><RotateCcw size={11} /> Regenerate</button></p></div>
    </section><aside className={`source-rail ${mobilePanel === "sources" ? "mobile-open" : ""}`}><header><BookOpen size={16} /><strong>Research context</strong><span>{sources.length}</span></header><div className="source-scroll">{!sources.length ? <div className="source-empty"><div className="source-illustration"><FileText size={34} /></div><h3>Evidence lives here.</h3><p>Retrieved passages appear alongside your answer, so you can see where every insight begins.</p><span className="eyebrow">TRACEABLE BY DESIGN</span></div> : sources.map((s,i) => <button className="source-card" key={i} onClick={() => openSource(s)}><div><span className="source-number">{String(i+1).padStart(2,"0")}</span><small>{s.page_number ? `PAGE ${s.page_number}` : "PASSAGE"}</small></div><h4>{s.document_name}</h4><p>{s.content}</p><span className="source-action">Explore source <ArrowUp size={13} /></span></button>)}</div><button className="mobile-close" onClick={() => setMobilePanel("")}>Done</button></aside>
    {preview && <div className="modal-backdrop" onClick={() => setPreview(null)}><section role="dialog" aria-modal="true" aria-label="Source passage" className="source-dialog" onClick={e => e.stopPropagation()}><header><h3>{preview.document_name}</h3><button className="icon-button" aria-label="Close source" onClick={() => setPreview(null)}><X size={18} /></button></header><p className="eyebrow">PAGE {preview.page_number || "N/A"} · CHUNK {preview.chunk_index}</p><blockquote>{preview.content}</blockquote>{preview.document_name.toLowerCase().endsWith(".pdf") ? <iframe title="Source PDF" src={`${apiBase}/documents/${preview.document_id}/file#page=${preview.page_number || 1}`} /> : <pre>{previewText || "Loading source text…"}</pre>}</section></div>}
  </div>;
}
