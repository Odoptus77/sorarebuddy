"use client";

import { useMemo, useState } from "react";

import { fmtEur, fmtSigned } from "@/lib/format";
import type { ClubRow } from "@/lib/types";

type SortKey = "player" | "season" | "value_eur" | "purchase_eur" | "delta_eur" | "delta_pct";

export function ClubTable({ rows }: { rows: ClubRow[] }) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("value_eur");
  const [desc, setDesc] = useState(true);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const r = needle ? rows.filter((x) => x.player.toLowerCase().includes(needle)) : rows;
    return [...r].sort((a, b) => {
      const va = a[sort] ?? (sort === "player" ? "" : -Infinity);
      const vb = b[sort] ?? (sort === "player" ? "" : -Infinity);
      const c = typeof va === "string" ? va.localeCompare(String(vb), "de") : (va as number) - (vb as number) || 0;
      return desc ? -c : c;
    });
  }, [rows, q, sort, desc]);

  const th = (key: SortKey, label: string, right = false) => (
    <th
      className={`py-2 pr-3 font-medium ${right ? "text-right" : ""}`}
      aria-sort={sort === key ? (desc ? "descending" : "ascending") : "none"}
    >
      <button
        type="button"
        onClick={() => (sort === key ? setDesc(!desc) : (setSort(key), setDesc(key !== "player")))}
        className="hover:text-ink"
      >
        {label}
        {sort === key ? (desc ? " ↓" : " ↑") : ""}
      </button>
    </th>
  );

  return (
    <div>
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Spieler suchen…"
        className="mb-3 w-full max-w-xs rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm outline-none focus:border-accent"
      />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] text-left text-sm">
          <thead className="text-xs text-ink-muted">
            <tr className="border-b border-line">
              {th("player", "Spieler")}
              {th("season", "Saison")}
              {th("purchase_eur", "Kaufpreis", true)}
              {th("value_eur", "Wert", true)}
              {th("delta_eur", "Δ €", true)}
              {th("delta_pct", "Δ %", true)}
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => {
              const up = (r.delta_eur ?? 0) > 0;
              const down = (r.delta_eur ?? 0) < 0;
              return (
                <tr key={r.card_slug} className="border-b border-line last:border-0">
                  <td className="py-1.5 pr-3">{r.player}</td>
                  <td className="tabular py-1.5 pr-3 text-ink-2">{r.season}</td>
                  <td className="tabular py-1.5 pr-3 text-right text-ink-2">{fmtEur(r.purchase_eur)}</td>
                  <td className="tabular py-1.5 pr-3 text-right">{fmtEur(r.value_eur)}</td>
                  <td className={`tabular py-1.5 pr-3 text-right ${up ? "text-good-ink" : down ? "text-critical" : "text-ink-2"}`}>
                    {up ? "▲ " : down ? "▼ " : ""}
                    {fmtSigned(r.delta_eur, 2)}
                  </td>
                  <td className="tabular py-1.5 pr-3 text-right text-ink-2">
                    {r.delta_pct == null ? "–" : `${fmtSigned(r.delta_pct, 0)} %`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-ink-muted">{shown.length} von {rows.length} Karten</p>
    </div>
  );
}
