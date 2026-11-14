import { test, expect } from "@playwright/test";

const document = { id: "paper-1", filename: "study.md", file_type: "md", file_size: 85,
  total_pages: 1, total_chunks: 1, status: "ready", error_message: null,
  created_at: "2026-11-14T10:00:00Z", extra_metadata: {} };

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) return route.fulfill({ json: { id: "user-1", name: "Ada", email: "ada@example.com" } });
    if (path.endsWith("/workspaces")) return route.fulfill({ json: [{ id: "workspace-1", name: "Research", documents: 1 }] });
    if (path.endsWith("/documents")) return route.fulfill({ json: { documents: [document], total: 1 } });
    if (path.endsWith("/chat/history")) return route.fulfill({ json: { messages: [], total: 0 } });
    return route.fulfill({ json: [] });
  });
});

test("summary modes, length, and passage inspection work", async ({ page }) => {
  let payload: Record<string, unknown> = {};
  await page.route("**/api/research/summarize", async route => {
    payload = route.request().postDataJSON();
    await route.fulfill({ json: { summaries: [{ document_id: "paper-1", document_name: "study.md",
      summary: "The study measured 42 observations.", truncated: false,
      sources: [{ document_id: "paper-1", document_name: "study.md", page_number: 1, chunk_index: 0, content: "We measured 42 observations." }] }] } });
  });
  await page.goto("/dashboard/summarize");
  await page.getByRole("checkbox").check();
  await page.getByRole("combobox", { name: "Summary type" }).selectOption("academic");
  await page.getByRole("combobox", { name: "Summary length" }).selectOption("long");
  await page.getByRole("button", { name: "Generate summaries" }).click();
  await expect(page.getByText("The study measured 42 observations.")).toBeVisible();
  expect(payload).toEqual({ document_ids: ["paper-1"], summary_type: "academic", length: "long" });
  await page.getByText("Inspect source passages (1)").click();
  await page.getByRole("button", { name: /Open source passage/ }).click();
  await expect(page.getByRole("dialog", { name: "Summary source passage" })).toBeVisible();
  await page.getByRole("button", { name: "Close source" }).click();
});

test("conversation rename and delete update persisted history", async ({ page }) => {
  let title = "Original question"; let deleted = false;
  await page.route("**/api/chat/sessions", route => route.fulfill({ json: deleted ? [] : [{ id: "chat-1", title, updated_at: "2026-11-14T10:00:00Z" }] }));
  await page.route("**/api/chat/sessions/chat-1", async route => {
    if (route.request().method() === "PATCH") title = route.request().postDataJSON().title;
    if (route.request().method() === "DELETE") deleted = true;
    await route.fulfill({ json: { id: "chat-1", title, success: true } });
  });
  await page.goto("/dashboard/history");
  await page.getByRole("button", { name: "Rename Original question" }).click();
  await page.getByRole("textbox", { name: "Conversation title" }).fill("Reviewed study");
  await page.getByRole("button", { name: "Save conversation title" }).click();
  await expect(page.getByRole("link", { name: /Reviewed study/ }).first()).toBeVisible();
  expect(title).toBe("Reviewed study");
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Delete Reviewed study" }).click();
  await expect(page.getByText("No conversations yet. Start with a question in the research workspace.")).toBeVisible();
  expect(deleted).toBe(true);
});

test("upload polling displays actual backend stages and unlocks research", async ({ page }) => {
  let phase = "empty";
  await page.route("**/api/documents", route => route.fulfill({ json: { total: phase === "empty" ? 0 : 1,
    documents: phase === "empty" ? [] : [{ ...document, status: phase === "ready" ? "ready" : phase === "queued" ? "queued" : "processing", processing_stage: phase }] } }));
  await page.route("**/api/documents/upload?background=true", async route => {
    expect(route.request().postDataBuffer()?.toString()).toContain("study.md");
    phase = "queued";
    await route.fulfill({ status: 202, json: { ...document, status: "queued" } });
  });
  await page.goto("/dashboard/workspace");
  await page.locator('input[type="file"]').setInputFiles({ name: "study.md", mimeType: "text/markdown", buffer: Buffer.from("# Study\nWe measured 42 observations.") });
  await expect(page.getByRole("status").filter({ hasText: "queued" })).toBeVisible();
  phase = "embedding";
  await expect(page.getByRole("status").filter({ hasText: "embedding" })).toBeVisible({ timeout: 8000 });
  phase = "ready";
  await page.getByRole("textbox", { name: "Research question" }).fill("What did the study find?");
  await expect(page.getByRole("button", { name: "Send question" })).toBeEnabled({ timeout: 8000 });
});

test("report export saves current edits before downloading", async ({ page }) => {
  const operations: string[] = [];
  await page.route("**/api/reports", route => route.fulfill({ json: [{ id: "report-1", title: "Saved report", content: "Original content" }] }));
  await page.route("**/api/reports/report-1", async route => {
    operations.push(`save:${route.request().postDataJSON().content}`);
    await route.fulfill({ json: { success: true } });
  });
  await page.route("**/api/reports/report-1/export?format=md", async route => {
    operations.push("export"); await route.fulfill({ body: "Edited findings", contentType: "text/markdown" });
  });
  await page.goto("/dashboard/reports");
  await page.getByRole("combobox", { name: "Saved report" }).selectOption("report-1");
  await page.getByRole("textbox", { name: "Edit research report" }).fill("Edited findings");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "MD", exact: true }).click();
  await download;
  expect(operations).toEqual(["save:Edited findings", "export"]);
});
