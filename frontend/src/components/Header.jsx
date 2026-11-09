import React from "react";
import { ShieldCheck, Database, Cpu, Activity, ExternalLink } from "lucide-react";

export function Header({ mode, setMode }) {
  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
            <span className="text-xl">🏦</span>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold tracking-tight text-white">YieldLens AI</h1>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20">
                Grounding Engine
              </span>
            </div>
            <p className="text-xs text-slate-400">Evidence-Grounded US Rates & Fed Commentary</p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {/* Generation Mode Switcher */}
          <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-1 text-xs">
            <button
              onClick={() => setMode("TEMPLATE")}
              className={`px-3 py-1 rounded-md font-medium transition ${
                mode === "TEMPLATE"
                  ? "bg-slate-800 text-sky-400 shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
              title="Deterministic template using validated numbers only. No LLM."
            >
              Template
            </button>
            <button
              onClick={() => setMode("LLM_RAG")}
              className={`px-3 py-1 rounded-md font-medium transition ${
                mode === "LLM_RAG"
                  ? "bg-slate-800 text-purple-400 shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
              title="LLM with retrieved evidence only (no structured facts injected)."
            >
              LLM RAG
            </button>
            <button
              onClick={() => setMode("HYBRID")}
              className={`px-3 py-1 rounded-md font-medium transition ${
                mode === "HYBRID"
                  ? "bg-sky-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
              title="Structured facts + retrieved evidence + claim verification (Production mode)."
            >
              Hybrid (Verified)
            </button>
          </div>

          <a
            href="https://github.com/yash9025/YieldLens-AI"
            target="_blank"
            rel="noreferrer"
            className="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 text-xs border border-slate-800 transition"
          >
            <span>GitHub</span>
            <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
          </a>
        </div>
      </div>
    </header>
  );
}

