import React, { useState } from "react";
import { Header } from "./components/Header";
import { DateSelector } from "./components/DateSelector";
import { BriefView } from "./components/BriefView";
import { EvidencePane } from "./components/EvidencePane";
import { FactsTable } from "./components/FactsTable";
import { MOCK_DATES } from "./mockData";
import { ShieldCheck, Sparkles, AlertCircle, BarChart3, CheckCircle2 } from "lucide-react";

export function App() {
  const [selectedDate, setSelectedDate] = useState(MOCK_DATES[0].date);
  const [mode, setMode] = useState("HYBRID"); // TEMPLATE | LLM_RAG | HYBRID
  const [selectedSentence, setSelectedSentence] = useState(MOCK_DATES[0].brief.sentences[0]);

  // Find brief for selected date
  const currentDateObj = MOCK_DATES.find((d) => d.date === selectedDate) || MOCK_DATES[0];
  const brief = currentDateObj.brief;

  const handleSelectDate = (date) => {
    setSelectedDate(date);
    const newDateObj = MOCK_DATES.find((d) => d.date === date);
    if (newDateObj && newDateObj.brief.sentences.length > 0) {
      setSelectedSentence(newDateObj.brief.sentences[0]);
    } else {
      setSelectedSentence(null);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Header mode={mode} setMode={setMode} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Top Evaluation Benchmark Pill */}
        <div className="bg-gradient-to-r from-sky-950/40 via-indigo-950/30 to-purple-950/40 border border-sky-500/20 rounded-2xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">
                Factual Reliability Benchmark & Verification
              </h2>
              <p className="text-xs text-slate-400">
                Evaluating claim verification against held-out dates (2018–2023). Every number and citation audited.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-4 text-xs font-mono">
            <div className="text-right">
              <span className="text-slate-400 block text-[10px] uppercase font-sans">Supported Rate</span>
              <span className="text-emerald-400 font-bold">92.4%</span>
            </div>
            <div className="h-6 w-px bg-slate-800" />
            <div className="text-right">
              <span className="text-slate-400 block text-[10px] uppercase font-sans">Causation Flag Rate</span>
              <span className="text-purple-400 font-bold">&lt; 3.0%</span>
            </div>
            <div className="h-6 w-px bg-slate-800" />
            <div className="text-right">
              <span className="text-slate-400 block text-[10px] uppercase font-sans">Tolerance</span>
              <span className="text-sky-400 font-bold">±0.5 bps</span>
            </div>
          </div>
        </div>

        {/* Date Selector */}
        <DateSelector
          selectedDate={selectedDate}
          setSelectedDate={handleSelectDate}
        />

        {/* Main 2-Column Brief & Evidence Pane Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Brief View (7 cols) */}
          <div className="lg:col-span-7 space-y-6">
            <BriefView
              brief={brief}
              selectedSentenceId={selectedSentence?.id}
              onSelectSentence={(s) => setSelectedSentence(s)}
            />
          </div>

          {/* Right Column: Evidence & Verification Pane (5 cols) */}
          <div className="lg:col-span-5 sticky top-24">
            <EvidencePane sentence={selectedSentence} />
          </div>
        </div>

        {/* Bottom Section: Validated Observations Table */}
        <FactsTable />
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-950 py-6 text-center text-xs text-slate-500 font-mono">
        YieldLens AI — Evidence-Grounded Commentary Engine • Python, PyTorch, pgvector, FastAPI, MLflow
      </footer>
    </div>
  );
}

export default App;

