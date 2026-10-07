const TZ = "Europe/Berlin";

export const fmtInt = (n: number | null | undefined) =>
  n == null ? "–" : Math.round(n).toLocaleString("de-DE");

export const fmt1 = (n: number | null | undefined) =>
  n == null ? "–" : n.toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const fmtPct = (p: number | null | undefined) =>
  p == null ? "–" : `${Math.round(p * 100)} %`;

export const fmtEur = (n: number | null | undefined) =>
  n == null ? "–" : n.toLocaleString("de-DE", { style: "currency", currency: "EUR" });

export const fmtSigned = (n: number | null | undefined, digits = 1) =>
  n == null
    ? "–"
    : `${n > 0 ? "+" : n < 0 ? "−" : "±"}${Math.abs(n).toLocaleString("de-DE", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      })}`;

/** "Fr 02.10., 16:00" in German time. */
export function fmtDateTime(iso: string | null | undefined) {
  if (!iso) return "–";
  const d = new Date(iso);
  const wd = d.toLocaleDateString("de-DE", { weekday: "short", timeZone: TZ }).replace(".", "");
  const day = d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", timeZone: TZ });
  const time = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: TZ });
  return `${wd} ${day}, ${time}`;
}

export function fmtDate(iso: string | null | undefined) {
  if (!iso) return "–";
  return new Date(iso).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", timeZone: TZ });
}

export function fmtAge(seconds: number | null | undefined) {
  if (seconds == null) return null;
  if (seconds < 90) return "gerade eben";
  const m = Math.round(seconds / 60);
  if (m < 90) return `vor ${m} Min.`;
  return `vor ${Math.round(m / 60)} Std.`;
}

const POS: Record<string, string> = {
  Goalkeeper: "TW",
  Defender: "ABW",
  Midfielder: "MF",
  Forward: "ST",
  Extra: "EXTRA",
};
export const posShort = (p: string | undefined) => (p ? POS[p] ?? p : "–");

const SRC: Record<string, string> = {
  model: "Modell",
  researched: "Recherche",
  sorare_odds: "Sorare-%",
  apif_out: "API-Football: fehlt",
  apif_doubtful: "API-Football: fraglich",
  intl_duty_auto: "Länderspiel-Abstellung",
  natl_bench_auto: "Nationalteam-Bank",
  natl_bench_soft: "Nationalteam-Bank",
  sorare_app: "Sorare-App (Nick)",
  sofa_pred_start: "SofaScore: voraussichtl. Startelf",
  sofa_pred_bench: "SofaScore: voraussichtl. Bank",
  sofa_pred_out: "SofaScore: nicht in voraussichtl. XI",
  sofa_conf_start: "SofaScore: Startelf bestätigt",
  sofa_conf_bench: "SofaScore: Bank bestätigt",
  sofa_conf_out: "SofaScore: nicht im Kader",
  suspension_risk: "Sperren-Verdacht",
  callup_out: "Abstellung (manuell)",
};
export const srcLabel = (s: string | undefined) => (s ? SRC[s] ?? s : "Modell");
