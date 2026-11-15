import { expect, Page, test } from "@playwright/test";

declare global {
  interface Window {
    __voiceTest: {
      starts: number;
      stops: number;
      aborts: number;
      cancellations: number;
      languages: string[];
      spoken: { text: string; lang: string }[];
      emit(texts: string[]): void;
      fail(code: string): void;
      finish(): void;
      lateFinish: (() => void) | null;
    };
  }
}

const paper = { id: "voice-paper", filename: "study.pdf", file_type: "pdf", file_size: 500,
  total_pages: 1, total_chunks: 1, status: "ready", error_message: null,
  created_at: "2026-11-15T10:00:00Z", extra_metadata: {} };
const source = { document_id: paper.id, document_name: paper.filename, page_number: 1,
  chunk_index: 0, content: "The study measured 42 observations.", similarity_score: .95 };
const answer = "The study measured **42 observations** [1].";

function stream(text = answer) {
  return `event: sources\ndata: ${JSON.stringify([source])}\n\nevent: token\ndata: ${JSON.stringify({ text })}\n\nevent: done\ndata: ${JSON.stringify({ answer: text, sources: [source] })}\n\n`;
}

async function mockSpeech(page: Page, input = true, output = true) {
  await page.addInitScript(({ input, output }) => {
    let active: FakeRecognition | null = null;
    let current: FakeUtterance | null = null;
    class FakeRecognition {
      lang = "";
      continuous = false;
      interimResults = false;
      maxAlternatives = 1;
      onstart: (() => void) | null = null;
      onend: (() => void) | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      onresult: ((event: { results: { 0: { transcript: string }; isFinal: boolean }[] }) => void) | null = null;
      start() { active = this; harness.starts++; harness.languages.push(this.lang); this.onstart?.(); }
      stop() { harness.stops++; this.onend?.(); }
      abort() { harness.aborts++; this.onend?.(); }
    }
    class FakeUtterance {
      lang = "";
      onend: (() => void) | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      constructor(public text: string) {}
    }
    const harness: Window["__voiceTest"] = {
      starts: 0, stops: 0, aborts: 0, cancellations: 0, languages: [], spoken: [], lateFinish: null,
      emit(texts) { active?.onresult?.({ results: texts.map(text => ({ 0: { transcript: text }, isFinal: true })) }); },
      fail(code) { active?.onerror?.({ error: code }); },
      finish() { current?.onend?.(); },
    };
    window.__voiceTest = harness;
    Object.defineProperty(window, "SpeechRecognition", { configurable: true, value: input ? FakeRecognition : undefined });
    Object.defineProperty(window, "webkitSpeechRecognition", { configurable: true, value: undefined });
    Object.defineProperty(window, "SpeechSynthesisUtterance", { configurable: true, value: output ? FakeUtterance : undefined });
    Object.defineProperty(window, "speechSynthesis", { configurable: true, value: output ? {
      getVoices: () => [{ lang: "en-IN", name: "English test voice" }, { lang: "hi-IN", name: "Hindi test voice" }],
      speak(message: FakeUtterance) {
        current = message;
        harness.spoken.push({ text: message.text, lang: message.lang });
        harness.lateFinish = () => message.onend?.();
      },
      cancel() { harness.cancellations++; current?.onerror?.({ error: "canceled" }); current = null; },
    } : undefined });
  }, { input, output });
}

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) return route.fulfill({ json: { id: "voice-user", name: "Ada", email: "ada@example.com" } });
    if (path.endsWith("/workspaces")) return route.fulfill({ json: [{ id: "voice-workspace", name: "Research", documents: 1 }] });
    if (path.endsWith("/documents")) return route.fulfill({ json: { documents: [paper], total: 1 } });
    if (path.endsWith("/chat/history")) return route.fulfill({ json: { messages: [], total: 0 } });
    if (path.endsWith("/chat/stream")) return route.fulfill({ contentType: "text/event-stream", body: stream() });
    return route.fulfill({ json: [] });
  });
});

test("Hindi dictation stays editable and sends through the cited chat before speaking", async ({ page }) => {
  await mockSpeech(page);
  let requests = 0;
  let question = "";
  await page.route("**/api/chat/stream", route => {
    requests++;
    question = route.request().postDataJSON().question;
    return route.fulfill({ contentType: "text/event-stream", body: stream() });
  });
  await page.goto("/dashboard/workspace");
  await page.getByRole("combobox", { name: "Voice language" }).selectOption("hi-IN");
  await page.getByRole("button", { name: "Start voice question" }).click();
  await expect(page.getByRole("button", { name: "Spoken replies" })).toHaveAttribute("aria-pressed", "true");
  await page.evaluate(() => window.__voiceTest.emit(["इस अध्ययन में", "कितने अवलोकन हैं?"]));
  const draft = page.getByRole("textbox", { name: "Research question" });
  await expect(draft).toHaveValue("इस अध्ययन में कितने अवलोकन हैं?");
  await expect(page.getByRole("button", { name: "Send question" })).toBeDisabled();
  await page.getByRole("button", { name: "Stop microphone" }).click();
  await draft.fill("इस अध्ययन में कितने अवलोकन मिले?");
  expect(requests).toBe(0);
  expect(await page.evaluate(() => window.__voiceTest.languages)).toEqual(["hi-IN"]);
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByText("42 observations", { exact: true })).toBeVisible();
  expect(question).toBe("इस अध्ययन में कितने अवलोकन मिले?");
  await expect.poll(() => page.evaluate(() => window.__voiceTest.spoken.length)).toBe(1);
  const spoken = await page.evaluate(() => window.__voiceTest.spoken[0]);
  expect(spoken).toEqual({ text: "The study measured 42 observations.", lang: "hi-IN" });
  await expect(page.locator(".inline-sources")).toContainText("study.pdf");
  await page.getByRole("button", { name: "Stop speaking", exact: true }).click();
  await expect(page.getByRole("button", { name: "Read answer aloud" })).toBeVisible();
});

test("denied microphone permissions preserve drafts and allow typed questions", async ({ page }) => {
  await mockSpeech(page);
  await page.goto("/dashboard/workspace");
  const draft = page.getByRole("textbox", { name: "Research question" });
  await draft.fill("My existing draft");
  await page.getByRole("button", { name: "Start voice question" }).click();
  await page.evaluate(() => window.__voiceTest.fail("not-allowed"));
  await expect(page.getByRole("alert").filter({ hasText: "Microphone access was denied" })).toBeVisible();
  await expect(draft).toHaveValue("My existing draft");
  await expect(page.getByRole("button", { name: "Start voice question" })).toBeEnabled();
  await draft.fill("How many observations?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByText("42 observations", { exact: true })).toBeVisible();
});

test("unsupported speech APIs keep the normal text workflow usable", async ({ page }) => {
  await mockSpeech(page, false, false);
  await page.goto("/dashboard/workspace");
  await expect(page.getByRole("button", { name: "Start voice question" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Spoken replies" })).toBeDisabled();
  await expect(page.getByText("Voice input is unavailable in this browser. You can still type.")).toBeVisible();
  await page.getByRole("textbox", { name: "Research question" }).fill("How many observations?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByText("42 observations", { exact: true })).toBeVisible();
});

test("old answers play in short chunks and stop without restarting the queue", async ({ page }) => {
  await mockSpeech(page);
  const longAnswer = "# Results\n\n" + "The study measured 42 observations [1]. ".repeat(18);
  await page.route("**/api/chat/history**", route => route.fulfill({ json: { messages: [
    { role: "assistant", content: longAnswer, sources: [source], timestamp: "2026-11-15T10:00:00Z" },
  ], total: 1 } }));
  await page.goto("/dashboard/workspace");
  await page.getByRole("button", { name: "Read answer aloud" }).click();
  await expect.poll(() => page.evaluate(() => window.__voiceTest.spoken.length)).toBe(1);
  const first = await page.evaluate(() => window.__voiceTest.spoken[0].text);
  expect(first.length).toBeLessThanOrEqual(220);
  expect(first).not.toContain("[1]");
  expect(first).not.toContain("#");
  await page.evaluate(() => window.__voiceTest.finish());
  await expect.poll(() => page.evaluate(() => window.__voiceTest.spoken.length)).toBe(2);
  await page.getByRole("button", { name: "Stop reading answer" }).click();
  await page.evaluate(() => window.__voiceTest.lateFinish?.());
  expect(await page.evaluate(() => window.__voiceTest.spoken.length)).toBe(2);
  await expect(page.getByRole("button", { name: "Read answer aloud" })).toBeVisible();
});

test("muting spoken replies while waiting prevents automatic audio", async ({ page }) => {
  await mockSpeech(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/chat/stream", async route => {
    await gate;
    return route.fulfill({ contentType: "text/event-stream", body: stream() });
  });
  await page.goto("/dashboard/workspace");
  await page.getByRole("button", { name: "Spoken replies" }).click();
  await page.getByRole("textbox", { name: "Research question" }).fill("How many observations?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByRole("button", { name: "Stop generation" })).toBeVisible();
  await page.getByRole("button", { name: "Spoken replies" }).click();
  release();
  await expect(page.getByText("42 observations", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.__voiceTest.spoken)).toEqual([]);
  await page.getByRole("button", { name: "Read answer aloud" }).click();
  await expect.poll(() => page.evaluate(() => window.__voiceTest.spoken.length)).toBe(1);
});

test("failed generations do not automatically speak partial output", async ({ page }) => {
  await mockSpeech(page);
  await page.route("**/api/chat/stream", route => route.fulfill({ contentType: "text/event-stream",
    body: 'event: token\ndata: {"text":"Partial answer"}\n\nevent: error\ndata: {"message":"Provider unavailable"}\n\n' }));
  await page.goto("/dashboard/workspace");
  await page.getByRole("button", { name: "Spoken replies" }).click();
  await page.getByRole("textbox", { name: "Research question" }).fill("How many observations?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Provider unavailable" })).toBeVisible();
  expect(await page.evaluate(() => window.__voiceTest.spoken)).toEqual([]);
});

test("dictation respects the question limit and microphone stops on navigation", async ({ page }) => {
  await mockSpeech(page);
  await page.goto("/dashboard/workspace");
  await page.getByRole("button", { name: "Start voice question" }).click();
  await page.evaluate(() => window.__voiceTest.emit(["a".repeat(2500)]));
  await expect(page.getByRole("textbox", { name: "Research question" })).toHaveValue("a".repeat(2000));
  await expect(page.getByRole("button", { name: "Start voice question" })).toBeDisabled();
  await page.getByRole("textbox", { name: "Research question" }).fill("");
  await page.getByRole("button", { name: "Start voice question" }).click();
  await page.locator('a[href="/dashboard/history"]').first().click();
  await expect(page).toHaveURL(/\/dashboard\/history/);
  expect(await page.evaluate(() => window.__voiceTest.aborts)).toBeGreaterThan(0);
});

test("voice preferences persist and controls fit mobile without autoplay", async ({ page }) => {
  await mockSpeech(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/dashboard/workspace");
  await page.getByRole("combobox", { name: "Voice language" }).selectOption("hi-IN");
  await page.getByRole("button", { name: "Spoken replies" }).click();
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Voice language" })).toHaveValue("hi-IN");
  await expect(page.getByRole("button", { name: "Spoken replies" })).toHaveAttribute("aria-pressed", "true");
  expect(await page.evaluate(() => window.__voiceTest.spoken)).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/voice-mobile.png", fullPage: true });
});
