"use client";

import { useEffect, useState } from "react";

function parts(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000));
  return { d: Math.floor(s / 86400), h: Math.floor((s % 86400) / 3600), m: Math.floor((s % 3600) / 60) };
}

/** Live countdown to the Classic deadline (the GW lock). */
export function Countdown({ to }: { to: string }) {
  const target = new Date(to).getTime();
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    const tick = () => setNow(Date.now());
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  if (now === null) return <span className="text-ink-muted">…</span>;
  const left = target - now;
  if (left <= 0) return <span>gelockt</span>;
  const { d, h, m } = parts(left);
  // Short enough for a half-width tile on a phone.
  const text = d > 0 ? `${d} T ${h} Std` : h > 0 ? `${h} Std ${m} Min` : `${m} Min`;
  return <span className="tabular whitespace-nowrap">{text}</span>;
}
