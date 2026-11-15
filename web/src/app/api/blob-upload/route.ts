import { handleUpload, type HandleUploadBody } from "@vercel/blob/client";

export async function POST(request: Request): Promise<Response> {
  try {
    const body = await request.json() as HandleUploadBody;
    const result = await handleUpload({
      request, body,
      onBeforeGenerateToken: async (pathname, clientPayload) => {
        const origin = request.headers.get("origin");
        if (!origin || origin !== new URL(request.url).origin) throw new Error("Invalid origin");
        const payload = JSON.parse(clientPayload || "{}");
        const backend = process.env.RESEARCHMIND_BACKEND_URL;
        if (!backend) throw new Error("Backend binding unavailable");
        const response = await fetch(new URL("api/storage/upload-authorizations", backend.endsWith("/") ? backend : backend + "/"), {
          method: "POST", cache: "no-store",
          headers: {
            "Content-Type": "application/json", Origin: origin,
            Cookie: request.headers.get("cookie") || "",
            ...(payload.workspace_id ? { "X-Workspace-Id": payload.workspace_id } : {}),
          },
          body: JSON.stringify({ ticket_id: payload.ticket_id, pathname }),
        });
        if (!response.ok) throw new Error("Upload not authorized");
        const authorization = await response.json();
        return {
          addRandomSuffix: false, allowOverwrite: false,
          maximumSizeInBytes: authorization.maximumSizeInBytes,
          validUntil: Date.now() + 15 * 60 * 1000,
        };
      },
    });
    return Response.json(result);
  } catch {
    return Response.json({ error: "Upload authorization failed. Sign in and select the file again." }, { status: 403 });
  }
}
