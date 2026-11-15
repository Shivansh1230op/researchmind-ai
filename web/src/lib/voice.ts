export type SpeechLocale = "en-IN" | "hi-IN";

export interface RecognitionResult {
  readonly isFinal: boolean;
  readonly length: number;
  readonly [index: number]: { transcript: string };
}

export interface RecognitionEvent {
  readonly results: ArrayLike<RecognitionResult>;
}

export interface BrowserRecognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

export type RecognitionConstructor = new () => BrowserRecognition;

export function recognitionConstructor(): RecognitionConstructor | undefined {
  const browser = window as Window & {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return browser.SpeechRecognition || browser.webkitSpeechRecognition;
}

export function synthesisSupported(): boolean {
  return typeof window.speechSynthesis?.speak === "function"
    && typeof window.SpeechSynthesisUtterance === "function";
}

export function recognitionError(code: string): string {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "Microphone access was denied. Allow it in your browser settings, then try again.";
    case "audio-capture": return "No working microphone was found. Connect one or type your question.";
    case "network": return "The browser's speech service could not connect. Try again or type your question.";
    case "no-speech": return "No speech was detected. Try speaking again or type your question.";
    case "language-not-supported": return "This speech language is unavailable. Try another language or type your question.";
    default: return "Voice input stopped unexpectedly. Your draft is still available to edit.";
  }
}

/** Leave citations and formatting on screen; speak the answer's readable prose. */
export function spokenText(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, " Code sample. ")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/\[\d+(?:\s*[,–-]\s*\d+)*\]/g, "")
    .replace(/<[^>]*>/g, "")
    .replace(/^\s{0,3}(?:#{1,6}\s+|>\s*|[-*+]\s+)/gm, "")
    .replace(/[*_`~|]/g, "")
    .replace(/\s+/g, " ")
    .replace(/\s+([,.!?;:।])/g, "$1")
    .trim();
}

/** Short utterances avoid browser text limits and make stopping responsive. */
export function speechChunks(markdown: string): string[] {
  let remaining = spokenText(markdown);
  const chunks: string[] = [];
  while (remaining.length) {
    if (remaining.length <= 220) {
      chunks.push(remaining);
      break;
    }
    const prefix = remaining.slice(0, 220);
    const sentence = [...prefix.matchAll(/[.!?।](?:\s|$)/g)].at(-1);
    const end = sentence && sentence.index >= 50 ? sentence.index + 1 : prefix.lastIndexOf(" ");
    const boundary = end > 0 ? end : 220;
    chunks.push(remaining.slice(0, boundary).trim());
    remaining = remaining.slice(boundary).trim();
  }
  return chunks;
}
