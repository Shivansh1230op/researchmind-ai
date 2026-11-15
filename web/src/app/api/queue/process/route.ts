import { handleCallback } from "@vercel/queue";

export const maxDuration = 300;
export const preferredRegion = "sin1";

const handleMessage = handleCallback(async (message: { document_id: string }) => {
  const backend = process.env.RESEARCHMIND_BACKEND_URL;
  const secret = process.env.INTERNAL_WORKER_SECRET;
  if (!backend || !secret) throw new Error("Processing service is not configured");
  const response = await fetch(new URL("internal/process-document", backend.endsWith("/") ? backend : backend + "/"), {
    method: "POST", cache: "no-store",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${secret}` },
    body: JSON.stringify(message),
    signal: AbortSignal.timeout(285_000),
  });
  if (!response.ok) throw new Error(`Document processing returned HTTP ${response.status}`);
});

export async function POST(request: Request): Promise<Response> {
  return handleMessage(request);
}
