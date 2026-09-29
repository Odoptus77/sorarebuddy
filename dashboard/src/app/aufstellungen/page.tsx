import type { Metadata } from "next";

import { LineupTable } from "@/components/lineup-table";
import { Card, ErrorState, PageHeader, SourceNote } from "@/components/ui";
import { getLineups } from "@/lib/data";
import { fmtInt, fmtPct } from "@/lib/format";

export const metadata: Metadata = { title: "Aufstellungen · sorarebuddy" };

export default async function Lineups() {
  const res = await getLineups();
  if (!res.ok) {
    return (
      <>
        <PageHeader title="Aufstellungen" />
        <ErrorState what="Aufstellungen" error={res.error} source={res.source} />
      </>
    );
  }
  const d = res.data;
  return (
    <>
      <PageHeader
        title="Aufstellungen"
        subtitle={`GW ${d.fixture.gameWeek} · ${d.cards_used ?? "–"} Karten · erwartet ${fmtInt(d.total_expected)} Punkte`}
      />
      <div className="space-y-4">
        {d.competitions.map((c) =>
          c.teams.map((t, i) => (
            <Card
              key={`${c.label}-${i}`}
              title={
                <>
                  {c.label}
                  {c.teams.length > 1 ? <span className="text-ink-muted"> · Team {i + 1}</span> : null}
                </>
              }
              aside={
                <>
                  EV {fmtInt(t.expected_total)} · Ø Start {fmtPct(t.avg_start)}
                  {c.cap ? ` · Cap ${fmtInt(t.cap_used)}/${c.cap}` : ""}
                  {!t.complete ? " · unvollständig" : ""}
                </>
              }
            >
              <LineupTable team={t} />
            </Card>
          )),
        )}
      </div>
      <SourceNote source={res.source} ageSeconds={res.ageSeconds} />
    </>
  );
}
