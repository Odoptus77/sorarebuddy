import type { Metadata } from "next";

import { Badge, Card, ErrorState, HBarChart, PageHeader, SourceNote, StatTile } from "@/components/ui";
import { getReview } from "@/lib/data";
import { fmt1, fmtInt } from "@/lib/format";

export const metadata: Metadata = { title: "GW-Bilanz · sorarebuddy" };

export default async function Review() {
  const res = await getReview();
  if (!res.ok) {
    return (
      <>
        <PageHeader title="GW-Bilanz" />
        <ErrorState
          what="GW-Bilanz"
          error={res.error}
          source={res.source}
          hint={
            <>
              Braucht den Sorare-Login (OAuth). Lokal: <code>python3 lineup_review.py --last 6</code> (schreibt{" "}
              <code>logs/lineup_review.json</code>).
            </>
          }
        />
      </>
    );
  }
  const gws = [...res.data.gameweeks].sort((a, b) => b.gw - a.gw);
  const closed = gws.filter((g) => g.state === "closed");
  const dnps = closed.reduce((s, g) => s + g.dnp.length, 0);
  const capLoss = closed.reduce((s, g) => s + g.captain_loss, 0);
  const rewards = closed.reduce((s, g) => s + g.lineups.reduce((t, l) => t + l.rewards, 0), 0);

  return (
    <>
      <PageHeader
        title="GW-Bilanz"
        subtitle={`Deine echten Aufstellungen und Ergebnisse · Kapitänsbonus geschätzt ×${res.data.captain_multiplier}`}
      />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Abgeschlossene GWs" value={closed.length} />
        <StatTile label="Rewards" value={rewards} sub="in abgeschlossenen GWs" />
        <StatTile label="Ausfälle" value={dnps} sub="aufgestellt, 0 Minuten" />
        <StatTile label="Kapitäns-Verlust" value={`${fmtInt(capLoss)} P.`} sub="vs. rückblickend bester Kapitän" />
      </div>

      <Card title="Ø Punkte je Aufstellung" className="mt-6">
        <HBarChart
          caption="Durchschnittliche Punkte je Aufstellung und Gameweek"
          data={gws
            .filter((g) => g.lineups.length > 0 && g.total > 0)
            .map((g) => ({
              label: `GW ${g.gw}${g.state !== "closed" ? " (läuft)" : ""}`,
              value: g.avg,
              display: fmtInt(g.avg),
              tip: `${g.lineups.length} Aufstellungen · Σ ${fmtInt(g.total)} · ${g.dnp.length} Ausfälle`,
            }))}
        />
      </Card>

      <div className="mt-4 space-y-4">
        {gws.map((g) => (
          <Card
            key={g.slug}
            title={`GW ${g.gw}`}
            aside={
              <span className="flex flex-wrap items-center gap-2">
                {g.state !== "closed" ? <Badge status="info">läuft · vorläufig</Badge> : null}
                {g.lineups.length} Aufstellungen · Σ {fmtInt(g.total)}
              </span>
            }
          >
            {g.total === 0 && g.state !== "closed" ? (
              <p className="mb-3 text-sm text-ink-2">Noch keine Punkte — die Spiele dieser GW laufen noch.</p>
            ) : null}
            {g.dnp.length > 0 ? (
              <p className="mb-3 text-sm text-ink-2">
                <Badge status="serious">{g.dnp.length} Ausfälle</Badge> <span className="ml-1">{g.dnp.join(", ")}</span>
              </p>
            ) : null}
            <div className="overflow-x-auto">
              <table className="w-full min-w-[36rem] text-left text-sm">
                <thead className="text-xs text-ink-muted">
                  <tr className="border-b border-line">
                    <th className="py-2 pr-3 font-medium">Wettbewerb</th>
                    <th className="py-2 pr-3 text-right font-medium">Platz</th>
                    <th className="py-2 pr-3 text-right font-medium">Punkte</th>
                    <th className="py-2 pr-3 font-medium">Reward</th>
                    <th className="py-2 font-medium">Kapitän</th>
                  </tr>
                </thead>
                <tbody>
                  {[...g.lineups].sort((a, b) => b.score - a.score).map((l, i) => (
                    <tr key={i} className="border-b border-line last:border-0">
                      <td className="py-1.5 pr-3">{l.competition}</td>
                      <td className="tabular py-1.5 pr-3 text-right">{l.rank ? fmtInt(l.rank) : "–"}</td>
                      <td className="tabular py-1.5 pr-3 text-right">{fmt1(l.score)}</td>
                      <td className="py-1.5 pr-3">{l.rewards ? <Badge status="good">{l.rewards}×</Badge> : <span className="text-ink-muted">–</span>}</td>
                      <td className="py-1.5 text-ink-2">
                        {l.captain ?? "–"}
                        {l.captain_loss && l.captain_loss > 0.5 ? (
                          <span className="text-xs text-ink-muted"> · besser {l.best_captain} (−{fmtInt(l.captain_loss)})</span>
                        ) : l.captain ? (
                          <span className="text-xs text-good-ink"> ✓</span>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        ))}
      </div>
      <SourceNote source={res.source} ageSeconds={res.ageSeconds} />
    </>
  );
}
