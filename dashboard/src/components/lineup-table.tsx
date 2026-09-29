import type { LineupCard, LineupTeam } from "@/lib/types";
import { fmt1, fmtDateTime, posShort, srcLabel } from "@/lib/format";

import { Badge, StartMeter } from "./ui";

/** Everything that needs a human look before the deadline. */
export function cardFlags(c: LineupCard) {
  const f: { status: "warning" | "serious" | "critical" | "info"; text: string; title?: string }[] = [];
  if (c.suspended) f.push({ status: "critical", text: "Sperre?", title: "Rote Karte im letzten Spiel" });
  if (c.injured) f.push({ status: "critical", text: "verletzt" });
  if (c.apif) f.push({ status: "serious", text: "API-Football", title: c.apif });
  if (c.intl_duty) f.push({ status: "serious", text: "Nationalteam", title: srcLabel(c.start_src) });
  if (c.status_conflict) f.push({ status: "warning", text: "Status prüfen", title: `Sorare-Status ${c.playing_status ?? "?"}` });
  if (c.override_stale) f.push({ status: "warning", text: "Recherche alt", title: "Override älter als letztes Spiel" });
  return f;
}

export function LineupTable({ team, compact = false }: { team: LineupTeam; compact?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[44rem] table-fixed text-left text-sm">
        <colgroup>
          <col className="w-14" />
          <col className="w-[22%]" />
          <col />
          <col className="w-28" />
          <col className="w-14" />
          <col className="w-14" />
          {!compact ? <col className="w-36" /> : null}
        </colgroup>
        <thead className="text-xs text-ink-muted">
          <tr className="border-b border-line">
            <th className="py-2 pr-2 font-medium">Pos</th>
            <th className="py-2 pr-2 font-medium">Spieler</th>
            <th className="py-2 pr-2 font-medium">Spiel</th>
            <th className="py-2 pr-2 font-medium">Start</th>
            <th className="py-2 pr-2 text-right font-medium">Proj.</th>
            <th className="py-2 pr-2 text-right font-medium">EV</th>
            {!compact ? <th className="py-2 font-medium">Hinweise</th> : null}
          </tr>
        </thead>
        <tbody>
          {team.cards.map((c) => {
            const flags = cardFlags(c);
            return (
              <tr key={c.slug} className="border-b border-line last:border-0 align-middle">
                <td className="py-2 pr-2 text-xs text-ink-muted">{posShort(c.slot)}</td>
                <td className="py-2 pr-2">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium">{c.player}</span>
                    {c.captain ? (
                      <span className="rounded bg-accent px-1.5 text-[10px] font-bold text-white" title="Kapitän">C</span>
                    ) : null}
                  </div>
                  <div className="text-xs text-ink-muted">
                    Karte {c.season}
                    {c.is_classic ? " · Classic" : " · In-Season"}
                  </div>
                </td>
                <td className="py-2 pr-2">
                  <div>
                    {c.team_name} <span className="text-ink-muted">vs</span> {c.opponent}
                  </div>
                  <div className="text-xs text-ink-muted">
                    {fmtDateTime(c.kickoff)}
                    {c.opp_type === "NationalTeam" ? " · Länderspiel" : ""}
                  </div>
                </td>
                <td className="py-2 pr-2">
                  <StartMeter p={c.start_prob} />
                  <div className="text-[11px] text-ink-muted">{srcLabel(c.start_src)}</div>
                </td>
                <td className="tabular py-2 pr-2 text-right">{fmt1(c.proj)}</td>
                <td className="tabular py-2 pr-2 text-right font-medium">{fmt1(c.ev)}</td>
                {!compact ? (
                  <td className="py-2">
                    <div className="flex flex-wrap gap-1">
                      {flags.map((f) => (
                        <Badge key={f.text} status={f.status} title={f.title}>
                          {f.text}
                        </Badge>
                      ))}
                    </div>
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
