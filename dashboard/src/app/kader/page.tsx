import type { Metadata } from "next";

import { ClubTable } from "@/components/club-table";
import { Card, ErrorState, PageHeader, SourceNote, StatTile } from "@/components/ui";
import { getClub } from "@/lib/data";
import { fmtEur, fmtSigned } from "@/lib/format";

export const metadata: Metadata = { title: "Kader · sorarebuddy" };

export default async function Club() {
  const res = await getClub();
  if (!res.ok) {
    return (
      <>
        <PageHeader title="Kader" />
        <ErrorState
          what="Kader"
          error={res.error}
          source={res.source}
          hint={<>Lokal: <code>python3 club_overview.py nicktd7 --rarities limited --json club.json</code></>}
        />
      </>
    );
  }
  const rows = res.data.rows;
  const value = rows.reduce((s, r) => s + (r.value_eur ?? 0), 0);
  const withBuy = rows.filter((r) => r.purchase_eur != null && r.value_eur != null);
  const paid = withBuy.reduce((s, r) => s + (r.purchase_eur ?? 0), 0);
  const worth = withBuy.reduce((s, r) => s + (r.value_eur ?? 0), 0);

  return (
    <>
      <PageHeader title="Kader" subtitle={`${res.data.nickname} · ${rows.length} Karten`} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        <StatTile label="Geschätzter Kaderwert" value={fmtEur(value)} sub="Summe der Marktwert-Schätzungen" />
        <StatTile
          label="Gewinn/Verlust"
          value={fmtSigned(worth - paid, 0) + " €"}
          sub={`${withBuy.length} Karten mit Kaufpreis (${fmtEur(paid)} bezahlt)`}
        />
        <StatTile label="Karten" value={rows.length} />
      </div>
      <Card title="Alle Karten" className="mt-6" aside="Wert = Schätzung aus letzten Verkäufen">
        <ClubTable rows={rows} />
      </Card>
      <SourceNote source={res.source} ageSeconds={res.ageSeconds} />
    </>
  );
}
