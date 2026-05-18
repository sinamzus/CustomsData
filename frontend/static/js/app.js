/* Iran Trade Map — Frontend */
'use strict';

const API = '';  // same-origin
const IRAN_LNG = 53.69, IRAN_LAT = 32.43;

// ── Direction color map ───────────────────────────────────────────────────
const DIR_COLOR = {
  export:  [63, 185, 80],
  import:  [247, 129, 102],
  transit: [210, 168, 255],
};

// ── State ─────────────────────────────────────────────────────────────────
let state = {
  year: 1402,
  direction: 'export',
  selectedCountry: null,
  mapFlows: [],
  partners: [],
};

// ── Deck.gl setup ─────────────────────────────────────────────────────────
const deckgl = new deck.DeckGL({
  container: 'deckCanvas',
  mapStyle: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  initialViewState: {
    longitude: 53.69, latitude: 30.0,
    zoom: 2.8, pitch: 40, bearing: 0,
  },
  controller: true,
  layers: [],
  getTooltip: null,
});

// ── Utility ───────────────────────────────────────────────────────────────
function fmt(n) {
  if (!n) return '—';
  if (n >= 1e9) return (n / 1e9).toFixed(1) + ' B$';
  if (n >= 1e6) return (n / 1e6).toFixed(0) + ' M$';
  return (n / 1e3).toFixed(0) + ' K$';
}

function fmtW(kg) {
  if (!kg) return '—';
  if (kg >= 1e9) return (kg / 1e9).toFixed(1) + ' Mt';
  if (kg >= 1e6) return (kg / 1e6).toFixed(1) + ' kt';
  return (kg / 1e3).toFixed(0) + ' t';
}

function showTooltip(x, y, html) {
  const el = document.getElementById('tooltip');
  el.innerHTML = html;
  el.style.left = x + 'px';
  el.style.top  = y + 'px';
  el.classList.remove('hidden');
}
function hideTooltip() {
  document.getElementById('tooltip').classList.add('hidden');
}

// ── Map layers ────────────────────────────────────────────────────────────
function buildLayers(flows) {
  if (!flows.length) return [];

  const dir = state.direction;
  const color = DIR_COLOR[dir] || [88, 166, 255];
  const maxVal = Math.max(...flows.map(f => f.value_usd || f.weight_kg || 1));

  const arcLayer = new deck.ArcLayer({
    id: 'trade-arcs',
    data: flows,
    getSourcePosition: f => dir === 'import'
      ? [f.lng, f.lat]
      : [IRAN_LNG, IRAN_LAT],
    getTargetPosition: f => dir === 'import'
      ? [IRAN_LNG, IRAN_LAT]
      : [f.lng, f.lat],
    getSourceColor: dir === 'import' ? color : [88, 166, 255],
    getTargetColor: dir === 'import' ? [88, 166, 255] : color,
    getWidth: f => {
      const v = f.value_usd || f.weight_kg || 0;
      return Math.max(0.5, (v / maxVal) * 8);
    },
    getHeight: 0.4,
    opacity: 0.7,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 80],
    onHover: ({ object, x, y }) => {
      if (object) {
        showTooltip(x, y,
          `<strong>${object.country}</strong>` +
          `<div>ارزش: <span class="val">${fmt(object.value_usd)}</span></div>` +
          `<div>وزن: <span class="val">${fmtW(object.weight_kg)}</span></div>`
        );
      } else {
        hideTooltip();
      }
    },
    onClick: ({ object }) => {
      if (object) {
        state.selectedCountry = object.country;
        loadTimeseries();
      }
    },
  });

  const scatterLayer = new deck.ScatterplotLayer({
    id: 'country-dots',
    data: flows,
    getPosition: f => [f.lng, f.lat],
    getRadius: f => {
      const v = f.value_usd || f.weight_kg || 0;
      return Math.max(40000, (v / maxVal) * 600000);
    },
    getFillColor: f => [...color, 180],
    getLineColor: [255, 255, 255, 60],
    lineWidthMinPixels: 1,
    stroked: true,
    pickable: true,
    onHover: ({ object, x, y }) => {
      if (object) {
        showTooltip(x, y,
          `<strong>${object.country}</strong>` +
          `<div>ارزش: <span class="val">${fmt(object.value_usd)}</span></div>` +
          `<div>وزن: <span class="val">${fmtW(object.weight_kg)}</span></div>`
        );
      } else {
        hideTooltip();
      }
    },
  });

  // Iran marker
  const iranLayer = new deck.ScatterplotLayer({
    id: 'iran-dot',
    data: [{ pos: [IRAN_LNG, IRAN_LAT] }],
    getPosition: d => d.pos,
    getRadius: 200000,
    getFillColor: [255, 200, 0, 220],
    getLineColor: [255, 255, 255],
    lineWidthMinPixels: 2,
    stroked: true,
  });

  return [arcLayer, scatterLayer, iranLayer];
}

function renderMap() {
  deckgl.setProps({ layers: buildLayers(state.mapFlows) });
  renderLegend();
}

function renderLegend() {
  const dir = state.direction;
  const col = DIR_COLOR[dir] || [88, 166, 255];
  const label = { export: 'صادرات', import: 'واردات', transit: 'ترانزیت' }[dir];
  document.getElementById('mapLegend').innerHTML = `
    <div class="legend-row">
      <div class="legend-dot" style="background:rgb(${col.join(',')})"></div>
      <span>${label} — ${state.year}</span>
    </div>
    <div class="legend-row">
      <div class="legend-dot" style="background:rgb(255,200,0)"></div>
      <span>ایران</span>
    </div>
    <div style="color:#8b949e;font-size:11px;margin-top:6px">ضخامت کمان = ارزش تجارت</div>
  `;
}

// ── Partners sidebar ──────────────────────────────────────────────────────
function renderPartners(partners) {
  const barClass = state.direction + '-bar';
  const maxVal = Math.max(...partners.map(p => p.value_usd || 1));
  const html = partners.map(p => `
    <div class="partner-row" onclick="selectCountry('${p.country_iso3}')">
      <span class="partner-rank">${p.rank}</span>
      <span class="partner-name">${p.name_fa || p.country_iso3}</span>
      <div class="partner-bar-wrap">
        <div class="partner-bar-bg">
          <div class="partner-bar-fill ${barClass}"
               style="width:${Math.max(2, p.value_usd / maxVal * 100)}%"></div>
        </div>
      </div>
      <span class="partner-value">${fmt(p.value_usd)}</span>
    </div>
  `).join('');
  document.getElementById('partnersList').innerHTML = html;
}

function selectCountry(iso3) {
  state.selectedCountry = iso3;
  loadTimeseries();
}

// ── Summary badges ────────────────────────────────────────────────────────
function renderSummary(data) {
  const exp = data.export?.value_usd;
  const imp = data.import?.value_usd;
  const transit = data.transit?.weight_kg;
  const bal = data.trade_balance_usd;

  document.getElementById('summaryBadges').innerHTML = `
    <div class="badge">صادرات: <span>${fmt(exp)}</span></div>
    <div class="badge">واردات: <span>${fmt(imp)}</span></div>
    <div class="badge">ترانزیت: <span>${fmtW(transit)}</span></div>
    <div class="badge">تراز: <span style="color:${bal >= 0 ? '#3fb950' : '#f78166'}">${fmt(Math.abs(bal))}</span></div>
  `;
}

// ── Plotly charts ─────────────────────────────────────────────────────────
function renderTimeseries(data, country) {
  const title = country
    ? `روند تجارت با ${country}`
    : 'روند کل تجارت';

  Plotly.newPlot('timeseriesChart', [{
    x: data.map(d => d.year),
    y: data.map(d => (d.value_usd || 0) / 1e9),
    type: 'scatter',
    mode: 'lines+markers',
    line: { color: state.direction === 'export' ? '#3fb950'
                 : state.direction === 'import' ? '#f78166' : '#d2a8ff',
            width: 2 },
    marker: { size: 5 },
    hovertemplate: '%{x}: %{y:.1f}B$<extra></extra>',
  }], {
    paper_bgcolor: 'transparent',
    plot_bgcolor:  'transparent',
    font: { color: '#e6edf3', size: 11 },
    margin: { t: 20, r: 10, b: 30, l: 40 },
    xaxis: { gridcolor: '#30363d', tickfont: { size: 10 } },
    yaxis: { gridcolor: '#30363d', tickfont: { size: 10 }, title: 'میلیارد دلار' },
    showlegend: false,
    height: 160,
  }, { displayModeBar: false, responsive: true });
}

function renderTreemap(data) {
  const top = data.slice(0, 18);
  Plotly.newPlot('treemapChart', [{
    type: 'treemap',
    labels: top.map(d => d.name_fa),
    parents: top.map(() => ''),
    values: top.map(d => d.value_usd),
    textinfo: 'label+percent root',
    hovertemplate: '%{label}<br>%{value:,.0f} $<extra></extra>',
    marker: {
      colors: top.map((_, i) => `hsl(${200 + i * 15},60%,45%)`),
    },
  }], {
    paper_bgcolor: 'transparent',
    plot_bgcolor:  'transparent',
    font: { color: '#e6edf3', size: 10 },
    margin: { t: 4, r: 4, b: 4, l: 4 },
    height: 220,
  }, { displayModeBar: false, responsive: true });
}

// ── API calls ─────────────────────────────────────────────────────────────
async function get(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
}

async function loadAll() {
  const { year, direction } = state;
  const [summary, flows, partners, treemapData] = await Promise.all([
    get(`/api/summary?year=${year}`),
    get(`/api/flows/map?year=${year}&direction=${direction}&top_n=60`),
    get(`/api/flows/partners?year=${year}&direction=${direction}&n=15`),
    get(`/api/flows/treemap?year=${year}&direction=${direction}`),
  ]);

  state.mapFlows = flows;
  state.partners = partners;

  renderSummary(summary);
  renderMap();
  renderPartners(partners);
  renderTreemap(treemapData);

  // Timeseries: total if no country selected
  await loadTimeseries();
}

async function loadTimeseries() {
  const { direction, selectedCountry } = state;
  const q = selectedCountry
    ? `/api/flows/timeseries?direction=${direction}&country=${selectedCountry}`
    : `/api/flows/timeseries?direction=${direction}`;
  const data = await get(q);
  renderTimeseries(data, selectedCountry);
}

// ── Init ──────────────────────────────────────────────────────────────────
async function init() {
  // Populate year selector
  const years = await get('/api/years');
  const sel = document.getElementById('yearSelect');
  [...years].reverse().forEach(y => {
    const opt = document.createElement('option');
    opt.value = y;
    opt.text  = y;
    if (y === 1402) opt.selected = true;
    sel.appendChild(opt);
  });

  sel.addEventListener('change', e => {
    state.year = parseInt(e.target.value);
    state.selectedCountry = null;
    loadAll();
  });

  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.direction = btn.dataset.dir;
      state.selectedCountry = null;
      loadAll();
    });
  });

  await loadAll();
}

document.addEventListener('DOMContentLoaded', init);
