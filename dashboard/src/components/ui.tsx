import type { ReactNode } from "react";

import { fmtAge } from "@/lib/format";

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle ? <p className="mt-1 text-sm text-ink-2">{subtitle}</p> : null}
      </div>
      {children}
    </header>
  );
}

export function Card({ title, aside, children, className = "" }: { title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-line bg-surface p-4 sm:p-5 ${className}`}>
      {title ? (
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-base font-semibold">{title}</h2>
          {aside ? <div className="text-xs text-ink-muted">{aside}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

/** Stat tile: one headline number (+ optional context line). */
export function StatTile({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold sm:text-3xl">{value}</div>
      {sub ? <div className="mt-1 text-sm text-ink-2">{sub}</div> : null}
    </div>
  );
}

type Status = "good" | "warning" | "serious" | "critical" | "info";
const STATUS_STYLE: Record<Status, { dot: string; icon: string }> = {
  good: { dot: "bg-good", icon: "✓" },
  warning: { dot: "bg-warning", icon: "!" },
  serious: { dot: "bg-serious", icon: "!" },
  critical: { dot: "bg-critical", icon: "✕" },
  info: { dot: "bg-accent", icon: "i" },
};

/** Status is never color alone: dot + icon + text label. */
export function Badge({ status, children, title }: { status: Status; children: ReactNode; title?: string }) {
  const s = STATUS_STYLE[status];
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-line bg-surface-2 px-2 py-0.5 text-xs text-ink-2"
    >
      <span className={`inline-flex h-3.5 w-3.5 items-center justify-center rounded-full text-[9px] font-bold text-black ${s.dot}`} aria-hidden>
        {s.icon}
      </span>
      {children}
    </span>
  );
}

/** Start probability as a meter: same-hue track, value label beside it. */
export function StartMeter({ p }: { p: number }) {
  const pct = Math.max(0, Math.min(1, p)) * 100;
  return (
    <div className="flex items-center gap-2" aria-label={`Startquote ${Math.round(pct)} Prozent`}>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-accent-soft/60">
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular w-9 text-right text-xs text-ink-2">{Math.round(pct)} %</span>
    </div>
  );
}

export function ErrorState({ what, error, source, hint }: { what: string; error: string; source: string; hint?: ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-5">
      <Badge status="critical">{what} nicht verfügbar</Badge>
      <p className="mt-3 text-sm text-ink-2">
        Quelle: {source} — {error}
      </p>
      {hint ? <div className="mt-3 text-sm text-ink-2">{hint}</div> : null}
    </div>
  );
}

export function SourceNote({ source, ageSeconds }: { source: string; ageSeconds?: number | null }) {
  const age = fmtAge(ageSeconds);
  return (
    <p className="mt-8 text-xs text-ink-muted">
      Datenquelle: {source}
      {age ? ` · berechnet ${age}` : ""}
    </p>
  );
}

export type BarDatum = { label: string; value: number; display: string; tip?: string };

/**
 * Horizontal magnitude bars (one hue). Thin marks, rounded data end, hairline
 * baseline, direct value labels, hover tooltip on the whole row, and a table
 * view for screen readers / exact values.
 */
export function HBarChart({ data, max, caption }: { data: BarDatum[]; max?: number; caption: string }) {
  const top = max ?? Math.max(1e-9, ...data.map((d) => d.value));
  return (
    <figure>
      <div className="space-y-2" role="img" aria-label={caption}>
        {data.map((d) => (
          <div key={d.label} className="viz-row grid grid-cols-[minmax(7rem,12rem)_1fr_auto] items-center gap-3" tabIndex={0}>
            <span className="truncate text-sm text-ink-2" title={d.label}>{d.label}</span>
            <div className="relative h-4 border-l border-axis">
              <div
                className="h-full rounded-r-[4px] bg-accent"
                style={{ width: `${Math.max(0, (d.value / top) * 100)}%` }}
              />
            </div>
            <span className="tabular text-sm text-ink">{d.display}</span>
            {d.tip ? (
              <div className="viz-tip pointer-events-none absolute left-40 top-6 z-10 rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink shadow-md">
                {d.tip}
              </div>
            ) : null}
          </div>
        ))}
      </div>
      <details className="mt-3 text-xs text-ink-muted">
        <summary className="cursor-pointer">Als Tabelle</summary>
        <table className="mt-2 w-full text-left">
          <caption className="sr-only">{caption}</caption>
          <tbody>
            {data.map((d) => (
              <tr key={d.label} className="border-t border-line">
                <th className="py-1 font-normal">{d.label}</th>
                <td className="tabular py-1 text-right">{d.display}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

/**
 * Diverging bars around zero (blue = above, red = below, gray midline), for
 * signed errors such as projection bias. Label says which side means what.
 */
export function DivergingBars({ data, caption, posLabel, negLabel }: { data: BarDatum[]; caption: string; posLabel: string; negLabel: string }) {
  const m = Math.max(1e-9, ...data.map((d) => Math.abs(d.value)));
  return (
    <figure>
      <div className="mb-2 grid grid-cols-[minmax(7rem,12rem)_1fr_auto] gap-3 text-xs text-ink-muted">
        <span />
        <div className="flex justify-between"><span>← {negLabel}</span><span>{posLabel} →</span></div>
        <span />
      </div>
      <div className="space-y-2" role="img" aria-label={caption}>
        {data.map((d) => {
          const w = (Math.abs(d.value) / m) * 50;
          return (
            <div key={d.label} className="viz-row grid grid-cols-[minmax(7rem,12rem)_1fr_auto] items-center gap-3" tabIndex={0}>
              <span className="truncate text-sm text-ink-2">{d.label}</span>
              <div className="relative h-4">
                <div className="absolute inset-y-0 left-1/2 w-px bg-axis" />
                {d.value >= 0 ? (
                  <div className="absolute inset-y-0 left-1/2 rounded-r-[4px] bg-accent" style={{ width: `${w}%` }} />
                ) : (
                  <div className="absolute inset-y-0 rounded-l-[4px] bg-neg" style={{ width: `${w}%`, right: "50%" }} />
                )}
              </div>
              <span className="tabular text-sm">{d.display}</span>
              {d.tip ? (
                <div className="viz-tip pointer-events-none absolute left-40 top-6 z-10 rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink shadow-md">
                  {d.tip}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
      <details className="mt-3 text-xs text-ink-muted">
        <summary className="cursor-pointer">Als Tabelle</summary>
        <table className="mt-2 w-full text-left">
          <caption className="sr-only">{caption}</caption>
          <tbody>
            {data.map((d) => (
              <tr key={d.label} className="border-t border-line">
                <th className="py-1 font-normal">{d.label}</th>
                <td className="tabular py-1 text-right">{d.display}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
