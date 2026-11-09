import React from "react";
import { Database, TrendingUp, TrendingDown, Minus, ExternalLink } from "lucide-react";
import { MOCK_FACTS_SUMMARY } from "../mockData";

export function FactsTable() {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Database className="w-4 h-4 text-sky-400" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
            Validated Market Observations (FRED)
          </h3>
        </div>
        <span className="text-[11px] text-slate-500 font-mono">Tolerance: ±0.5 bps</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 font-mono text-[11px]">
              <th className="py-2.5 px-3">Series</th>
              <th className="py-2.5 px-3 text-right">Yield Level</th>
              <th className="py-2.5 px-3 text-right">Daily Move</th>
              <th className="py-2.5 px-3 text-right">1-Week Move</th>
              <th className="py-2.5 px-3 text-right">YTD Move</th>
              <th className="py-2.5 px-3 text-right">Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {MOCK_FACTS_SUMMARY.map((row, idx) => {
              const isUp = row.daily_change.startsWith("+");
              const isZero = row.daily_change.startsWith("0");
              return (
                <tr key={idx} className="hover:bg-slate-800/40 transition">
                  <td className="py-2.5 px-3 font-sans font-medium text-slate-200">
                    {row.series}
                  </td>
                  <td className="py-2.5 px-3 text-right font-bold text-white">
                    {row.level}
                  </td>
                  <td className={`py-2.5 px-3 text-right font-semibold ${
                    isZero ? "text-slate-400" : isUp ? "text-rose-400" : "text-emerald-400"
                  }`}>
                    {row.daily_change}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-300">
                    {row.weekly_change}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-400">
                    {row.ytd_change}
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <a
                      href={row.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sky-400 hover:text-sky-300 inline-flex items-center space-x-1"
                    >
                      <span>FRED</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

