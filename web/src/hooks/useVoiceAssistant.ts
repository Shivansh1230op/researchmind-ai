"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BrowserRecognition, recognitionConstructor, recognitionError, speechChunks, SpeechLocale, synthesisSupported } from "@/lib/voice";

type InputState = "idle" | "starting" | "listening" | "stopping";

export function useVoiceAssistant(onTranscript: (text: string) => void) {
  const [inputSupported, setInputSupported] = useState(false);
  const [outputSupported, setOutputSupported] = useState(false);
  const [ready, setReady] = useState(false);
  const [inputState, setInputState] = useState<InputState>("idle");
  const [locale, setLocaleState] = useState<SpeechLocale>("en-IN");
  const [autoRead, setAutoReadState] = useState(false);
  const [speakingId, setSpeakingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const recognition = useRef<BrowserRecognition | null>(null);
  const recognitionTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stopTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const utterance = useRef<SpeechSynthesisUtterance | null>(null);
  const speechVersion = useRef(0);
  const localeRef = useRef<SpeechLocale>("en-IN");
  const autoReadRef = useRef(false);
  const mounted = useRef(false);
  const transcriptRef = useRef(onTranscript);
  transcriptRef.current = onTranscript;

  const clearTimers = useCallback(() => {
    if (recognitionTimer.current) clearTimeout(recognitionTimer.current);
    if (stopTimer.current) clearTimeout(stopTimer.current);
    recognitionTimer.current = stopTimer.current = null;
  }, []);

  const stopSpeaking = useCallback(() => {
    speechVersion.current++;
    if (utterance.current && "speechSynthesis" in window) window.speechSynthesis.cancel();
    utterance.current = null;
    setSpeakingId(null);
  }, []);

  const cancelListening = useCallback(() => {
    const active = recognition.current;
    recognition.current = null;
    clearTimers();
    if (active) {
      active.onend = active.onresult = active.onerror = active.onstart = null;
      try { active.abort(); } catch { /* Already ended. */ }
    }
    setInputState("idle");
  }, [clearTimers]);

  const stopListening = useCallback(() => {
    const active = recognition.current;
    if (!active || stopTimer.current) return;
    setInputState("stopping");
    try {
      active.stop();
      // Preserve final results, but release the UI if a browser misses onend.
      if (recognition.current === active) stopTimer.current = setTimeout(cancelListening, 2500);
    } catch { cancelListening(); }
  }, [cancelListening]);

  const persist = (key: string, value: string) => {
    try { localStorage.setItem(key, value); } catch { /* Preferences are optional. */ }
  };

  const setLocale = (value: SpeechLocale) => {
    cancelListening();
    stopSpeaking();
    localeRef.current = value;
    setLocaleState(value);
    persist("researchmind-voice-language", value);
  };

  const setAutoRead = (enabled: boolean) => {
    autoReadRef.current = enabled;
    setAutoReadState(enabled);
    persist("researchmind-voice-replies", String(enabled));
    if (!enabled) stopSpeaking();
  };

  useEffect(() => {
    mounted.current = true;
    setInputSupported(Boolean(recognitionConstructor()));
    setOutputSupported(synthesisSupported());
    try {
      const saved = localStorage.getItem("researchmind-voice-language");
      const language = saved === "hi-IN" || saved === "en-IN" ? saved : navigator.language.startsWith("hi") ? "hi-IN" : "en-IN";
      localeRef.current = language;
      setLocaleState(language);
      autoReadRef.current = localStorage.getItem("researchmind-voice-replies") === "true";
      setAutoReadState(autoReadRef.current);
    } catch { /* Use defaults when browser storage is unavailable. */ }
    setReady(true);
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") { cancelListening(); stopSpeaking(); }
    };
    const hide = () => { if (document.hidden) cancelListening(); };
    document.addEventListener("keydown", escape);
    document.addEventListener("visibilitychange", hide);
    return () => {
      mounted.current = false;
      document.removeEventListener("keydown", escape);
      document.removeEventListener("visibilitychange", hide);
      clearTimers();
      const active = recognition.current;
      recognition.current = null;
      if (active) {
        active.onend = active.onresult = active.onerror = active.onstart = null;
        try { active.abort(); } catch { /* Already ended. */ }
      }
      speechVersion.current++;
      if (utterance.current && "speechSynthesis" in window) window.speechSynthesis.cancel();
      utterance.current = null;
    };
  }, [clearTimers, cancelListening, stopSpeaking]);

  const startListening = (draft: string) => {
    if (!mounted.current || recognition.current) return;
    const Constructor = recognitionConstructor();
    if (!Constructor) {
      setError("Voice input is unavailable in this browser. You can still type your question.");
      return;
    }
    stopSpeaking();
    setError("");
    const prefix = draft.trimEnd();
    let active: BrowserRecognition;
    try { active = new Constructor(); }
    catch { setError("Could not start voice input. You can still type your question."); return; }
    recognition.current = active;
    active.lang = localeRef.current;
    active.continuous = true;
    active.interimResults = true;
    active.maxAlternatives = 1;
    setInputState("starting");
    active.onstart = () => {
      if (recognition.current !== active) return;
      setInputState("listening");
      // Starting a voice question opts into spoken replies; the toggle can mute them.
      if (synthesisSupported()) setAutoRead(true);
      recognitionTimer.current = setTimeout(stopListening, 90_000);
    };
    active.onresult = event => {
      if (recognition.current !== active) return;
      const words = Array.from(event.results).map(result => result[0]?.transcript || "").join(" ").trim();
      const text = [prefix, words].filter(Boolean).join(" ");
      transcriptRef.current(text.slice(0, 2000));
      if (text.length >= 2000) stopListening();
    };
    active.onerror = event => {
      if (recognition.current !== active) return;
      if (event.error !== "aborted") setError(recognitionError(event.error));
      cancelListening();
    };
    active.onend = () => {
      if (recognition.current !== active) return;
      recognition.current = null;
      clearTimers();
      setInputState("idle");
    };
    try { active.start(); }
    catch {
      cancelListening();
      setError("Could not start the microphone. Check browser permissions or type your question.");
    }
  };

  const speak = useCallback((text: string, id: number) => {
    if (!mounted.current) return;
    if (!synthesisSupported()) {
      setError("Spoken audio is unavailable in this browser. The full answer is available on screen.");
      return;
    }
    cancelListening();
    stopSpeaking();
    setError("");
    const chunks = speechChunks(text);
    if (!chunks.length) return;
    const version = speechVersion.current;
    const language = localeRef.current;
    const voices = window.speechSynthesis.getVoices();
    const voice = voices.find(item => item.lang.toLowerCase() === language.toLowerCase())
      || voices.find(item => item.lang.toLowerCase().startsWith(language.slice(0, 2)));
    setSpeakingId(id);
    const play = (index: number) => {
      if (speechVersion.current !== version) return;
      if (index >= chunks.length) { utterance.current = null; setSpeakingId(null); return; }
      const next = new SpeechSynthesisUtterance(chunks[index]);
      utterance.current = next;
      next.lang = language;
      if (voice) next.voice = voice;
      next.onend = () => play(index + 1);
      next.onerror = event => {
        if (speechVersion.current !== version) return;
        utterance.current = null;
        setSpeakingId(null);
        if (event.error !== "interrupted" && event.error !== "canceled") {
          setError("Audio could not play. Try Read answer aloud, or read the answer on screen.");
        }
      };
      try { window.speechSynthesis.speak(next); }
      catch { stopSpeaking(); setError("Audio could not play. The answer is available on screen."); }
    };
    play(0);
  }, [cancelListening, stopSpeaking]);

  const readReply = (text: string, id: number) => {
    if (autoReadRef.current) speak(text, id);
  };

  return {
    ready, inputSupported, outputSupported, inputState,
    listening: inputState !== "idle", locale, setLocale, autoRead, setAutoRead,
    speakingId, error, startListening, stopListening, cancelListening,
    speak, readReply, stopSpeaking,
  };
}
