const API = "http://localhost:8000";

let state = {
  limit: 15,
  offset: 0,
  bucket: "day",
  filters: {}
};

let charts = { trend: null, dir: null, unit: null };

// Map
let map = null;
let mapMarkers = [];

// Live
let liveTimer = null;
let lastUpdatedAt = null;

function qs(id){ return document.getElementById(id); }

function toISOFromDatetimeLocal(v){
  if(!v) return null;
  return new Date(v).toISOString();
}

function buildQuery(params){
  const usp = new URLSearchParams();
  for (const [k, assume] of Object.entries(params)){
    const v = assume;
    if(v === null || v === undefined || v === "") continue;
    usp.set(k, v);
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

async function apiGet(path, params={}){
  const res = await fetch(`${API}${path}${buildQuery(params)}`);
  if(!res.ok){
    const t = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${t}`);
  }
  return await res.json();
}

function numberFmt(x){
  if(x === null || x === undefined) return "—";
  const n = Number(x);
  if(Number.isNaN(n)) return String(x);
  return n.toLocaleString("uk-UA", {maximumFractionDigits: 2});
}

function setStatus(ok){
  const el = qs("apiStatus");
  el.textContent = ok ? "OK" : "ERROR";
  el.style.background = ok ? "rgba(70, 210, 120, .18)" : "rgba(255, 80, 80, .18)";
  el.style.borderColor = ok ? "rgba(70, 210, 120, .35)" : "rgba(255, 80, 80, .35)";
}

function showToast(msg="Оновлено"){
  const t = qs("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  setTimeout(()=>t.classList.add("hidden"), 900);
}

function readFilters(){
  const start = toISOFromDatetimeLocal(qs("fStart").value);
  const end = toISOFromDatetimeLocal(qs("fEnd").value);
  const direction = qs("fDirection").value;
  const min_value = qs("fMinValue").value ? Number(qs("fMinValue").value) : null;
  const confirmed = qs("fConfirmed").value; // "", "true", "false"
  return { start, end, direction, min_value, confirmed };
}

function resetFiltersUI(){
  qs("fStart").value = "";
  qs("fEnd").value = "";
  qs("fDirection").value = "";
  qs("fMinValue").value = "";
  qs("fConfirmed").value = "";
}

function currentCommonParams(){
  const f = state.filters;
  return {
    start: f.start,
    end: f.end,
    direction: f.direction,
    min_value: f.min_value,
    confirmed: (f.confirmed === "" || f.confirmed === undefined) ? null : f.confirmed
  };
}

function destroyChart(ch){ if(ch) ch.destroy(); }

function animateCounter(el, toValue, formatter=numberFmt, ms=550){
  const fromText = el.dataset.prev || "0";
  const from = Number(fromText.replace(/\s/g,'').replace(',','.')) || 0;
  const to = Number(toValue) || 0;
  const t0 = performance.now();

  function step(t){
    const p = Math.min(1, (t - t0)/ms);
    const v = from + (to - from) * (1 - Math.pow(1-p, 3));
    el.textContent = formatter(v);
    if(p < 1) requestAnimationFrame(step);
    else {
      el.textContent = formatter(to);
      el.dataset.prev = String(to);
    }
  }
  requestAnimationFrame(step);
}

// ---------- Delta helpers ----------
function pctDelta(curr, prev){
  const c = Number(curr) || 0;
  const p = Number(prev) || 0;
  if(p === 0 && c === 0) return { text: "Δ: 0%", cls: "" };
  if(p === 0) return { text: "Δ: +∞", cls: "up" };
  const pct = ((c - p) / p) * 100;
  const sign = pct >= 0 ? "+" : "";
  const cls = pct > 0 ? "up" : (pct < 0 ? "down" : "");
  return { text: `Δ: ${sign}${pct.toFixed(1)}%`, cls };
}

function setDelta(el, curr, prev){
  const d = pctDelta(curr, prev);
  el.textContent = d.text;
  el.classList.remove("up","down");
  if(d.cls) el.classList.add(d.cls);
}

function computePeriodWindow(){
  // Якщо задано start/end -> порівнюємо з попереднім періодом такої ж довжини.
  // Якщо ні -> беремо останні 7 днів vs попередні 7 днів.
  const now = new Date();
  const f = state.filters;

  let start = f.start ? new Date(f.start) : null;
  let end = f.end ? new Date(f.end) : null;

  if(!end) end = now;
  if(!start){
    start = new Date(end.getTime() - 7*24*3600*1000);
  }

  // попередній період
  const len = end.getTime() - start.getTime();
  const prevEnd = new Date(start.getTime());
  const prevStart = new Date(start.getTime() - len);

  return {
    curr: { start: start.toISOString(), end: end.toISOString() },
    prev: { start: prevStart.toISOString(), end: prevEnd.toISOString() }
  };
}

// ---------- Charts ----------
function renderTrend(points){
  const labels = points.map(p => p.bucket_start);
  const counts = points.map(p => p.events_count);
  const sums = points.map(p => p.amount_sum);

  const ctx = qs("trendChart").getContext("2d");
  destroyChart(charts.trend);

  charts.trend = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "К-сть подій", data: counts, tension: 0.25 },
        { label: "Сума amount", data: sums, tension: 0.25 }
      ]
    },
    options: {
      responsive: true,
      animation: { duration: 650 },
      interaction: { mode: "index", intersect: false },
      scales: { y: { beginAtZero: true } }
    }
  });
}

function renderBar(canvasId, title, items){
  const labels = items.map(x => x.category);
  const data = items.map(x => x.events_count);

  const ctx = qs(canvasId).getContext("2d");
  const prev = (canvasId === "dirChart") ? charts.dir : charts.unit;
  destroyChart(prev);

  const ch = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [{ label: title, data }] },
    options: { responsive: true, animation: { duration: 650 }, scales: { y: { beginAtZero: true } } }
  });

  if(canvasId === "dirChart") charts.dir = ch;
  else charts.unit = ch;
}

// ---------- Heatmap ----------
function lerp(a,b,t){ return a + (b-a)*t; }

function valueToColor(v, vmin, vmax){
  if(vmax <= vmin) return "rgba(122,162,255,.15)";
  const t = (v - vmin) / (vmax - vmin);
  const alpha = lerp(0.10, 0.90, Math.max(0, Math.min(1, t)));
  return `rgba(122,162,255,${alpha})`;
}

function renderHeatmap(data){
  const wrap = qs("heatmap");
  wrap.innerHTML = "";

  const rts = data.resource_types;
  const weeks = data.weeks;
  const m = data.matrix;

  if(!rts.length || !weeks.length){
    wrap.textContent = "Немає даних для heatmap";
    qs("heatLegend").textContent = "";
    return;
  }

  let vmin = Infinity, vmax = -Infinity;
  for(const row of m) for(const v of row){ vmin = Math.min(vmin, v); vmax = Math.max(vmax, v); }

  const grid = document.createElement("div");
  grid.className = "hmGrid";
  grid.style.gridTemplateColumns = `180px repeat(${weeks.length}, 22px)`;

  const corner = document.createElement("div");
  corner.className = "hmLabel";
  corner.textContent = "resource_type \\ week";
  grid.appendChild(corner);

  for(const w of weeks){
    const lbl = document.createElement("div");
    lbl.className = "hmLabel";
    lbl.style.writingMode = "vertical-rl";
    lbl.style.transform = "rotate(180deg)";
    lbl.style.textAlign = "center";
    lbl.textContent = w;
    grid.appendChild(lbl);
  }

  for(let i=0;i<rts.length;i++){
    const rlbl = document.createElement("div");
    rlbl.className = "hmLabel";
    rlbl.textContent = rts[i];
    grid.appendChild(rlbl);

    for(let j=0;j<weeks.length;j++){
      const v = m[i][j];
      const cell = document.createElement("div");
      cell.className = "hmCell";
      cell.title = `${rts[i]} / ${weeks[j]}: ${numberFmt(v)}`;
      cell.style.background = valueToColor(v, vmin, vmax);
      grid.appendChild(cell);
    }
  }

  wrap.appendChild(grid);
  qs("heatLegend").textContent = `min=${numberFmt(vmin)}  max=${numberFmt(vmax)} (сума amount)`;
}

// ---------- Table / Modal ----------
async function openDetails(id){
  const data = await apiGet(`/allocations/${id}`);
  qs("modalTitle").textContent = `Подія #${data.id}`;
  qs("modalBody").textContent = JSON.stringify(data, null, 2);
  qs("modalBackdrop").classList.remove("hidden");
}
function closeModal(){ qs("modalBackdrop").classList.add("hidden"); }

function renderTable(page){
  const tb = qs("tbody");
  tb.innerHTML = "";

  for(const it of page.items){
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${it.id}</td>
      <td>${new Date(it.occurred_at).toLocaleString("uk-UA")}</td>
      <td>${it.direction}</td>
      <td>${it.resource_type}</td>
      <td>${it.unit}</td>
      <td>${numberFmt(it.amount)}</td>
      <td>${numberFmt(it.duration_days)}</td>
      <td>${it.confirmed ? "true" : "false"}</td>
    `;
    tr.addEventListener("click", () => openDetails(it.id));
    tb.appendChild(tr);
  }

  const from = state.offset + 1;
  const to = Math.min(state.offset + state.limit, page.total);
  qs("pageInfo").textContent = `${from}-${to} з ${page.total}`;

  qs("btnPrev").disabled = state.offset === 0;
  qs("btnNext").disabled = (state.offset + state.limit) >= page.total;
}

// ---------- Map ----------
function initMap(){
  map = L.map("map", { zoomControl: true }).setView([48.6, 31.3], 6);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);

  qs("mapHint").textContent = "Порада: клік по точці показує короткі деталі.";
}

function clearMapMarkers(){
  for(const m of mapMarkers){ m.remove(); }
  mapMarkers = [];
}

function colorByType(rt){
  let h = 0;
  for(let i=0;i<rt.length;i++) h = (h*31 + rt.charCodeAt(i)) % 360;
  return `hsl(${h} 80% 60%)`;
}

async function loadMap(common){
  const pts = await apiGet("/map_points", { ...common, limit: 350 });
  clearMapMarkers();

  if(!pts.length){
    qs("mapHint").textContent = "Немає точок для поточних фільтрів.";
    return;
  }

  const bounds = [];
  for(const p of pts){
    const radius = Math.max(4, Math.min(18, Math.sqrt(Number(p.amount || 0)) / 3));
    const marker = L.circleMarker([p.lat, p.lon], {
      radius,
      color: colorByType(p.resource_type),
      weight: 2,
      fillOpacity: p.confirmed ? 0.55 : 0.25
    }).addTo(map);

    marker.bindPopup(`
      <b>#${p.id}</b><br/>
      ${new Date(p.occurred_at).toLocaleString("uk-UA")}<br/>
      <b>${p.direction}</b> • ${p.resource_type}<br/>
      ${p.unit}<br/>
      amount: <b>${numberFmt(p.amount)}</b><br/>
      confirmed: ${p.confirmed ? "true" : "false"}
    `);

    mapMarkers.push(marker);
    bounds.push([p.lat, p.lon]);
  }

  try{
    map.fitBounds(bounds, { padding: [18, 18], maxZoom: 9 });
  }catch(_e){}

  qs("mapHint").textContent = `Показано точок: ${pts.length}`;
}

// ---------- Reveal ----------
function setupReveal(){
  const els = document.querySelectorAll(".reveal");
  const io = new IntersectionObserver((entries)=>{
    for(const e of entries){
      if(e.isIntersecting){
        e.target.classList.add("on");
        io.unobserve(e.target);
      }
    }
  }, { threshold: 0.08 });
  els.forEach(el => io.observe(el));
}

// ---------- Fullscreen ----------
function isFullscreen(){ return !!document.fullscreenElement; }

async function toggleFullscreen(){
  try{
    if(!isFullscreen()) await document.documentElement.requestFullscreen();
    else await document.exitFullscreen();
  }catch(e){
    console.error(e);
    alert("Fullscreen недоступний у цьому браузері/налаштуваннях.");
  }
}

function syncFullscreenButton(){
  const b = qs("btnFullscreen");
  if(!b) return;
  b.textContent = isFullscreen() ? "⤫ Exit full screen" : "⛶ Full screen";
}

// ---------- Last updated label ----------
function setLastUpdatedNow(){
  lastUpdatedAt = new Date();
  qs("lastUpdated").textContent = `оновлення: щойно`;
}

function startLastUpdatedTicker(){
  setInterval(() => {
    if(!lastUpdatedAt) return;
    const s = Math.floor((Date.now() - lastUpdatedAt.getTime())/1000);
    qs("lastUpdated").textContent = `оновлення: ${s}s тому`;
  }, 1000);
}

// ---------- Live mode ----------
function stopLive(){
  if(liveTimer) clearInterval(liveTimer);
  liveTimer = null;
}

function startLive(){
  stopLive();
  const sec = Number(qs("liveInterval").value || 20);
  liveTimer = setInterval(async () => {
    try{
      await loadAll(false);
    }catch(e){
      console.error(e);
      // якщо API впало — просто не зупиняємо, але покажемо статус
      setStatus(false);
    }
  }, sec * 1000);
}

// ---------- Load all ----------
async function loadAll(showToastAfter=false){
  const common = currentCommonParams();

  // KPI (current + prev period) for deltas
  const win = computePeriodWindow();
  const kpiCurr = await apiGet("/kpi", { ...common, start: win.curr.start, end: win.curr.end });
  const kpiPrev = await apiGet("/kpi", { ...common, start: win.prev.start, end: win.prev.end });

  animateCounter(qs("kpiCount"), kpiCurr.events_count, (v)=>numberFmt(Math.round(v)));
  animateCounter(qs("kpiAmountSum"), kpiCurr.amount_sum, numberFmt);
  animateCounter(qs("kpiDurationAvg"), kpiCurr.duration_avg, numberFmt);
  qs("kpiTopType").textContent = kpiCurr.top_resource_type ?? "—";

  setDelta(qs("kpiCountDelta"), kpiCurr.events_count, kpiPrev.events_count);
  setDelta(qs("kpiAmountSumDelta"), kpiCurr.amount_sum, kpiPrev.amount_sum);
  setDelta(qs("kpiDurationAvgDelta"), kpiCurr.duration_avg, kpiPrev.duration_avg);

  // top type delta (text-only)
  const topDelta = qs("kpiTopTypeDelta");
  const prevTop = kpiPrev.top_resource_type ?? "—";
  const currTop = kpiCurr.top_resource_type ?? "—";
  topDelta.textContent = (prevTop === currTop) ? `Δ: без змін` : `Δ: було "${prevTop}"`;

  // Trend / distributions / heatmap / table / map
  const trend = await apiGet("/trend", { ...common, bucket: state.bucket });
  renderTrend(trend);

  const distDir = await apiGet("/distribution/direction", common);
  renderBar("dirChart", "К-сть подій", distDir);

  const distUnit = await apiGet("/distribution/unit", common);
  renderBar("unitChart", "К-сть подій", distUnit);

  const hm = await apiGet("/heatmap", { ...common, metric: "amount_sum" });
  renderHeatmap(hm);

  const page = await apiGet("/allocations", { ...common, limit: state.limit, offset: state.offset });
  renderTable(page);

  await loadMap(common);

  setLastUpdatedNow();
  if(showToastAfter) showToast("Оновлено");
}

async function init(){
  setupReveal();
  initMap();
  startLastUpdatedTicker();

  // Fullscreen
  qs("btnFullscreen").addEventListener("click", toggleFullscreen);
  document.addEventListener("fullscreenchange", () => {
    syncFullscreenButton();
    if(map) setTimeout(() => map.invalidateSize(), 150);
  });
  syncFullscreenButton();

  // Health
  try{
    await apiGet("/health");
    setStatus(true);
  }catch(e){
    console.error(e);
    setStatus(false);
  }

  // Live controls
  qs("liveToggle").addEventListener("change", () => {
    if(qs("liveToggle").checked) startLive();
    else stopLive();
  });
  qs("liveInterval").addEventListener("change", () => {
    if(qs("liveToggle").checked) startLive();
  });
  qs("btnRefresh").addEventListener("click", async () => {
    await loadAll(true);
  });

  // Filters
  qs("btnApply").addEventListener("click", async () => {
    state.filters = readFilters();
    state.offset = 0;
    await loadAll(true);
  });

  qs("btnReset").addEventListener("click", async () => {
    resetFiltersUI();
    state.filters = readFilters();
    state.offset = 0;
    await loadAll(true);
  });

  // Pagination
  qs("btnPrev").addEventListener("click", async () => {
    state.offset = Math.max(0, state.offset - state.limit);
    await loadAll(false);
  });

  qs("btnNext").addEventListener("click", async () => {
    state.offset = state.offset + state.limit;
    await loadAll(false);
  });

  // Trend toggle
  qs("btnDay").addEventListener("click", async () => {
    state.bucket = "day";
    qs("btnDay").classList.add("active");
    qs("btnWeek").classList.remove("active");
    await loadAll(true);
  });

  qs("btnWeek").addEventListener("click", async () => {
    state.bucket = "week";
    qs("btnWeek").classList.add("active");
    qs("btnDay").classList.remove("active");
    await loadAll(true);
  });

  // Modal
  qs("btnClose").addEventListener("click", () => qs("modalBackdrop").classList.add("hidden"));
  qs("modalBackdrop").addEventListener("click", (e) => {
    if(e.target.id === "modalBackdrop") qs("modalBackdrop").classList.add("hidden");
  });

  // initial
  state.filters = readFilters();
  await loadAll(false);
}

init().catch(err => {
  console.error(err);
  setStatus(false);
  alert("Помилка завантаження даних. Перевір API та консоль.");
});
