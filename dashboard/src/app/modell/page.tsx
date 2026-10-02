import type { Metadata } from "next";

import { Badge, Card, DivergingBars, ErrorState, HBarChart, PageHeader, SourceNote, StatTile } from "@/components/ui";
import { getModel } from "@/lib/data";
import type { ModelData } from "@/lib/types";
import { fmt1, fmtDate, fmtPct, fmtSigned, srcLabel } from "@/lib/format";

export const metadata: Metadata = { title: "Modell · sorarebuddy" };

const GROUP: Record<string, string> = {
  Goalkeeper: "TW",
  Defender: "Abwehr",
  Midfielder: "Mittelfeld",
  Forward: "Sturm",
  club: "Klub",
  national: "Länderspiel",
};
const groupLabel = (k: string) => k.split("|").map((p) => GROUP[p] ?? p).join(" · ");

/** Which parts of the learned calibration are really switched on. */
function calState(cal: ModelData["calibration"]) {
  if (!cal?.active) return "inaktiv";
  if (!cal.by_type) return "aktiv";
  const on: string[] = Object.entries(cal.by_type).filter(([, v]) => v.active).map(([k]) => (k === "national" ? "Länderspiele" : "Klub"));
  if (cal.proj_loo?.active) on.push("Projektion");
  return on.length ? on.join(" + ") : "neutral";
}

export default async function Model() {
  const res = await getModel();
  if (!res.ok) {
    return (
      <>
        <PageHeader title="Modell" />
        <ErrorState what="Modelldaten" error={res.error} source={res.source} />
      </>
    );
  }
  const { evaluation: ev, calibration: cal } = res.data;
  if (!ev) {
    return (
      <>
        <PageHeader title="Modell" subtitle="Treffer-Bilanz und Lernkreislauf" />
        <Card>
          <Badge status="info">noch keine Auswertung</Badge>
          <p className="mt-3 text-sm text-ink-2">
            Sobald Spiele mit geloggter Vorhersage gespielt sind, erzeugt <code>python3 evaluate.py</code>{" "}
            <code>logs/evaluation.json</code> und <code>calibration.json</code>.
          </p>
        </Card>
      </>
    );
  }
  const sources = Object.entries(ev.by_source).sort((a, b) => b[1].n - a[1].n);
  const groups = Object.entries(ev.projection?.groups ?? {}).sort((a, b) => b[1].n - a[1].n);

  return (
    <>
      <PageHeader title="Modell" subtitle={`Treffer-Bilanz · Stand ${fmtDate(ev.updated)}`} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Ausgewertete Spiele" value={ev.evaluated} sub={`${ev.pending} ausstehend · ${ev.upcoming ?? 0} geplant`} />
        <StatTile label="Brier-Score" value={ev.brier != null ? fmt1(ev.brier * 100) : "–"} sub="×100, kleiner = besser" />
        <StatTile label="Reale Startquote" value={fmtPct(ev.start_rate)} />
        <StatTile
          label="Kalibrierung"
          value={calState(cal)}
          sub={cal ? `${cal.n}/${cal.min_n} Spiele · Proj. ×${cal.proj_scale?.value ?? 1}` : "–"}
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card title="Brier je Quelle" aside="kleiner = besser">
          <HBarChart
            caption="Brier-Score je Signalquelle"
            data={sources.map(([k, s]) => ({
              label: `${srcLabel(k)} (${s.n})`,
              value: s.brier,
              display: fmt1(s.brier * 100),
              tip: `vorhergesagt Ø ${fmtPct(s.mean_pred)} · real ${fmtPct(s.actual)}`,
            }))}
          />
        </Card>

        <Card title="Projektion: Fehler je Position × Spieltyp" aside={ev.projection ? `MAE ${fmt1(ev.projection.mae)}` : ""}>
          {groups.length ? (
            <DivergingBars
              caption="Projektions-Bias je Position und Spieltyp"
              posLabel="überschätzt"
              negLabel="unterschätzt"
              data={groups.map(([k, g]) => ({
                label: `${groupLabel(k)} (${g.n})`,
                value: g.bias,
                display: fmtSigned(g.bias),
                tip: `MAE ${fmt1(g.mae)} · gelernter Faktor ×${cal?.proj_scale_groups?.[k]?.value ?? "–"}`,
              }))}
            />
          ) : (
            <p className="text-sm text-ink-2">Noch zu wenige gespielte Spiele.</p>
          )}
        </Card>
      </div>

      {ev.misses?.length ? (
        <Card title="Größte Fehlgriffe" className="mt-4" aside="≥ 70 % und nicht gestartet / ≤ 30 % und gestartet">
          <ul className="space-y-1.5 text-sm">
            {ev.misses.map((m) => (
              <li key={m.player + m.kickoff} className="flex flex-wrap justify-between gap-2">
                <span>
                  {m.player} <span className="text-xs text-ink-muted">{fmtDate(m.kickoff)} · {srcLabel(m.src)}</span>
                </span>
                <span className="tabular text-ink-2">
                  {fmtPct(m.pred)} → {m.started ? "Startelf" : m.played ? "Joker" : "nicht gespielt"}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
      <SourceNote source={res.source} ageSeconds={res.ageSeconds} />
    </>
  );
}
