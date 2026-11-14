import { FileText, Sparkles, ScanLine, Check } from "lucide-react";

/** Decorative research motif. No document data or analytics are represented. */
export default function ResearchConstellation() {
  return <div className="research-constellation" aria-hidden="true">
    <div className="constellation-halo" />
    <svg viewBox="0 0 440 280" className="constellation-map" fill="none">
      <defs><radialGradient id="orbit-tint"><stop stopColor="#839cfc" stopOpacity=".18" /><stop offset="1" stopColor="#839cfc" stopOpacity="0" /></radialGradient><linearGradient id="orbit-line"><stop stopColor="#7998f8" stopOpacity=".15" /><stop offset=".5" stopColor="#a5b8ff" stopOpacity=".7" /><stop offset="1" stopColor="#7998f8" stopOpacity=".15" /></linearGradient></defs>
      <circle cx="220" cy="140" r="135" fill="url(#orbit-tint)" />
      <ellipse cx="220" cy="140" rx="167" ry="87" stroke="url(#orbit-line)" transform="rotate(-24 220 140)" />
      <ellipse cx="220" cy="140" rx="146" ry="68" stroke="#91a9f0" strokeOpacity=".23" transform="rotate(40 220 140)" />
      <circle cx="220" cy="140" r="113" stroke="#8198d3" strokeOpacity=".12" strokeDasharray="3 9" className="constellation-dashed" />
      <path d="M90 91L220 140L351 67M220 140L336 220M220 140L94 216" stroke="#88a8fa" strokeOpacity=".28" strokeDasharray="4 5" />
      {[[79,100],[350,76],[320,226],[109,219],[223,27],[383,149]].map(([cx,cy],i)=><circle key={i} cx={cx} cy={cy} r={i%2?3:4} fill={i%2?"#a8baff":"#7ee0d2"} opacity=".8" />)}
    </svg>
    <div className="constellation-center"><div className="constellation-core"><Sparkles size={33} strokeWidth={1.4} /></div><span>RESEARCHMIND</span></div>
    <div className="constellation-paper"><span className="constellation-file"><FileText size={16} /></span><div><strong>Your source material</strong><small>One connected workspace</small></div><Check size={12} /></div>
    <div className="constellation-insight"><span><ScanLine size={15} /></span><div><strong>Make the connection.</strong><small>Clarity starts with a question.</small></div></div>
    <span className="constellation-twinkle twinkle-one">✦</span><span className="constellation-twinkle twinkle-two">✧</span>
  </div>;
}
