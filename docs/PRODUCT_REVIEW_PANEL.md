# Expert Panel Review — «نقشه تجارت ایران / Iran Trade Map»

> A cross-disciplinary product review. Five experts independently audited the
> codebase, then convened to debate the findings and agree on what is failing
> and how to fix it. This document is the transcript of that discussion and the
> panel's shared conclusion.

---

## The panel

| Expert | Field | One-line stance |
|--------|-------|-----------------|
| **Dr. Nasim** | Product Manager / UX Researcher | "It's an engineer's demo, not a user's tool — no user's real question can be answered end-to-end." |
| **Reza** | Data Engineer / Data Quality | "It has never processed a real IRICA file. The product runs exclusively on synthetic demo data." |
| **Lena** | Frontend / Data-Viz Engineer | "The core visual probably renders as arcs floating over a void, and one failed fetch kills the whole page." |
| **Marcus** | Backend / Systems Architect | "It wears a production Docker/nginx costume over a demo. The database is decorative." |
| **Yara** | Business / Go-to-Market Strategist | "The engineering is real; the strategy is inverted. It competes with free, superior tools while discarding its only moat." |

---

## Round 1 — Opening positions

**Dr. Nasim (Product):** The README never names a user, and it shows on every
screen. The value proposition is "a beautiful globe with glowing arcs" — that's a
*visualization*, not a *product*. Users arrive with questions; the tool gives them
no way to ask. There's no product filter (the backend supports `hs_chapter` but the
UI never exposes it), no export, no shareable URL, no drill-down. You can exhaust the
entire app in about 40 seconds. Nothing brings anyone back tomorrow.

**Reza (Data):** I'll go further, and this reframes everything Nasim just said.
The product doesn't run on real data at all. There's a hard schema break:
`normalizer.run_all` emits a column called `year`, but `api/store.py` reads
`shamsi_year` on startup (`store.py:39`). The instant a real
`normalized_trade.parquet` exists, the API throws `KeyError: 'shamsi_year'` and
**the site fails to boot.** It only works today because `utils/sample_data.py`
happens to emit the columns the API wants. Every number on screen is synthetic.

**Lena (Frontend):** That matches what I found on the client. `index.html` loads
**Mapbox GL v3** but never sets an access token — Mapbox throws on init without one.
The Carto basemap style wants **MapLibre**, not Mapbox. So the basemap likely errors
out and you get arcs over a black void. And even the happy path is fragile: `loadAll`
fires four fetches with no try/catch, and `get()` throws on any non-2xx — so a single
failed request leaves the dashboard blank forever, no spinner, no error. For an
audience inside Iran, loading Mapbox + unpkg + Carto from foreign CDNs is the
worst-case dependency choice; those hosts are exactly what gets blocked.

**Marcus (Backend):** The infrastructure tells the same story. The API never touches
Postgres — `grep` for `create_engine`/`psycopg`/`sqlalchemy` across `api/` returns
nothing. The whole `db/` package and the Postgres container in `docker-compose.yml`
are dead weight. `lru_cache` is imported and never used, so every request re-runs a
full-DataFrame `groupby`. The nginx config declares `proxy_cache_valid` but never
defines a cache zone, so server-side caching is a no-op. It's a demo wearing a
production costume.

**Yara (Strategy):** And zoom out: even if all of that worked perfectly, who is it
*for*? OEC.world already does this exact arc/treemap/partner visualization for every
country, free, and better. UN Comtrade and World Bank are free. The one defensible
asset — granular IRICA customs records with unit prices — is exactly what this
product de-emphasizes, treating IRICA as one of five equal sources. It's built as a
Persian dashboard for an audience that can't be billed (no payment rails into Iran),
competing head-on with free superior tools, while ignoring an existential OFAC/
sanctions constraint. The strategy is inverted.

---

## Round 2 — Cross-examination and debate

**Dr. Nasim → Reza:** So when I said "no user's question can be answered
end-to-end," the real reason is worse than a missing feature — the pipeline that
would feed those features doesn't connect?

**Reza:** Correct. It's not just missing UI. The moment real data flows, five things
break silently and two break loudly. Currency is a time bomb: a bare `ارزش` column is
often **Rial**, not USD, but it's mapped to `value_usd` — that inflates a flow by ~5
orders of magnitude. Rial-only rows sum to zero and vanish. Weight in tons gets read
as kg (1000× off). And there's no dedup, so IRICA's cumulative year-to-date files get
concatenated onto monthly files and the year is multiply-counted. None of this is
guarded. A bad month ships silently.

**Yara → Reza:** That actually *sharpens* my strategic point. The data-accuracy
problem isn't only a bug — it's the market problem. Iran's official customs figures
are widely regarded as politically curated and are contradicted by mirror data from
China, Turkey, UAE. A serious analyst's first question is "why should I trust these
numbers?" If we can't even reconcile our own columns, we certainly can't answer that.

**Marcus → Yara:** But here's where I'll push on you. You want to pivot to an
English-first intelligence product for Western analysts. That's a coherent business,
but it's a *different* product from what's in this repo — Persian-first, Iran-user,
free dashboard. We can't do both well with the current team and this codebase. Which
is it?

**Yara:** I hear that, and I'll concede the pivot is a big bet, not a bug-fix. But my
claim is narrower than "throw it away." The *asset* to lead with — granular IRICA HS6
data with unit prices, reconciled against mirror data — is valuable regardless of which
audience we serve. Reconciliation is the wedge either way: for a Persian audience it's
credibility; for a Western audience it's the paid differentiator. So I don't need the
panel to resolve the audience question today. I need us to agree that **the reconciled,
granular IRICA layer is the point**, and that the current "fifth rendering of open
aggregates" is not.

**Dr. Nasim:** I can align with that. My "pick one user, close one loop" prescription
is audience-agnostic in mechanism: expose the product/HS filter the backend already
has, add export + a shareable URL, and label the data honestly. Those make it a
*citable tool* whether the citer writes in Persian or English.

**Lena:** And nothing I'm asking for conflicts with either audience. Loading states,
self-hosted libraries, a basemap that actually renders, an encoding whose widths are
comparable (right now `pitch: 40` foreshortens the arcs so you can't compare the one
quantitative channel that matters) — those are table stakes in any language.

**Reza → everyone:** Then let me name the thing we're circling. Every one of you found
a different symptom, but they rhyme: **the product presents confidence it hasn't
earned.** Fake numbers shown as real (`store.py` silently falls back to sample data
with no banner). A cache that isn't caching. A Postgres that serves nothing. A
"transit" tab that renders empty because of a filter-order bug (`store.py:166`). A map
that drops any country lacking coordinates, so the arcs on screen don't sum to the
headline total — and the user is never told.

**Marcus:** That's the through-line. It's *Potemkin completeness*. The scaffolding
signals "production data platform"; the reality is "synthetic single-file demo." The
danger isn't that it's early — everything is early once. The danger is that it hides
how early it is, from users **and from its own builders.** That's why no test caught
the schema break: the tests validate the sample data, so the demo validates the demo.

**Yara:** Agreed, and that's the commercial killer too. A data product's entire equity
is trust. The first time a journalist cites a number that turns out to be synthetic —
or off by 100,000× because a Rial column was read as USD — the credibility is gone and
doesn't come back.

---

## Round 3 — Convergence: the root cause

The panel agreed the many findings collapse to **one root cause and three
consequences.**

**Root cause — a broken vertical slice masked by synthetic data.**
There is no working end-to-end path from a real IRICA file to a rendered, trustworthy
number. The seams between stages (parser → normalizer → store; store → map; app →
CDN; API → Postgres) are each broken or bypassed, and a synthetic-data fallback hides
every one of those breaks. The project optimized *breadth* (five data sources, Docker,
nginx, Postgres schema, five endpoints) before it ever closed *one* vertical slice.

This produces three consequences, one per layer:

1. **It isn't true** (Data). Currency/unit/dedup/schema defects mean that even once it
   boots on real data, the numbers are wrong in ways nobody is alerted to.
2. **It isn't usable** (Product + Frontend). No named user, no answerable question, no
   export/share, a probably-blank map, no loading/error states, no mobile, half-done
   RTL.
3. **It isn't wanted — as built** (Strategy + Backend). It competes with free superior
   tools, discards its only moat, can't be billed to its stated audience, carries
   unaddressed sanctions risk, and runs on infrastructure that serves no real load.

---

## Conclusion & agreed roadmap

> **Verdict:** The failure is not a lack of engineering effort — the pipeline
> scaffolding and the schema design are genuinely competent. The failure is
> **sequencing and honesty**: the team built a wide, impressive-looking platform on
> top of a vertical slice that was never actually connected, and let synthetic data
> disguise the gap. The fix is to *narrow, connect, and be honest* before widening
> again.

### Now — earn the right to be trusted (unblock the real-data path)
*Owners: Data + Backend. Nothing else matters until these land.*

1. **Unify the schema and prove it with a contract test.** Make `normalizer.run_all`
   emit the canonical names the API reads (`shamsi_year`, `commodity_fa`, …); add a
   test that writes a real-shaped normalized parquet and boots `store.load()` + one
   query. (Fixes the `KeyError` that keeps the site on synthetic data.)
2. **Fix currency and units at parse time — never guess.** Separate `value_rial` /
   `value_usd`, add a period-keyed IRR→USD table stored as provenance, coalesce
   FOB/CIF, convert tons→kg. Aggregate one reconciled value column.
3. **Make ingestion idempotent and cumulative-aware.** Natural key + `file_hash` skip
   + upsert; detect YTD-cumulative vs monthly files so years aren't multiply-counted.
4. **Stop lying about data state.** A loud, persistent `DEMO / نمونه` banner whenever
   `store.py` falls back to sample data; a "source + last-updated" badge otherwise;
   surface the *unmapped-country value share* so the map reconciles with the totals.
5. **Turn `quality_report` into an enforced gate** (fail/quarantine on thresholds of
   value-at-risk), and add real API + adversarial-fixture tests so the demo can no
   longer validate the demo.

### Next — make it usable and make it render
*Owners: Frontend + Product.*

6. **Fix the map stack:** self-host + version-pin the libs (CDN/sanctions resilience),
   switch Mapbox GL → **MapLibre GL** so the token-free basemap actually renders.
7. **Add loading / error / empty states** around `loadAll`; default to the latest
   available year instead of a hardcoded `1402`; fix the empty Transit panel bug.
8. **Close one user loop end-to-end:** expose the HS/product filter the backend
   already supports, add CSV/PNG export and a shareable URL (encode state in the query
   string). This is what turns a screenshot into a citable tool.
9. **Fix the encoding and finish RTL:** `pitch: 0`, pixel-unit √-scaled symbols, color
   the treemap by HS section (not rank index), add a non-color channel for
   export/import; actually load Vazirmatn, Persian numerals, responsive/mobile layout.

### Later — decide what it's *for*, then widen
*Owners: Strategy + Product. Requires an explicit decision, not a code change.*

10. **Lead with the moat: reconciled, granular IRICA data.** Ingest partner-country
    mirror data (Comtrade — already scraped) and show IRICA-vs-mirror with a
    discrepancy/confidence indicator. "The only Iran-trade tool that tells you where
    the official numbers don't add up" is a real, defensible differentiator that
    OEC/Comtrade do not offer — and it doubles as the credibility layer for any
    audience.
11. **Make the audience decision explicitly** (Persian civic tool vs English-first
    analyst product), and **get a sanctions/OFAC opinion before building further** —
    it gates hosting, payments, and who you can serve.
12. **Ship distribution:** one hosted URL, SEO landing pages per country/commodity,
    embeddable charts. A data product grows through its screenshots in articles, not
    its feature count.

---

### One-sentence panel summary
*The product fails because it built breadth on a vertical slice that was never
connected and hid the gap behind synthetic data; make it better by narrowing to one
honest, correct, end-to-end path — real IRICA numbers, reconciled and clearly
labelled, answering one user's question — before widening again.*
