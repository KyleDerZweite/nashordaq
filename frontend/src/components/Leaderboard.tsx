import type { LeaderboardEntry } from "../types";
import { formatAmount } from "../utils/format";

interface Props {
  entries: LeaderboardEntry[];
}

export default function Leaderboard({ entries }: Props) {
  return (
    <section className="border-2 border-hex-gold-dim bg-hex-panel">
      <div className="border-b-2 border-hex-gold-dim px-5 py-3">
        <h2 className="font-serif text-xl font-bold text-hex-gold">
          Leaderboard
        </h2>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b-2 border-hex-border text-left">
              <th className="px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                Rank
              </th>
              <th className="px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                Player
              </th>
              <th className="px-4 py-2 text-right font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                Net Worth
              </th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr
                key={e.rank}
                className={`border-b border-hex-border/50 transition-colors hover:bg-hex-bg-alt ${
                  e.rank === 1 ? "bg-hex-gold/5" : ""
                }`}
              >
                <td className="px-4 py-2.5 font-mono text-sm">
                  <span
                    className={`inline-block h-6 w-6 border-2 text-center text-xs leading-5 font-bold ${
                      e.rank === 1
                        ? "border-hex-gold bg-hex-gold text-hex-bg"
                        : e.rank === 2
                          ? "border-hex-bronze text-hex-bronze"
                          : e.rank === 3
                            ? "border-[#CD7F32] text-[#CD7F32]"
                            : "border-hex-border text-hex-border"
                    }`}
                  >
                    {e.rank}
                  </span>
                </td>
                <td className="px-4 py-2.5 font-mono text-sm font-medium text-hex-white">
                  {e.display_name}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-sm font-bold text-hex-gold">
                  {formatAmount(e.total_value)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
