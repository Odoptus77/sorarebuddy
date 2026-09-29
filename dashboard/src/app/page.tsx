import Link from "next/link";

import { Countdown } from "@/components/countdown";
import { cardFlags } from "@/components/lineup-table";
import { Badge, Card, ErrorState, HBarChart, PageHeader, SourceNote, StatTile } from "@/components/ui";
import { getLineups, getModel } from "@/lib/data";
import { fmt1, fmtDateTime, fmtInt, fmtPct, srcLabel } from "@/lib/format";
import type { LineupCard } from "@/lib/types";

export default async function Overview() {
  const [lineups, model] = await Promise.all([getLineups(), getModel()]);

  if (!lineups.ok) {
    return (
      <>
        <PageHeader title="Übersicht" />
        <ErrorState
          what="Aufstellungen"
          error={lineups.error}
          source={lineups.source}
          hint={
            <>
              Lokal: im Repo <code>python3 lineup_suggest.py nicktd7 --rarities limited --json lineups.json</code>{" "}
              ausführen, oder <code>SORAREBUDDY_API_URL</code> auf das Backend setzen.
            </>
          }
        />
      </>
    );
  }

  const d = lineups.data;
  const teams = d.competitions.flatMap((c) =>
    c.teams.map((t, i) => ({ label: c.teams.length > 1 ? `${c.label} · T${i + 1}` : c.label, team: t })),
  );
  const cards = teams.flatMap((t) => t.team.cards.map((c) => ({ ...c, where: t.label })));
  const alerts = cards
    .map((c) => ({ c, flags: cardFlags(c) }))
    .filter((x) => x.flags.length > 0);
  const lowStart = cards.filter((c) => c.start_prob < 0.5).sort((a, b) => a.start_prob - b.start_prob);
  const captains = cards.filter((c) => c.captain);
  const ev = model.ok ? model.data.evaluation : null;

  return (
    <>
      <PageHeader
        title={`GW ${d.fixture.gameWeek}`}
        subtitle={`${fmtDateTime(d.fixture.start)} bis ${fmtDateTime(d.fixture.end)}${d.international_break ? " · Länderspielpause" : ""}`}
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Deadline in" value={<Countdown to={d.fixture.start} />} sub={fmtDateTime(d.fixture.start)} />
        <StatTile label="Erwartete Punkte" value={fmtInt(d.total_expected)} sub={`projiziert ${fmtInt(d.total_projected)}`} />
        <StatTile label="Teams / Karten" value={`${teams.length} / ${d.cards_used ?? cards.length}`} sub={`${d.competitions.length} Wettbewerbe`} />
        <StatTile
          label="Treffer-Bilanz"
          value={ev?.brier != null ? fmt1(ev.brier * 100) : "–"}
          sub={ev ? `Brier ×100 · ${ev.evaluated} Spiele` : "noch keine Auswertung"}
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-5">
        <Card title="Erwartete Punkte je Team" aside="EV = Projektion × Startquote" className="lg:col-span-3">
          <HBarChart
            caption="Erwartete Punkte je Team"
            data={teams.map((t) => ({
              label: t.label,
              value: t.team.expected_total,
              display: fmtInt(t.team.expected_total),
              tip: `Ø Start ${fmtPct(t.team.avg_start)} · min ${fmtPct(t.team.min_start)} · projiziert ${fmtInt(t.team.projected_total)}`,
            }))}
          />
          <Link href="/aufstellungen" className="mt-4 inline-block text-sm text-accent-ink hover:underline">
            Alle Aufstellungen →
          </Link>
        </Card>

        <Card title="Kapitäne" className="lg:col-span-2">
          <ul className="space-y-2 text-sm">
            {captains.map((c) => (
              <li key={c.slug + c.where} className="flex items-center justify-between gap-3">
                <span>
                  <span className="font-medium">{c.player}</span>
                  <span className="block text-xs text-ink-muted">{c.where}</span>
                </span>
                <span className="tabular text-ink-2">{fmtPct(c.start_prob)}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Vor der Deadline prüfen" aside={`${alerts.length} Spieler`}>
          {alerts.length === 0 ? (
            <Badge status="good">keine Warnungen</Badge>
          ) : (
            <ul className="space-y-2 text-sm">
              {alerts.map(({ c, flags }) => (
                <li key={c.slug + c.where} className="flex flex-wrap items-center justify-between gap-2">
                  <span>
                    <span className="font-medium">{c.player}</span>{" "}
                    <span className="text-xs text-ink-muted">{c.where}</span>
                  </span>
                  <span className="flex flex-wrap gap-1">
                    {flags.map((f) => (
                      <Badge key={f.text} status={f.status} title={f.title}>{f.text}</Badge>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Unsichere Starter (< 50 %)" aside={`${lowStart.length} Karten`}>
          {lowStart.length === 0 ? (
            <Badge status="good">alle ≥ 50 %</Badge>
          ) : (
            <ul className="space-y-2 text-sm">
              {lowStart.map((c: LineupCard & { where: string }) => (
                <li key={c.slug + c.where} className="flex items-center justify-between gap-3">
                  <span>
                    <span className="font-medium">{c.player}</span>{" "}
                    <span className="text-xs text-ink-muted">{c.where} · {srcLabel(c.start_src)}</span>
                  </span>
                  <span className="tabular text-ink-2">{fmtPct(c.start_prob)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <SourceNote source={lineups.source} ageSeconds={lineups.ageSeconds} />
    </>
  );
}
