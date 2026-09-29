import "server-only";

import { readFile } from "node:fs/promises";
import path from "node:path";
import { connection } from "next/server";

import type {
  ClubData,
  Loaded,
  LineupsData,
  ModelData,
  ReviewData,
} from "./types";

// Two data sources, both server-side only (nothing here reaches the browser):
//
// 1. Backend mode: SORAREBUDDY_API_URL (+ SORAREBUDDY_API_TOKEN) point at
//    backend/server.py. The Sorare key stays on that server; the token is the
//    backend's APP_TOKEN and is only ever sent from this Node process.
// 2. Local mode (no API URL): read the JSON files the Python scripts write,
//    from SORAREBUDDY_DATA_DIR (default: the repo root, one level up).
//    Those files hold account data and are gitignored.

const API_URL = process.env.SORAREBUDDY_API_URL?.replace(/\/+$/, "");
const API_TOKEN = process.env.SORAREBUDDY_API_TOKEN;
const SLUG = process.env.SORAREBUDDY_SLUG ?? "nicktd7";
const RARITIES = process.env.SORAREBUDDY_RARITIES ?? "limited";
const DATA_DIR = process.env.SORAREBUDDY_DATA_DIR ?? path.resolve(process.cwd(), "..");
// A cold pipeline run on the backend can take minutes.
const TIMEOUT_MS = Number(process.env.SORAREBUDDY_TIMEOUT_MS ?? 180_000);

async function fromApi<T>(route: string, params: Record<string, string> = {}): Promise<Loaded<T>> {
  const url = new URL(`${API_URL}${route}`);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const source = `Backend ${url.host}${route}`;
  try {
    const res = await fetch(url, {
      headers: API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {},
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!res.ok) {
      const body = await res.text();
      return { ok: false, source, error: `HTTP ${res.status}: ${body.slice(0, 200)}` };
    }
    const age = res.headers.get("X-Cache-Age");
    return { ok: true, source, data: (await res.json()) as T, ageSeconds: age ? Number(age) : null };
  } catch (e) {
    return { ok: false, source, error: e instanceof Error ? e.message : String(e) };
  }
}

async function fromFile<T>(rel: string): Promise<Loaded<T>> {
  const file = path.join(DATA_DIR, rel);
  const source = `Datei ${rel}`;
  try {
    return { ok: true, source, data: JSON.parse(await readFile(file, "utf-8")) as T };
  } catch (e) {
    const code = (e as NodeJS.ErrnoException).code;
    return {
      ok: false,
      source,
      error: code === "ENOENT" ? `${rel} fehlt in ${DATA_DIR}` : e instanceof Error ? e.message : String(e),
    };
  }
}

export const dataMode = API_URL ? "backend" : "local";

export async function getLineups(): Promise<Loaded<LineupsData>> {
  await connection(); // always render with fresh data
  return API_URL
    ? fromApi<LineupsData>("/api/lineups", { slug: SLUG, rarities: RARITIES })
    : fromFile<LineupsData>("lineups.json");
}

export async function getClub(): Promise<Loaded<ClubData>> {
  await connection();
  return API_URL
    ? fromApi<ClubData>("/api/club", { slug: SLUG, rarities: RARITIES })
    : fromFile<ClubData>("club.json");
}

export async function getModel(): Promise<Loaded<ModelData>> {
  await connection();
  if (API_URL) return fromApi<ModelData>("/api/model");
  const [evaluation, calibration] = await Promise.all([
    fromFile<ModelData["evaluation"]>("logs/evaluation.json"),
    fromFile<ModelData["calibration"]>("calibration.json"),
  ]);
  return {
    ok: true,
    source: "Dateien logs/evaluation.json + calibration.json",
    data: {
      evaluation: evaluation.ok ? evaluation.data : null,
      calibration: calibration.ok ? calibration.data : null,
    },
  };
}

export async function getReview(): Promise<Loaded<ReviewData>> {
  await connection();
  return API_URL
    ? fromApi<ReviewData>("/api/review", { slug: SLUG })
    : fromFile<ReviewData>("logs/lineup_review.json");
}
