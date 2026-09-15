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
/* rewards by player */
.rewardnote{color:var(--ink-soft);font-size:12.5px;margin:0 2px 12px;line-height:1.6}
.rewardgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
.rrow{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:11px 13px;
  box-shadow:var(--shadow);display:grid;grid-template-columns:1fr auto;gap:2px 10px;align-items:baseline}
.rrow .rp{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rrow .rv{font-family:"Archivo";font-weight:800;color:var(--gain)}
.rrow .rm{font-size:11.5px;color:var(--ink-soft)}
.rrow .rbar{grid-column:1/-1;height:5px;border-radius:99px;background:var(--panel-2);overflow:hidden;margin-top:6px}
.rrow .rbar>span{display:block;height:100%;background:var(--gain)}
.rankn{font-size:11.5px;color:var(--ink-soft);font-variant-numeric:tabular-nums;margin-right:6px}
tr.clickable{cursor:pointer}
.trophy{margin-left:6px;font-size:11px;opacity:.85}
/* tabs */
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin-bottom:24px}
.tab{border:none;background:transparent;color:var(--ink-soft);font:inherit;font-weight:600;
  padding:10px 15px;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px}
.tab[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--accent)}
.tab:hover{color:var(--ink)}
/* suggestions */
.sugg-note{color:var(--ink-soft);font-size:12.5px;line-height:1.6;margin:0 2px 22px}
.hswrap{display:flex;flex-wrap:wrap;gap:8px;margin:0 2px 20px}
.hschip{font-size:12px;border:1px solid var(--line);border-radius:10px;padding:7px 11px;background:var(--card);line-height:1.4}
.hschip b{font-variant-numeric:tabular-nums}
.hschip.ok{border-color:var(--gain);color:var(--gain)}
.hschip.ok b{color:var(--gain)}
.hschip.no{color:var(--ink-soft)}
.rar-block{margin-bottom:30px}
.lineups2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.lucard{background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);overflow:hidden}
.lucard .h{display:flex;justify-content:space-between;align-items:baseline;gap:10px;
  padding:14px 16px;border-bottom:1px solid var(--line);background:var(--panel)}
.lucard .h .t{font-family:"Archivo";font-weight:800;font-size:15px}
.lucard .h .tot{font-family:"Archivo";font-weight:800;color:var(--accent);font-size:15px;white-space:nowrap}
.prow{display:grid;grid-template-columns:auto 1fr auto;gap:2px 12px;align-items:center;padding:11px 16px;border-bottom:1px solid var(--line)}
.prow:last-child{border-bottom:none}
.slotchip{grid-row:span 2;align-self:center;font-size:10px;font-weight:700;letter-spacing:.03em;
  text-transform:uppercase;color:var(--ink-soft);background:var(--panel-2);border-radius:7px;padding:6px 6px;min-width:44px;text-align:center}
.prow .pn{font-weight:600}
.prow .pp{font-family:"Archivo";font-weight:800;font-variant-numeric:tabular-nums;text-align:right;grid-row:span 2;align-self:center;font-size:17px}
.prow .pm{grid-column:2/3;font-size:11.5px;color:var(--ink-soft)}
.pchip{display:inline-block;font-size:9.5px;font-weight:800;letter-spacing:.02em;color:#fff;
  border-radius:6px;padding:1px 5px;margin-left:6px;vertical-align:middle;font-variant-numeric:tabular-nums}
.pchip.hi{background:var(--gain)} .pchip.mid{background:#c98a00} .pchip.lo{background:var(--loss)}
.prow .pp .ev{display:block;font-size:10.5px;font-weight:700;color:var(--ink-soft);letter-spacing:0}
.mins{font-variant-numeric:tabular-nums}
.mins b{color:var(--gain)} .mins .s{color:#c98a00} .mins .x{color:var(--loss)}
.safe{font-size:11.5px;color:var(--ink-soft);white-space:nowrap}
.safe b{font-variant-numeric:tabular-nums}
.safe .hi{color:var(--gain)} .safe .mid{color:#c98a00} .safe .lo{color:var(--loss)}
.capbadge{display:inline-block;background:var(--accent);color:#fff;font-size:9.5px;font-weight:800;
  border-radius:5px;padding:1px 5px;margin-left:6px;vertical-align:middle}
.capline{padding:9px 16px;font-size:12px;color:var(--ink-soft);border-bottom:1px solid var(--line);background:var(--panel)}
.capline b{color:var(--ink);font-variant-numeric:tabular-nums}
.lu-warn{padding:9px 16px;font-size:12px;color:var(--loss);background:var(--loss-bg);border-bottom:1px solid var(--line)}
.comp-block{margin-bottom:24px}
.comp-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:0 2px 10px}
.comp-title{font-family:"Archivo";font-weight:800;font-size:16px}
.fmt-badge{font-size:11px;font-weight:700;letter-spacing:.03em;color:var(--accent);
  background:var(--panel-2);border-radius:6px;padding:3px 8px}
.teams-note{font-size:12px;color:var(--ink-soft)}
/* modal */
.modal-back{position:fixed;inset:0;background:rgba(8,12,10,.55);display:none;
  align-items:flex-start;justify-content:center;padding:6vh 16px;z-index:60;overflow-y:auto}
.modal-back.open{display:flex}
.modal{position:relative;background:var(--card);color:var(--ink);border:1px solid var(--line);
  border-radius:16px;max-width:660px;width:100%;box-shadow:var(--shadow);padding:22px 22px 24px}
.modal h3{font-family:"Archivo";font-size:21px;letter-spacing:-.01em;padding-right:32px}
.modal .msub{color:var(--ink-soft);font-size:13px;margin:4px 0 8px}
.mclose{position:absolute;top:12px;right:14px;border:none;background:transparent;color:var(--ink-soft);
  font-size:26px;line-height:1;cursor:pointer;padding:2px 6px;border-radius:8px}
.mclose:hover{background:var(--panel-2);color:var(--ink)}
.lu{border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-top:12px;background:var(--panel)}
.lu .luhead{display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap}
.lu .comp{font-weight:700}
.lu .gw{color:var(--ink-soft);font-size:12px}
.lu .rv{font-family:"Archivo";font-weight:800;color:var(--gain);white-space:nowrap}
.lu .rvs{font-size:11.5px;color:var(--ink-soft);font-weight:500}
.lu .players{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.lu .pchip{font-size:12px;background:var(--card);border:1px solid var(--line);border-radius:99px;padding:3px 10px}
.lu .pchip.me{background:var(--accent);color:#fff;border-color:transparent;font-weight:600}
.lu .pchip .ps{margin-left:7px;opacity:.7;font-variant-numeric:tabular-nums;font-weight:600}
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

  <nav class="tabs" id="tabs" role="tablist">
    <button class="tab" id="tab-overview" role="tab" aria-selected="true" data-view="overview">Übersicht</button>
    <button class="tab" id="tab-suggest" role="tab" aria-selected="false" data-view="suggest" hidden>Vorschläge</button>
  </nav>

  <div id="view-overview">
  <section class="kpis" id="kpis"></section>

  <div class="eyebrow" style="margin:26px 2px 0">Nach Seltenheit</div>
  <section class="strip" id="strip"></section>

  <section id="rewardsSection" hidden>
    <div class="eyebrow" style="margin:26px 2px 8px">Rewards nach Spieler</div>
    <p class="rewardnote" id="rewardnote"></p>
    <div class="rewardgrid" id="rewardgrid"></div>
  </section>

  <div class="eyebrow" style="margin:26px 2px 10px">Karten</div>
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
        <th data-k="reward_eur">Reward</th>
        <th data-k="value_eur">Akt. Wert</th>
        <th data-k="realized_net">Reward − Kauf</th>
        <th data-k="sale_now">Verkauf jetzt</th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <div class="count" id="count"></div>

  <p class="foot" id="foot"></p>
  </div><!-- /view-overview -->

  <div id="view-suggest" hidden></div>
</div>

<div class="modal-back" id="modalBack" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
  <div class="modal" role="document">
    <button class="mclose" id="modalClose" type="button" aria-label="Schließen">×</button>
    <h3 id="modalTitle"></h3>
    <div class="msub" id="modalSub"></div>
    <div id="modalBody"></div>
  </div>
</div>

<script>
const DATA = __CLUB_DATA__;
const REWARDS = __REWARDS_DATA__;
const LINEUPS = __LINEUPS_DATA__;
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

// ---- per-card reward + result (value − purchase + reward) ----
const cardRewards = (REWARDS && REWARDS.cards) || {};
rows.forEach(r=>{
  const cr = cardRewards[r.card_slug];
  r.reward_eur = cr ? cr.reward_eur : 0;
  // realized so far, net of what you paid: what the card has brought in
  r.realized_net = (r.purchase_eur!=null)
    ? Math.round((r.reward_eur - r.purchase_eur)*100)/100 : null;
  // total result if you sold it now: reward − purchase + current value
  r.sale_now = (r.value_eur!=null && r.purchase_eur!=null)
    ? Math.round((r.reward_eur - r.purchase_eur + r.value_eur)*100)/100 : null;
});

// index: card slug -> reward lineups it appeared in, and slug -> row
const rewardLineups = (REWARDS && REWARDS.reward_lineups) || [];
const lineupsByCard = {};
rewardLineups.forEach(lu=>(lu.cards||[]).forEach(cs=>{(lineupsByCard[cs]=lineupsByCard[cs]||[]).push(lu);}));
const rowBySlug = {};
rows.forEach(r=>{rowBySlug[r.card_slug]=r;});

document.getElementById("nick").textContent = DATA.nickname;
document.getElementById("crest").textContent = (DATA.nickname||"?").slice(0,1).toUpperCase();
document.getElementById("cardcount").textContent = rows.length;
document.getElementById("asof").innerHTML = "Stand: " + DATA.as_of + "<br>" + priced.length + " mit bekanntem Kaufpreis";

const plClass = pl>=0?"pos":"neg";
const rewardTotal = REWARDS ? REWARDS.totals.total_reward_eur : 0;
if(REWARDS){
  const real = rewardTotal;               // cash rewards actually received
  const broughtIn = real - invested;      // Reward − Kauf: net brought in so far
  const saleNow = broughtIn + valueAll;   // + current value: result if sold now
  const bClass = broughtIn>=0?"pos":"neg";
  const sClass = saleNow>=0?"pos":"neg";
  const sPct = invested ? saleNow/invested*100 : 0;
  document.getElementById("kpis").innerHTML = `
    <div class="kpi"><span class="label">Investiert (gekaufte Karten)</span>
      <span class="val num">${eur(invested)}</span><span class="meta">${priced.length} Karten gekauft</span></div>
    <div class="kpi"><span class="label">Rewards erhalten</span>
      <span class="val num pos">${eur(real)}</span><span class="meta">${REWARDS.totals.reward_lineups} Lineups mit €-Reward</span></div>
    <div class="kpi"><span class="label">Bisher eingespielt (Reward − Kauf)</span>
      <span class="val num ${bClass}">${eur(broughtIn)}</span><span class="meta">realisiert, netto gegen Kaufpreis</span></div>
    <div class="kpi hero"><span class="label">Bei Verkauf jetzt (+ Kartenwert)</span>
      <span class="val num ${sClass}">${eur(saleNow)}</span><span class="meta">inkl. Kartenwert ${eur(valueAll)} · Rendite ${pct(sPct)}</span></div>`;
} else {
  document.getElementById("kpis").innerHTML = `
    <div class="kpi"><span class="label">Investiert (gekaufte Karten)</span>
      <span class="val num">${eur(invested)}</span><span class="meta">${priced.length} Karten mit Kaufpreis</span></div>
    <div class="kpi"><span class="label">Geschätzter Gesamtwert</span>
      <span class="val num">${eur(valueAll)}</span><span class="meta">alle ${rows.length} Karten bewertet</span></div>
    <div class="kpi hero"><span class="label">Gewinn / Verlust</span>
      <span class="val num ${plClass}">${eur(pl)}</span><span class="meta">auf ${both.length} vergleichbaren Karten</span></div>
    <div class="kpi"><span class="label">Rendite</span>
      <span class="val num ${plClass}">${pct(plPct)}</span><span class="meta">Wert ${eur(valueBoth)} vs. ${eur(investedBoth)}</span></div>`;
}

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

// ---- rewards by player ----
if(REWARDS && REWARDS.players && REWARDS.players.length){
  document.getElementById("rewardsSection").hidden = false;
  const players = REWARDS.players.slice().sort((a,b)=>b.reward_eur-a.reward_eur);
  const maxR = players[0].reward_eur || 1;
  document.getElementById("rewardnote").innerHTML =
    "Jeder Geld-Reward eines Lineups wird gleichmäßig auf seine Spieler aufgeteilt (Reward ÷ Spieler) und je Spieler summiert. "+
    "Basis: " + REWARDS.totals.reward_lineups + " von " + REWARDS.totals.lineups + " Lineups mit €-Reward, gesamt " + eur(rewardTotal) + ". "+
    "Karten-Rewards tragen in der API keinen €-Wert und sind hier nicht enthalten.";
  document.getElementById("rewardgrid").innerHTML = players.map((p,i)=>`
    <div class="rrow">
      <span class="rp"><span class="rankn">${i+1}</span>${p.player}</span>
      <span class="rv num">${eur(p.reward_eur)}</span>
      <span class="rm">${p.reward_lineups} Lineup${p.reward_lineups===1?"":"s"}</span>
      <span class="rbar"><span style="width:${Math.max(3,p.reward_eur/maxR*100)}%"></span></span>
    </div>`).join("");
}

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
let sortKey="sale_now", sortDir=1; // 1 asc, -1 desc ; default worst first
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
    const rn=r.realized_net==null?"":(r.realized_net>=0?"pos":"neg");
    const sn=r.sale_now==null?"":(r.sale_now>=0?"pos":"neg");
    const rnCell=r.realized_net==null?`<span class="muted">—</span>`:`<span class="${rn}">${eur(r.realized_net)}</span>`;
    const snPill=r.sale_now==null?`<span class="muted">—</span>`:`<span class="delta-pill ${sn}">${eur(r.sale_now)}</span>`;
    const clickable = r.reward_eur>0 && (lineupsByCard[r.card_slug]||[]).length>0;
    return `<tr ${clickable?`class="clickable" data-slug="${r.card_slug}" title="Reward-Lineups ansehen"`:""}>
      <td class="l"><span class="player" title="${(r.player||'').replace(/"/g,'&quot;')}">${r.player||"—"}</span>${clickable?'<span class="trophy">🏆</span>':''}</td>
      <td class="l"><span class="rchip"><span class="dot" style="background:${c}"></span>${RARITY_LABEL[r.rarity]||r.rarity}</span></td>
      <td class="num muted">${r.season??"—"}</td>
      <td class="num">${r.purchase_eur==null?'<span class="muted">—</span>':eur(r.purchase_eur)}</td>
      <td class="num">${r.reward_eur>0?'<span class="pos">'+eur(r.reward_eur)+'</span>':'<span class="muted">—</span>'}</td>
      <td class="num">${eur(r.value_eur)}</td>
      <td class="num">${rnCell}</td>
      <td class="num">${snPill}</td>
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
  "Tipp: Karten mit 🏆 anklicken, um die Lineups zu sehen, mit denen der Reward gewonnen wurde. "+
  "&bdquo;Kaufpreis&ldquo; = der vom aktuellen Besitzer gezahlte Preis aus öffentlichen Transferdaten; Karten aus Tausch, Reward oder Shards haben keinen Geldpreis (—). "+
  "&bdquo;Akt. Wert&ldquo; = Median der letzten öffentlichen Verkäufe je Spieler + Seltenheit + Season — ein Schätzwert, kein Verkaufsangebot. "+
  "&bdquo;Reward&ldquo; = erhaltene Geld-Rewards der Lineups mit genau dieser Karte (Reward ÷ gespielte Karten, aufsummiert). "+
  "&bdquo;Reward − Kauf&ldquo; = was die Karte bisher netto eingespielt hat (Reward minus Kaufpreis). "+
  "&bdquo;Verkauf jetzt&ldquo; = Ergebnis bei sofortigem Verkauf = Reward − Kaufpreis + akt. Wert. "+
  "Common-Karten sind ausgenommen. Quelle: Sorare GraphQL API.";

// theme toggle
const tb=document.getElementById("themebtn");
tb.onclick=()=>{const cur=document.documentElement.getAttribute("data-theme");
  const next=cur==="dark"?"light":(cur==="light"?"dark":(matchMedia("(prefers-color-scheme:dark)").matches?"light":"dark"));
  document.documentElement.setAttribute("data-theme",next);};

// ---- reward lineup modal ----
const modalBack=document.getElementById("modalBack");
function fmtFixture(slug){
  return (slug||"").replace(/^football-/,"").replace(/-/g," ")
    .replace(/\b([a-z]{3})\b/g, m=>m.charAt(0).toUpperCase()+m.slice(1));
}
function openModal(r){
  const lus=(lineupsByCard[r.card_slug]||[]).slice();
  document.getElementById("modalTitle").textContent =
    (r.player||"?")+" · "+(RARITY_LABEL[r.rarity]||r.rarity)+(r.season?(" · "+r.season):"");
  document.getElementById("modalSub").innerHTML =
    "Reward für diese Karte: <b class='pos'>"+eur(r.reward_eur)+"</b> aus "+lus.length+" Lineup"+(lus.length===1?"":"s")+" — so wurde er gewonnen:";
  document.getElementById("modalBody").innerHTML = lus.map(lu=>{
    const n=(lu.cards&&lu.cards.length)||5;
    const share=Math.round(lu.eur/n*100)/100;
    const chips=(lu.players||[]).map(p=>{
      const me=(p.displayName||"")===(r.player||"");
      const sc=(p.score!=null)?`<span class="ps">${p.score.toLocaleString("de-DE",{maximumFractionDigits:1})}</span>`:"";
      return `<span class="pchip${me?" me":""}">${p.displayName||p.slug}${sc}</span>`;
    }).join("");
    const meta=[];
    if(lu.ranking!=null) meta.push("Platz "+lu.ranking.toLocaleString("de-DE"));
    if(lu.score!=null) meta.push("Score "+lu.score.toLocaleString("de-DE",{maximumFractionDigits:2}));
    const metaLine=meta.length?`<br><span class="gw">${meta.join(" · ")}</span>`:"";
    return `<div class="lu">
      <div class="luhead">
        <div><span class="comp">${lu.leaderboard||"?"}</span><br><span class="gw">${fmtFixture(lu.fixture)}</span>${metaLine}</div>
        <div class="rv">${eur(lu.eur)}<div class="rvs">Anteil dieser Karte ${eur(share)}</div></div>
      </div>
      <div class="players">${chips}</div>
    </div>`;
  }).join("");
  modalBack.classList.add("open");
  document.getElementById("modalClose").focus();
}
function closeModal(){modalBack.classList.remove("open");}
document.getElementById("rows").addEventListener("click", e=>{
  const tr=e.target.closest("tr.clickable"); if(!tr) return;
  const r=rowBySlug[tr.dataset.slug]; if(r) openModal(r);
});
document.getElementById("modalClose").onclick=closeModal;
modalBack.addEventListener("click", e=>{ if(e.target===modalBack) closeModal(); });
document.addEventListener("keydown", e=>{ if(e.key==="Escape") closeModal(); });

// ---- tabs + lineup suggestions ----
function showView(v){
  document.getElementById("view-overview").hidden = (v!=="overview");
  document.getElementById("view-suggest").hidden = (v!=="suggest");
  document.querySelectorAll(".tab").forEach(t=>t.setAttribute("aria-selected", t.dataset.view===v?"true":"false"));
}
document.querySelectorAll(".tab").forEach(t=>t.onclick=()=>showView(t.dataset.view));

const SLOT_DE={Goalkeeper:"TW",Defender:"ABW",Midfielder:"MF",Forward:"ST",Extra:"Extra"};
function fmtDate(iso){ try{return new Date(iso).toLocaleDateString("de-DE",{day:"numeric",month:"short"});}catch(e){return "";} }
function fmtDT(iso){ try{return new Date(iso).toLocaleString("de-DE",{weekday:"short",day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"});}catch(e){return "";} }
function startCls(p){ return p>=0.75?"hi":(p>=0.5?"mid":"lo"); }
const SOFA_DE={confirmed_start:["bestätigt: Start","hi"],confirmed_bench:["bestätigt: Bank","lo"],
  confirmed_out:["nicht im Kader","lo"],pred_start:["voraussichtl. Start","mid"],pred_bench:["voraussichtl. Bank","lo"]};
function sofaTag(c){
  const s=c.sofa_status; if(!s||!SOFA_DE[s]) return "";
  const [txt,cls]=SOFA_DE[s];
  return ` · <span class="safe"><b class="${cls}">SofaScore: ${txt}</b></span>`;
}
function startChip(p){
  if(p==null) return "";
  return `<span class="pchip ${startCls(p)}" title="Startelf-Wahrscheinlichkeit">${Math.round(p*100)}%</span>`;
}
function minsHtml(arr){
  if(!arr||!arr.length) return "";
  // most recent first: full start (≥60), part (30–59), cameo/none (<30)
  const cells=arr.map(m=>{
    if(m==null) return '<span class="x">·</span>';
    if(m>=60) return `<b>${Math.round(m)}</b>`;
    if(m>=30) return `<span class="s">${Math.round(m)}</span>`;
    return `<span class="x">${Math.round(m)}</span>`;
  });
  return `<span class="mins">Min ${cells.join(" ")}</span>`;
}
function prow(c){
  const cap=c.captain?'<span class="capbadge">C</span>':'';
  const cl=c.classic?'<span class="capbadge" style="background:var(--flat)">Classic</span>':'';
  const ha=c.home?"H":"A";
  const slot=c.slot||c.slot_primary||"";
  const chip=startChip(c.start_prob);
  const ev=(c.ev!=null)?`<span class="ev">EV ${c.ev.toLocaleString("de-DE",{maximumFractionDigits:1})}</span>`:"";
  return `<div class="prow">
    <span class="slotchip">${SLOT_DE[slot]||slot||"–"}</span>
    <span class="pn">${c.player}${cap}${cl}${chip}</span>
    <span class="pp">${c.proj.toLocaleString("de-DE",{maximumFractionDigits:1})}${ev}</span>
    <span class="pm">L5 ${c.l5!=null?c.l5.toLocaleString("de-DE"):"–"} · ${c.opponent||"?"} (${ha}) · Cap ${c.cap_score!=null?c.cap_score.toLocaleString("de-DE"):"–"} · ${minsHtml(c.recent_mins)}${sofaTag(c)}</span>
  </div>`;
}
function teamCard(comp, team, idx){
  const capUse = comp.cap ? `Cap ${team.cap_used} / ${comp.cap}` : `Cap ${team.cap_used} (uncapped)`;
  const warn = team.over_cap
    ? `<div class="lu-warn">⚠ Cap nicht erfüllbar — bestes Team liegt bei ${team.cap_used} > ${comp.cap}.</div>`
    : (!team.complete ? `<div class="lu-warn">⚠ Unvollständig — nicht genug spielende Karten (${team.cards.length}/${comp.size}).</div>` : "");
  const rows = team.cards.map(prow).join("");
  const as=team.avg_start;
  const safe=(as!=null)?`<div class="capline"><span class="safe">Startelf-Schnitt <b class="${startCls(as)}">${Math.round(as*100)}%</b>${team.min_start!=null?` · schwächster <b class="${startCls(team.min_start)}">${Math.round(team.min_start*100)}%</b>`:""}${team.expected_total!=null?` · Erwartung <b>Σ ${Math.round(team.expected_total).toLocaleString("de-DE")}</b>`:""}${idx===0?" · sichere Aufstellung":(team.risk_floor!=null&&team.risk_floor<0.5?" · Risiko erlaubt":"")}</span></div>`:"";
  return `<div class="lucard">
    <div class="h"><span class="t">Team ${idx+1}</span><span class="tot">Σ ${Math.round(team.projected_total).toLocaleString("de-DE")}</span></div>
    <div class="capline">${capUse}</div>${safe}${warn}${rows}</div>`;
}
function renderSuggestions(){
  const L=LINEUPS;
  const comps=L.competitions||[];
  const rars=[...new Set(comps.map(c=>c.rarity))];
  const blocks=rars.map(rar=>{
    const cs=comps.filter(c=>c.rarity===rar);
    const el=(L.eligible&&L.eligible[rar]!=null)?L.eligible[rar]:(cs[0]?cs[0].eligible_count:0);
    const compBlocks=cs.map(comp=>{
      const teams=comp.teams||[];
      const dl=comp.deadline_first?` · ⏱ ab ${fmtDT(comp.deadline_first)}`:"";
      const pw=comp.prize_weight?`<span class="fmt-badge" style="color:var(--gain)">Pool ×${comp.prize_weight.toLocaleString("de-DE")}</span>`:"";
      const body = teams.length
        ? `<div class="lineups2">${teams.map((t,i)=>teamCard(comp,t,i)).join("")}</div>`
        : `<div class="lu-warn" style="border-radius:12px">Kein vollständiges Team möglich.</div>`;
      return `<div class="comp-block">
        <div class="comp-head">
          <span class="comp-title">${comp.label}</span>
          <span class="fmt-badge">${comp.format}${comp.size?` · ${comp.size} Karten`:""}</span>
          ${pw}
          <span class="teams-note">bis ${comp.teams_cap} Team${comp.teams_cap>1?"s":""}${teams.length?` · ${teams.length} gebaut`:""}${dl}</span>
        </div>${body}</div>`;
    }).join("");
    return `<div class="rar-block">
      <div class="eyebrow" style="margin:18px 2px 12px">${RARITY_LABEL[rar]||rar} · ${el} spielende Karten im GW</div>
      ${compBlocks}</div>`;
  }).join("");
  const totS=L.total_projected!=null?Math.round(L.total_projected).toLocaleString("de-DE"):"—";
  const totE=L.total_expected!=null?Math.round(L.total_expected).toLocaleString("de-DE"):"—";
  const hso=L.hotstreak_overview||[];
  const hsChips=hso.map(h=>{
    const ok=h.fieldable;
    const miss=Math.max(0,(h.needed||4)-h.in_season);
    return `<span class="hschip ${ok?'ok':'no'}">${(RARITY_LABEL[h.rarity]||h.rarity)} · ${h.label.replace('Pro · ','').replace(' (Hot Streak)','')}
      <b>${h.in_season}/${h.needed||4}</b> ${ok?'✓ spielbar':'· fehlen '+miss}</span>`;
  }).join("");
  const hsBlock=hso.length?`<div class="eyebrow" style="margin:4px 2px 8px">Hot-Streak-Überblick (In-Season-Tiefe · 4 nötig + 1 Classic)</div><div class="hswrap">${hsChips}</div>`:"";
  const sofaBanner = L.sofascore
    ? `<div class="capline" style="border-radius:12px;margin:0 0 12px;border:1px solid var(--line)"><span class="safe"><b class="hi">✓ Voraussichtliche Aufstellungen (SofaScore) aktiv</b> — bestätigte Teamsheets überschreiben den Score, voraussichtliche Elf fließt gewichtet ein.</span></div>`
    : "";
  document.getElementById("view-suggest").innerHTML = `
    <div class="eyebrow" style="margin:2px 2px 4px">Bestmögliches Gesamt-Setup (Sorare 27)</div>
    <h2 style="font-family:Archivo;font-size:20px;letter-spacing:-.01em;margin:0 0 6px">Spieltag ${L.fixture.gameWeek} · ${fmtDate(L.fixture.start)}–${fmtDate(L.fixture.end)}</h2>
    <div class="kpis" style="margin-bottom:14px">
      <div class="kpi"><span class="label">Projizierter Gesamt-Score</span><span class="val num">Σ ${totS}</span><span class="meta">wenn alle spielen</span></div>
      <div class="kpi"><span class="label">Erwartungswert (× Startelf)</span><span class="val num">Σ ${totE}</span><span class="meta">Punkte × Startwahrscheinlichkeit</span></div>
      <div class="kpi"><span class="label">Karten eingesetzt</span><span class="val num">${L.cards_used??"—"}</span><span class="meta">jede Karte nur einmal (global)</span></div>
      <div class="kpi hero"><span class="label">Aufstellungen</span><span class="val num">${(L.competitions||[]).reduce((s,c)=>s+(c.teams||[]).length,0)}</span><span class="meta">nach erwartetem Ertrag priorisiert</span></div>
    </div>
    ${sofaBanner}
    ${hsBlock}
    <p class="sugg-note"><b>Startelf-Score (Prediction):</b> der farbige %-Chip je Karte ist die geschätzte <b>Startwahrscheinlichkeit</b> — gemischt aus <b>zuletzt gespielten Minuten</b> (stärkstes Signal, jüngste Spiele höher gewichtet; die Zahlen bei „Min" = Minuten der letzten Spiele, <b class="mins"><b>grün</b></b> = Start ≥60′, <span class="mins"><span class="s">gelb</span></span> = Teileinsatz, <span class="mins"><span class="x">rot</span></span> = Kurz-/kein Einsatz), <b>Einsatzquote</b> (letzte 15 SO5) und dem <b>Verletzungs-Feed</b> mit Rückkehrdatum (gegengeprüft mit den Minuten). <b>Team 1 = sichere Aufstellung</b> (nur nahezu sichere Starter, Schwelle 75 %); jedes weitere Team senkt die Schwelle (55/40/25 %), darf also <b>riskieren</b>. Ausgewählt wird nach <b>Erwartungswert EV = projizierte Punkte × Startwahrscheinlichkeit</b>. Optional lässt sich eine externe Quelle (<b>SofaScore</b>) zuschalten, die dann bestätigte Teamsheets/voraussichtliche Elf einmischt — SofaScore sperrt derzeit aber Server-IPs, daher nutzt der Score aktuell nur Sorare-Daten.<br><br><b>Max-Profit-Aufteilung:</b> jede Karte wird <b>nur einmal</b> im ganzen GW eingesetzt; zuerst die <b>In-Season Hot Streaks (Pro)</b>, danach die übrigen nach <b>EV × Pool-Gewicht</b>. Das <b>Pool-Gewicht</b> (z. B. Pool ×2,6) schätzt den relativen Preispool je Wettbewerb (Rare ≈ 2× Limited, Pro > Arena, Champion/Top-Ligen größer) — anpassbar, keine exakten Auszahlungen. <b>Pro = SO7</b> (7 Karten, Hot Streaks 5), <b>Arena = SO5</b> (Cap: Σ L15-Scores ≤ Cap). <b>⏱</b> = frühester Anstoß (Deadline); <b>Contender</b> nutzt das späteste Spielende seiner Ligen. Projizierter Score = L5-Form × Einsatzquote × Heimvorteil (H); <b>C</b> = Kapitän (×2). <b>Näherung:</b> exakte Step-Clock/Contender-Gruppierung noch nicht abgebildet.</p>
    ${blocks}`;
}
if(LINEUPS && (LINEUPS.competitions||LINEUPS.rarities)){
  document.getElementById("tab-suggest").hidden=false;
  renderSuggestions();
}

// default sort indicator
const dth=document.querySelector('thead th[data-k="sale_now"]');
dth.setAttribute("aria-sort","ascending");
render();
</script>
"""


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path")
    ap.add_argument("--out", default="dashboard.html")
    ap.add_argument("--rewards", default=None,
                    help="optional rewards.json from rewards_by_player.py")
    ap.add_argument("--lineups", default=None,
                    help="optional lineups.json from lineup_suggest.py")
    args = ap.parse_args(argv)
    with open(args.json_path, encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("as_of", datetime.date.today().isoformat())

    rewards = "null"
    if args.rewards:
        with open(args.rewards, encoding="utf-8") as fh:
            rw = json.load(fh)
        # keep only what the page needs
        rewards = json.dumps({
            "totals": rw.get("totals", {}),
            "players": rw.get("players", []),
            "cards": rw.get("cards", {}),
            "reward_lineups": rw.get("reward_lineups", []),
        }, ensure_ascii=False)

    lineups = "null"
    if args.lineups:
        with open(args.lineups, encoding="utf-8") as fh:
            lineups = json.dumps(json.load(fh), ensure_ascii=False)

    html = TEMPLATE.replace("__CLUB_DATA__", json.dumps(data, ensure_ascii=False))
    html = html.replace("__REWARDS_DATA__", rewards)
    html = html.replace("__LINEUPS_DATA__", lineups)
    html = html.replace("__NICK__", data.get("nickname", "Club"))
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"Wrote {args.out} ({len(html):,} bytes, {len(data['rows'])} rows)")


if __name__ == "__main__":
    main(sys.argv[1:])
