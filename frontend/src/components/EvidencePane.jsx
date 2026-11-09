import React from "react";
import { CheckCircle2, AlertTriangle, XCircle, HelpCircle, ExternalLink, Calculator, BookOpen, Scale } from "lucide-react";

export function EvidencePane({ sentence }) {
  if (!sentence) {
    return (
      <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-8 text-center text-slate-500 h-full flex flex-col items-center justify-center">
        <Scale className="w-10 h-10 text-slate-700 mb-3" />
        <h3 className="text-sm font-semibold text-slate-300">Evidence & Verification Inspector</h3>
        <p className="text-xs text-slate-500 max-w-xs mt-1">
          Click any sentence in the brief to view its supporting facts, document passages, and verification audit results.
        </p>
      </div>
    );
  }

  const { text, verdict, issues, evidence, uncertainty } = sentence;
  const facts = evidence?.facts || [];
  const chunks = evidence?.chunks || [];

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-6 h-full overflow-y-auto">
      {/* Pane Header */}
      <div className="border-b border-slate-800 pb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-mono text-slate-400">Claim ID: {sentence.id}</span>
          <span
            className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${
              verdict === "SUPPORTED"
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                : verdict === "PARTIAL"
                ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                : verdict === "UNSUPPORTED"
                ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                : "bg-slate-500/10 text-slate-300 border-slate-500/30"
            }`}
          >
            {verdict}
          </span>
        </div>
        <p className="text-sm font-medium text-slate-100 italic bg-slate-950 p-3 rounded-lg border border-slate-800">
          "{text}"
        </p>
      </div>

      {/* Verification Issues / Audit Report */}
      {issues && issues.length > 0 && (
        <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-500/30 space-y-2">
          <div className="flex items-center space-x-2 text-amber-400 text-xs font-semibold">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>Verification Audit Findings</span>
          </div>
          <ul className="text-xs text-amber-200/90 space-y-1 list-disc list-inside">
            {issues.map((issue, idx) => (
              <li key={idx}>{issue}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Causation Discipline Flag */}
      {uncertainty && (
        <div className="p-3.5 rounded-xl bg-purple-950/20 border border-purple-500/30 space-y-1.5">
          <div className="flex items-center space-x-2 text-purple-400 text-xs font-semibold">
            <Scale className="w-4 h-4 flex-shrink-0" />
            <span>Causal Attribution Qualification</span>
          </div>
          <p className="text-xs text-purple-200/90">{uncertainty}</p>
        </div>
      )}

      {/* Structured Facts Grounding */}
      <div className="space-y-3">
        <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-slate-300">
          <Calculator className="w-4 h-4 text-sky-400" />
          <span>Structured Market Facts ({facts.length})</span>
        </div>

        {facts.length === 0 ? (
          <p className="text-xs text-slate-500 italic bg-slate-950/50 p-3 rounded-lg border border-slate-800">
            No numerical structured facts associated with this sentence.
          </p>
        ) : (
          <div className="space-y-2">
            {facts.map((fact, idx) => (
              <div
                key={idx}
                className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-sky-300">{fact.series}</span>
                  <span className="text-xs font-mono font-bold text-white px-2 py-0.5 rounded bg-slate-800">
                    {fact.value}
                  </span>
                </div>
                <div className="text-[11px] font-mono text-slate-400 bg-slate-900/80 p-2 rounded border border-slate-800/80">
                  {fact.formula}
                </div>
                <div className="flex items-center justify-between pt-1 text-[11px]">
                  <span className="text-slate-500">Source: {fact.source}</span>
                  {fact.url && (
                    <a
                      href={fact.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sky-400 hover:text-sky-300 flex items-center space-x-1"
                    >
                      <span>View on FRED</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Retrieved Fed Document Passages */}
      <div className="space-y-3">
        <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-slate-300">
          <BookOpen className="w-4 h-4 text-indigo-400" />
          <span>Retrieved Document Evidence ({chunks.length})</span>
        </div>

        {chunks.length === 0 ? (
          <p className="text-xs text-slate-500 italic bg-slate-950/50 p-3 rounded-lg border border-slate-800">
            No document passages cited for this claim.
          </p>
        ) : (
          <div className="space-y-2">
            {chunks.map((chunk, idx) => (
              <div
                key={idx}
                className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 space-y-2"
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-indigo-300">{chunk.doc_type}</span>
                  <span className="text-[11px] font-mono text-slate-500">{chunk.pub_datetime}</span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/50 p-2.5 rounded border border-slate-800/60">
                  "{chunk.text}"
                </p>
                <div className="pt-1 text-[11px] flex justify-end">
                  {chunk.source_url && (
                    <a
                      href={chunk.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-indigo-400 hover:text-indigo-300 flex items-center space-x-1"
                    >
                      <span>Federal Reserve Official Release</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

