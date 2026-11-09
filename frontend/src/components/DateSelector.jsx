import React from "react";
import { Calendar, ChevronRight } from "lucide-react";
import { MOCK_DATES } from "../mockData";

export function DateSelector({ selectedDate, setSelectedDate }) {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <Calendar className="w-4 h-4 text-sky-400" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Historical Evaluation Dates
          </h2>
        </div>
        <span className="text-[11px] text-slate-500">Held-Out Curated Corpus</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {MOCK_DATES.map((item) => {
          const isSelected = item.date === selectedDate;
          return (
            <button
              key={item.date}
              onClick={() => setSelectedDate(item.date)}
              className={`text-left p-3 rounded-lg border transition flex items-start justify-between ${
                isSelected
                  ? "bg-sky-950/40 border-sky-500/50 shadow-sm"
                  : "bg-slate-900 border-slate-800/80 hover:border-slate-700"
              }`}
            >
              <div>
                <div className="flex items-center space-x-2">
                  <span className={`text-xs font-mono font-bold ${isSelected ? "text-sky-300" : "text-slate-200"}`}>
                    {item.date}
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                    FOMC
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1 line-clamp-1">{item.event}</p>
              </div>
              <ChevronRight
                className={`w-4 h-4 mt-1 transition ${
                  isSelected ? "text-sky-400 translate-x-0.5" : "text-slate-600"
                }`}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}

