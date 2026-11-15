"use client";

import { Loader2, Mic, MicOff, Square, Volume2, VolumeX } from "lucide-react";
import { useVoiceAssistant } from "@/hooks/useVoiceAssistant";
import { SpeechLocale } from "@/lib/voice";

type Props = { voice: ReturnType<typeof useVoiceAssistant>; draft: string; busy: boolean };

export default function VoiceControls({ voice, draft, busy }: Props) {
  const microphoneLabel = voice.listening ? "Stop microphone" : "Start voice question";
  const status = voice.inputState === "starting" ? "Waiting for microphone permission…"
    : voice.inputState === "stopping" ? "Finishing your transcript…"
    : voice.listening ? "Listening… Stop the mic, review your question, then send."
    : voice.speakingId !== null ? "Reading the answer aloud."
    : voice.ready && !voice.inputSupported ? "Voice input is unavailable in this browser. You can still type."
    : "Speak in Hindi or English. Review the transcript before sending.";

  return <div className="voice-controls" aria-label="Voice assistant controls">
    <div className="voice-controls-row">
      <button type="button" className={`voice-mic ${voice.listening ? "is-listening" : ""}`}
        aria-label={microphoneLabel} aria-pressed={voice.listening}
        disabled={!voice.ready || !voice.inputSupported || busy || (!voice.listening && draft.length >= 2000)}
        title={voice.listening ? "Stop listening and review your transcript" : "Speak a question and enable spoken replies"}
        onClick={() => voice.listening ? voice.stopListening() : voice.startListening(draft)}>
        {voice.inputState === "starting" || voice.inputState === "stopping" ? <Loader2 size={15} className="animate-spin" /> : voice.listening ? <Square size={14} /> : voice.inputSupported ? <Mic size={15} /> : <MicOff size={15} />}
        <span>{voice.listening ? "Stop mic" : "Voice question"}</span>
      </button>
      <select aria-label="Voice language" value={voice.locale} disabled={voice.listening}
        onChange={event => voice.setLocale(event.target.value as SpeechLocale)}>
        <option value="en-IN">English (India)</option>
        <option value="hi-IN">हिन्दी (भारत)</option>
      </select>
      <button type="button" className={`voice-replies ${voice.autoRead ? "is-enabled" : ""}`}
        aria-label="Spoken replies" aria-pressed={voice.autoRead}
        disabled={!voice.ready || !voice.outputSupported}
        title="Automatically read completed answers aloud"
        onClick={() => voice.setAutoRead(!voice.autoRead)}>
        {voice.autoRead ? <Volume2 size={15} /> : <VolumeX size={15} />}<span>Spoken replies</span>
      </button>
      {voice.speakingId !== null && <button type="button" className="voice-stop" aria-label="Stop speaking" onClick={voice.stopSpeaking}><Square size={13} /> Stop audio</button>}
    </div>
    <p id="research-voice-status" className="voice-status" role="status" aria-live="polite">{status}</p>
    {voice.listening && <p className="voice-privacy">Your browser’s speech service processes microphone audio.</p>}
    {voice.ready && !voice.outputSupported && <p className="voice-status">Spoken replies are unavailable in this browser. Answers remain readable on screen.</p>}
    {voice.error && <p className="error-box" role="alert">{voice.error}</p>}
  </div>;
}
