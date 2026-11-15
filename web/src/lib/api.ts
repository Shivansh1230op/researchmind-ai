/**
 * API client for communicating with the ResearchMind AI FastAPI backend.
 *
 * In development, Next.js rewrites /api/* to http://localhost:8000/*
 * (see next.config.ts). In production, set NEXT_PUBLIC_API_URL.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";
export const apiBase = API_BASE;
export function workspaceHeaders(): Record<string, string> {
  const id = typeof window !== "undefined" ? localStorage.getItem("researchmind-workspace") : null;
  return id ? { "X-Workspace-Id": id } : {};
}

// ── Types ──────────────────────────────────────────────────────

export interface DocumentMeta {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  total_pages: number | null;
  total_chunks: number;
  status: string;
  error_message: string | null;
  created_at: string;
  extra_metadata: Record<string, unknown> | null;
  processing_stage?: string | null;
}

export interface SourceCitation {
  document_id: string;
  document_name: string;
  page_number: number | null;
  chunk_index: number;
  content: string;
  similarity_score: number;
}

export interface ChatResponse {
  answer: string;
  sources: SourceCitation[];
  session_id: string;
  question: string;
  confidence: number;
  no_answer_found: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: SourceCitation[] | null;
  timestamp: string | null;
}

export interface HealthStatus {
  status: string;
  version: string;
  database: string;
  vector_store: string;
  embedding_model: string;
  llm_backend: string;
}

// ── API Functions ──────────────────────────────────────────────

export async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...workspaceHeaders(),
      ...options?.headers,
    },
  });

  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/auth/") && typeof window !== "undefined") window.location.assign("/login");
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  return res.json();
}

async function uploadCloudDocument(file: File, onProgress?: (pct: number) => void): Promise<DocumentMeta> {
  const ticket = await fetchAPI<{ id: string; pathname: string }>("/documents/uploads", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: file.name, file_size: file.size }),
  });
  const { upload } = await import("@vercel/blob/client");
  await upload(ticket.pathname, file, {
    access: "private", handleUploadUrl: "/api/blob-upload", multipart: true,
    clientPayload: JSON.stringify({ ticket_id: ticket.id, workspace_id: workspaceHeaders()["X-Workspace-Id"] }),
    onUploadProgress: ({ percentage }) => onProgress?.(Math.round(percentage)),
  });
  return fetchAPI<DocumentMeta>(`/documents/uploads/${ticket.id}/complete`, { method: "POST" });
}

export const api = {
  // ── Health ───────────────────────────────────────────────────
  health: () => fetchAPI<HealthStatus>("/health"),

  // ── Documents ─────────────────────────────────────────────────
  listDocuments: () =>
    fetchAPI<{ documents: DocumentMeta[]; total: number }>("/documents"),

  uploadDocument: (file: File, onProgress?: (pct: number) => void) =>
    process.env.NEXT_PUBLIC_STORAGE_BACKEND === "vercel_blob"
    ? uploadCloudDocument(file, onProgress)
    : new Promise<DocumentMeta>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append("file", file);

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      });

      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          try {
            const err = JSON.parse(xhr.responseText);
            reject(new Error(err.detail || `Upload failed: ${xhr.status}`));
          } catch {
            reject(new Error(`Upload failed: ${xhr.status}`));
          }
        }
      });

      xhr.addEventListener("error", () => reject(new Error("Network error")));
      xhr.open("POST", `${API_BASE}/documents/upload?background=true`);
      xhr.withCredentials = true;
      Object.entries(workspaceHeaders()).forEach(([key, value]) => xhr.setRequestHeader(key, value));
      xhr.send(formData);
    }),

  deleteDocument: (id: string) =>
    fetchAPI<{ success: boolean; message: string; document_id: string }>(
      `/documents/${id}`,
      { method: "DELETE" }
    ),

  // ── Chat ─────────────────────────────────────────────────────
  chat: (question: string, sessionId: string, documentIds?: string[], topK?: number) =>
    fetchAPI<ChatResponse>("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        session_id: sessionId,
        document_ids: documentIds,
        top_k: topK,
      }),
    }),

  getHistory: (sessionId: string) =>
    fetchAPI<{ session_id: string; messages: ChatMessage[]; total: number }>(
      `/chat/history?session_id=${encodeURIComponent(sessionId)}`
    ),

  clearHistory: (sessionId: string) =>
    fetchAPI<{ success: boolean; message: string; session_id: string }>(
      `/chat/clear?session_id=${encodeURIComponent(sessionId)}`,
      { method: "POST" }
    ),

  // ── Summarization ─────────────────────────────────────────────
  summarize: (documentId: string, summaryType: string) =>
    fetchAPI<{
      document_id: string;
      document_name: string;
      summary: string;
      summary_type: string;
      key_points: string[] | null;
      definitions: Record<string, string>[] | null;
    }>("/documents/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_id: documentId, summary_type: summaryType }),
    }),

  // ── Comparison ───────────────────────────────────────────────
  compare: (documentIds: string[], aspect: string) =>
    fetchAPI<{
      comparison: string;
      document_names: string[];
      aspects_covered: string[];
    }>("/documents/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_ids: documentIds, aspect }),
    }),
};
