import React from "react";
import { CheckCircle2, AlertTriangle, XCircle, HelpCircle, ArrowUpRight } from "lucide-react";

export function BriefView({ brief, selectedSentenceId, onSelectSentence }) {
  if (!brief) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-8 text-center text-slate-400">
        No brief available for this date and mode.
      </div>
    );
  }

  const getVerdictBadge = (verdict) => {
    switch (verdict) {
      case "SUPPORTED":
        return (
          <span className="inline-flex items-center space-x-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" />
            <span>SUPPORTED</span>
          </span>
        );
      case "PARTIAL":
        return (
          <span className="inline-flex items-center space-x-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertTriangle className="w-3 h-3" />
            <span>PARTIAL</span>
          </span>
        );
      case "UNSUPPORTED":
        return (
          <span className="inline-flex items-center space-x-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <XCircle className="w-3 h-3" />
            <span>UNSUPPORTED</span>
          </span>
        );
      case "UNCERTAIN":
      default:
        return (
          <span className="inline-flex items-center space-x-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-500/10 text-slate-300 border border-slate-500/20">
            <HelpCircle className="w-3 h-3" />
            <span>UNCERTAIN</span>
          </span>
        );
    }
  };

  const marketMoves = brief.sentences.filter((s) => s.section === "market_moves");
  const fedContext = brief.sentences.filter((s) => s.section === "fed_context");
  const uncertainty = brief.sentences.filter((s) => s.section === "uncertainty_flags");

  const renderSection = (title, sentences, description) => {
    if (!sentences || sentences.length === 0) return null;
    return (
      <div className="space-y-3">
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">{title}</h3>
          {description && <p className="text-[11px] text-slate-500">{description}</p>}
        </div>
        <div className="space-y-2">
          {sentences.map((sent) => {
            const isSelected = sent.id === selectedSentenceId;
            return (
              <div
                key={sent.id}
                onClick={() => onSelectSentence(sent)}
                className={`group cursor-pointer p-3.5 rounded-xl border transition-all text-sm leading-relaxed ${
                  isSelected
                    ? "bg-slate-900 border-sky-500 ring-1 ring-sky-500 shadow-md shadow-sky-500/5"
                    : "bg-slate-900/50 border-slate-800/80 hover:border-slate-700 hover:bg-slate-900/90"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-slate-200 group-hover:text-white transition">
                    {sent.text}
                  </p>
                  <div className="flex-shrink-0 flex items-center space-x-2">
                    {getVerdictBadge(sent.verdict)}
                    <ArrowUpRight
                      className={`w-4 h-4 transition ${
                        isSelected ? "text-sky-400 opacity-100" : "text-slate-600 opacity-0 group-hover:opacity-100"
                      }`}
                    />
                  </div>
                </div>

                <div className="mt-2.5 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                  <div className="flex items-center space-x-3">
                    <span>{sent.fact_ids?.length || 0} facts linked</span>
                    <span>•</span>
                    <span>{sent.chunk_ids?.length || 0} chunks cited</span>
                  </div>
                  <span className="text-sky-400/80 text-[10px] font-sans font-medium">Click to inspect evidence</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-6 space-y-6">
      {/* Header & summary */}
      <div className="border-b border-slate-800/80 pb-5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono text-sky-400 font-semibold">{brief.date}</span>
          <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
            Mode: {brief.mode}
          </span>
        </div>
        <h2 className="text-base font-semibold text-white mt-2">Daily Market Briefing</h2>
        <p className="text-xs text-slate-400 mt-1 italic leading-relaxed">
          "{brief.summary}"
        </p>
      </div>

      {/* Sections */}
      {renderSection(
        "1. What Moved — Exact Numerical Changes",
        marketMoves,
        "Calculated deterministically in Python against FRED market observations."
      )}

      {renderSection(
        "2. Federal Reserve Policy Announcements",
        fedContext,
        "Grounding passages retrieved from official FOMC statements and meeting minutes."
      )}

      {renderSection(
        "3. Explicit Uncertainty & Causation Discipline",
        uncertainty,
        "Distinguishes temporal sequence ('rose after') from unestablished causal claims ('caused yields to rise')."
      )}
    </div>
  );
}

