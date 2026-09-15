#!/usr/bin/env python3
"""Render a club overview (from club_overview.py JSON) into a standalone HTML dashboard.

Usage:
    python3 build_dashboard.py <club.json> [--out dashboard.html]

The JSON is the file written by `club_overview.py --json`. The dashboard is a
single self-contained HTML file (data embedded) that can be published as an
Artifact or opened in a browser.
"""
import argparse
import datetime
import json
import sys

TEMPLATE = r"""<title>__NICK__ Club Ledger</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800;900&family=Hanken+Grotesk:wght@400;500;600;700&display=swap">
<style>
:root{
  --pitch:#0f1a14; --panel:#f6f7f4; --panel-2:#eceee8; --ink:#141a16; --ink-soft:#5a655d;
  --line:#dfe3db; --accent:#3d5afe;
  --gain:#0b8a4b; --gain-bg:#e5f4ec; --loss:#c62838; --loss-bg:#fbe9eb; --flat:#8a938c;
  --bg:#fbfcfa; --card:#ffffff; --shadow:0 1px 2px rgba(20,26,22,.06),0 8px 24px rgba(20,26,22,.05);
  --limited:#f4b52a; --rare:#e0403f; --super_rare:#2f7be0; --unique:#20242a;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --panel:#161d18; --panel-2:#1c241f; --ink:#eef2ec; --ink-soft:#9aa79f; --line:#28322b;
  --accent:#8b9dff; --gain:#3ad089; --gain-bg:#123123; --loss:#ff6b7a; --loss-bg:#331a1f;
  --bg:#0d130f; --card:#151c17; --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.35);
}}
:root[data-theme="dark"]{
  --panel:#161d18; --panel-2:#1c241f; --ink:#eef2ec; --ink-soft:#9aa79f; --line:#28322b;
  --accent:#8b9dff; --gain:#3ad089; --gain-bg:#123123; --loss:#ff6b7a; --loss-bg:#331a1f;
  --bg:#0d130f; --card:#151c17; --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"Hanken Grotesk",system-ui,sans-serif;line-height:1.5;
  -webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
.wrap{max-width:1180px;margin:0 auto;padding-inline:20px;padding-block:28px 64px}
h1,h2,h3{font-family:"Archivo",system-ui,sans-serif;margin:0;text-wrap:balance}
.num{font-variant-numeric:tabular-nums}
.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-soft);font-weight:600}

/* header */
header.top{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;
  border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:24px}
.badge{display:flex;align-items:center;gap:14px}
.crest{width:52px;height:52px;border-radius:14px;flex:none;
  background:linear-gradient(145deg,var(--pitch),#26402f);color:#fff;
  display:grid;place-items:center;font-family:"Archivo";font-weight:900;font-size:22px;
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.08)}
.badge h1{font-size:26px;font-weight:800;letter-spacing:-.01em}
.badge .sub{color:var(--ink-soft);font-size:13px}
.asof{text-align:right;color:var(--ink-soft);font-size:12.5px}
.theme-btn{border:1px solid var(--line);background:var(--card);color:var(--ink);
  border-radius:9px;padding:7px 11px;font:inherit;font-size:13px;cursor:pointer}

/* KPI row */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:14px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 18px 16px;
  box-shadow:var(--shadow);display:flex;flex-direction:column;gap:6px;min-width:0}
.kpi .label{font-size:12.5px;color:var(--ink-soft);font-weight:600}
.kpi .val{font-family:"Archivo";font-weight:800;font-size:30px;letter-spacing:-.02em;line-height:1.05}
.kpi .val.small{font-size:26px}
.kpi .meta{font-size:12.5px;color:var(--ink-soft)}
.pos{color:var(--gain)} .neg{color:var(--loss)}
.kpi.hero{background:linear-gradient(160deg,var(--pitch),#22392a);color:#eaf3ec;border-color:transparent}
.kpi.hero .label,.kpi.hero .meta{color:#a9c3b3}

/* rarity strip */
.strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0 26px}
.rare-card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 15px;
  box-shadow:var(--shadow);display:flex;flex-direction:column;gap:8px}
.rare-head{display:flex;align-items:center;gap:8px}
.dot{width:10px;height:10px;border-radius:50%}
.rare-head .name{font-weight:700;font-size:13.5px;text-transform:capitalize}
.rare-head .cnt{margin-left:auto;color:var(--ink-soft);font-size:12.5px}
.rare-card .pl{font-family:"Archivo";font-weight:800;font-size:19px}
.bar{height:6px;border-radius:99px;background:var(--panel-2);overflow:hidden}
.bar>span{display:block;height:100%}

/* controls */
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
.controls input[type=search]{flex:1;min-width:180px;border:1px solid var(--line);background:var(--card);
  color:var(--ink);border-radius:10px;padding:9px 12px;font:inherit}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{border:1px solid var(--line);background:var(--card);color:var(--ink-soft);border-radius:99px;
  padding:6px 12px;font:inherit;font-size:12.5px;font-weight:600;cursor:pointer}
.chip[aria-pressed=true]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.toggle{display:flex;align-items:center;gap:7px;color:var(--ink-soft);font-size:13px;cursor:pointer;user-select:none}

/* table */
.tablewrap{background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);
  overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13.5px;min-width:720px}
thead th{position:sticky;top:env(safe-area-inset-top,0px);background:var(--card);z-index:1;
  text-align:right;padding:13px 14px;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;
  color:var(--ink-soft);font-weight:700;border-bottom:1px solid var(--line);cursor:pointer;white-space:nowrap}
thead th.l{text-align:left}
thead th[aria-sort=ascending]::after{content:" ↑";color:var(--accent)}
thead th[aria-sort=descending]::after{content:" ↓";color:var(--accent)}
tbody td{padding:11px 14px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
tbody td.l{text-align:left}
tbody tr:hover{background:var(--panel)}
tbody tr:last-child td{border-bottom:none}
.player{font-weight:600;color:var(--ink);max-width:210px;overflow:hidden;text-overflow:ellipsis}
.rchip{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:700;text-transform:capitalize;
  color:var(--ink-soft)}
.rchip .dot{width:8px;height:8px}
.muted{color:var(--flat)}
.delta-pill{display:inline-block;padding:2px 8px;border-radius:99px;font-weight:700;font-size:12.5px}
.delta-pill.pos{background:var(--gain-bg);color:var(--gain)}
.delta-pill.neg{background:var(--loss-bg);color:var(--loss)}
.foot{color:var(--ink-soft);font-size:12px;margin-top:14px;line-height:1.6}
.count{color:var(--ink-soft);font-size:12.5px;margin:10px 2px 0}
@media (max-width:720px){.kpis{grid-template-columns:repeat(2,1fr)}.badge h1{font-size:22px}}
</style>

<div class="wrap">
  <header class="top">
    <div class="badge">
      <div class="crest" id="crest">N</div>
      <div>
        <div class="eyebrow">Sorare Club Ledger</div>
        <h1 id="nick">Manager</h1>
        <div class="sub"><span id="cardcount"></span> handelbare Karten · Wert geschätzt aus letzten Verkäufen</div>
      </div>
    </div>
    <div>
      <button class="theme-btn" id="themebtn" type="button">Theme</button>
      <div class="asof" id="asof"></div>
    </div>
  </header>

  <section class="kpis" id="kpis"></section>

  <div class="eyebrow" style="margin:26px 2px 0">Nach Seltenheit</div>
  <section class="strip" id="strip"></section>

  <div class="eyebrow" style="margin:6px 2px 10px">Karten</div>
  <div class="controls">
    <input type="search" id="search" placeholder="Spieler suchen…" aria-label="Spieler suchen">
    <div class="chips" id="rarChips"></div>
    <label class="toggle"><input type="checkbox" id="onlyPriced"> nur mit Kaufpreis</label>
  </div>
  <div class="tablewrap">
    <table>
      <thead><tr>
        <th class="l" data-k="player">Spieler</th>
        <th class="l" data-k="rarity">Seltenheit</th>
        <th data-k="season">Season</th>
        <th data-k="purchase_eur">Kaufpreis</th>
        <th data-k="value_eur">Akt. Wert</th>
        <th data-k="delta_eur">Δ €</th>
        <th data-k="delta_pct">Δ %</th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <div class="count" id="count"></div>

  <p class="foot" id="foot"></p>
</div>

<script>
const DATA = __CLUB_DATA__;
const RARITY_COLORS = {limited:"#f4b52a",rare:"#e0403f",super_rare:"#2f7be0",unique:"#20242a"};
const RARITY_LABEL = {limited:"Limited",rare:"Rare",super_rare:"Super Rare",unique:"Unique"};
const rows = DATA.rows;
const eur = n => n==null ? "—" : (n<0?"−":"") + "€" + Math.abs(n).toLocaleString("de-DE",{minimumFractionDigits:2,maximumFractionDigits:2});
const pct = n => n==null ? "—" : (n>0?"+":"") + n.toLocaleString("de-DE",{maximumFractionDigits:1}) + "%";

// ---- totals ----
const priced = rows.filter(r=>r.purchase_eur!=null);
const both = rows.filter(r=>r.delta_eur!=null);
const sum = (a,k)=>a.reduce((s,r)=>s+(r[k]||0),0);
const invested = sum(priced,"purchase_eur");
const valueBoth = sum(both,"value_eur");
const investedBoth = sum(both,"purchase_eur");
const pl = valueBoth - investedBoth;
const plPct = investedBoth ? pl/investedBoth*100 : 0;
const valueAll = sum(rows.filter(r=>r.value_eur!=null),"value_eur");

document.getElementById("nick").textContent = DATA.nickname;
document.getElementById("crest").textContent = (DATA.nickname||"?").slice(0,1).toUpperCase();
document.getElementById("cardcount").textContent = rows.length;
document.getElementById("asof").innerHTML = "Stand: " + DATA.as_of + "<br>" + priced.length + " mit bekanntem Kaufpreis";

const plClass = pl>=0?"pos":"neg";
document.getElementById("kpis").innerHTML = `
  <div class="kpi"><span class="label">Investiert (gekaufte Karten)</span>
    <span class="val num">${eur(invested)}</span><span class="meta">${priced.length} Karten mit Kaufpreis</span></div>
  <div class="kpi"><span class="label">Geschätzter Gesamtwert</span>
    <span class="val num">${eur(valueAll)}</span><span class="meta">alle ${rows.length} Karten bewertet</span></div>
  <div class="kpi hero"><span class="label">Gewinn / Verlust</span>
    <span class="val num ${plClass}">${eur(pl)}</span><span class="meta">auf ${both.length} vergleichbaren Karten</span></div>
  <div class="kpi"><span class="label">Rendite</span>
    <span class="val num ${plClass}">${pct(plPct)}</span><span class="meta">Wert ${eur(valueBoth)} vs. ${eur(investedBoth)}</span></div>`;

// ---- rarity strip ----
const rarities = [...new Set(rows.map(r=>r.rarity))].sort((a,b)=>rows.filter(r=>r.rarity===b).length-rows.filter(r=>r.rarity===a).length);
const strip = document.getElementById("strip");
strip.innerHTML = rarities.map(rar=>{
  const rs = rows.filter(r=>r.rarity===rar);
  const rb = rs.filter(r=>r.delta_eur!=null);
  const rpl = sum(rb,"value_eur")-sum(rb,"purchase_eur");
  const rInv = sum(rb,"purchase_eur");
  const rpct = rInv? rpl/rInv*100 : 0;
  const c = RARITY_COLORS[rar]||"#888";
  const cls = rpl>=0?"pos":"neg";
  const width = Math.min(100, Math.abs(rpct));
  return `<div class="rare-card">
    <div class="rare-head"><span class="dot" style="background:${c}"></span>
      <span class="name">${RARITY_LABEL[rar]||rar}</span><span class="cnt">${rs.length}</span></div>
    <div class="pl num ${cls}">${eur(rpl)}</div>
    <div class="bar"><span style="width:${width}%;background:${rpl>=0?'var(--gain)':'var(--loss)'}"></span></div>
    <div class="meta" style="font-size:12px;color:var(--ink-soft)">${pct(rpct)} · Ø Kauf ${eur(rInv/(rb.length||1))}</div>
  </div>`;
}).join("");

// ---- rarity filter chips ----
const rarChips = document.getElementById("rarChips");
let activeRar = new Set();
rarChips.innerHTML = rarities.map(r=>`<button class="chip" data-r="${r}" aria-pressed="false">${RARITY_LABEL[r]||r}</button>`).join("");
rarChips.querySelectorAll(".chip").forEach(ch=>ch.onclick=()=>{
  const r=ch.dataset.r;
  if(activeRar.has(r)){activeRar.delete(r);ch.setAttribute("aria-pressed","false");}
  else{activeRar.add(r);ch.setAttribute("aria-pressed","true");}
  render();
});

// ---- table ----
let sortKey="delta_eur", sortDir=1; // 1 asc, -1 desc ; default worst first
const tbody=document.getElementById("rows");
const search=document.getElementById("search");
const onlyPriced=document.getElementById("onlyPriced");

function cmp(a,b){
  let x=a[sortKey], y=b[sortKey];
  const an=x==null, bn=y==null;
  if(an&&bn)return 0; if(an)return 1; if(bn)return -1; // nulls last
  if(typeof x==="string")return x.localeCompare(y)*sortDir;
  return (x-y)*sortDir;
}
function render(){
  const q=search.value.trim().toLowerCase();
  let view=rows.filter(r=>{
    if(activeRar.size && !activeRar.has(r.rarity))return false;
    if(onlyPriced.checked && r.purchase_eur==null)return false;
    if(q && !(r.player||"").toLowerCase().includes(q))return false;
    return true;
  });
  view.sort(cmp);
  tbody.innerHTML=view.map(r=>{
    const c=RARITY_COLORS[r.rarity]||"#888";
    const dc=r.delta_eur==null?"":(r.delta_eur>=0?"pos":"neg");
    const dpill=r.delta_eur==null?`<span class="muted">—</span>`:`<span class="delta-pill ${dc}">${eur(r.delta_eur)}</span>`;
    return `<tr>
      <td class="l"><span class="player" title="${(r.player||'').replace(/"/g,'&quot;')}">${r.player||"—"}</span></td>
      <td class="l"><span class="rchip"><span class="dot" style="background:${c}"></span>${RARITY_LABEL[r.rarity]||r.rarity}</span></td>
      <td class="num muted">${r.season??"—"}</td>
      <td class="num">${r.purchase_eur==null?'<span class="muted">—</span>':eur(r.purchase_eur)}</td>
      <td class="num">${eur(r.value_eur)}</td>
      <td class="num">${dpill}</td>
      <td class="num ${dc}">${pct(r.delta_pct)}</td>
    </tr>`;
  }).join("");
  document.getElementById("count").textContent = view.length + " von " + rows.length + " Karten";
}
document.querySelectorAll("thead th").forEach(th=>th.onclick=()=>{
  const k=th.dataset.k;
  if(k===sortKey){sortDir*=-1;}
  else{sortKey=k;sortDir=(k==="player"||k==="rarity")?1:-1;}
  document.querySelectorAll("thead th").forEach(t=>t.removeAttribute("aria-sort"));
  th.setAttribute("aria-sort", sortDir===1?"ascending":"descending");
  render();
});
search.oninput=render; onlyPriced.onchange=render;

document.getElementById("foot").innerHTML =
  "„Kaufpreis" = der vom aktuellen Besitzer gezahlte Preis aus öffentlichen Transferdaten; Karten aus Tausch, Reward oder Shards haben keinen Geldpreis (—). "+
  "„Akt. Wert" = Median der letzten öffentlichen Verkäufe je Spieler + Seltenheit + Season — ein Schätzwert, kein Verkaufsangebot. "+
  "Common-Karten sind ausgenommen. Quelle: Sorare GraphQL API.";

// theme toggle
const tb=document.getElementById("themebtn");
tb.onclick=()=>{const cur=document.documentElement.getAttribute("data-theme");
  const next=cur==="dark"?"light":(cur==="light"?"dark":(matchMedia("(prefers-color-scheme:dark)").matches?"light":"dark"));
  document.documentElement.setAttribute("data-theme",next);};

// default sort indicator
const dth=document.querySelector('thead th[data-k="delta_eur"]');
dth.setAttribute("aria-sort","ascending");
render();
</script>
"""


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path")
    ap.add_argument("--out", default="dashboard.html")
    args = ap.parse_args(argv)
    with open(args.json_path, encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("as_of", datetime.date.today().isoformat())
    html = TEMPLATE.replace("__CLUB_DATA__", json.dumps(data, ensure_ascii=False))
    html = html.replace("__NICK__", data.get("nickname", "Club"))
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"Wrote {args.out} ({len(html):,} bytes, {len(data['rows'])} rows)")


if __name__ == "__main__":
    main(sys.argv[1:])
