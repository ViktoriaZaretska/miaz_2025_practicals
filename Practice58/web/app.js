const API = "http://127.0.0.1:8000";

Chart.register(ChartDataLabels);

const COLORS = {
  cyan:  "rgba(0, 210, 255, 0.85)",
  purple:"rgba(140, 110, 255, 0.85)",
  amber: "rgba(255, 210, 80, 0.90)",
  green: "rgba(0, 255, 170, 0.80)",
  red:   "rgba(255, 80, 90, 0.85)",
  gray:  "rgba(150, 170, 210, 0.35)",
};

Chart.defaults.color = "rgba(234,240,255,0.90)";
Chart.defaults.font.family = "system-ui, Segoe UI, Arial";
Chart.defaults.plugins.legend.labels.boxWidth = 10;

let cycleWeekChart, flowWeekChart, workedChart, unitBarChart, ringChart;

function el(tag, attrs={}) {
  const e = document.createElement(tag);
  Object.entries(attrs).forEach(([k,v]) => e[k]=v);
  return e;
}
function clamp(n, a, b){ return Math.max(a, Math.min(b, n)); }

function fmtHMFromMinutes(mins){
  if (mins === null || mins === undefined || isNaN(Number(mins))) return "—";
  const m = Math.max(0, Math.round(Number(mins)));
  const h = Math.floor(m / 60);
  const mm = String(m % 60).padStart(2, "0");
  return `${h}:${mm}`;
}
function fmtHumanHM(mins){
  if (mins === null || mins === undefined || isNaN(Number(mins))) return "—";
  const m = Math.max(0, Math.round(Number(mins)));
  const h = Math.floor(m / 60);
  const mm = m % 60;
  if (h <= 0) return `${mm} хв`;
  return `${h} год ${mm} хв`;
}

function setKpiClass(node, state){
  node.classList.remove("good","warn","bad");
  node.classList.add(state);
}
function statusBadgeClass(status){
  if (status === "прострочено") return "s_bad";
  if (status === "в_роботі" || status === "отримано") return "s_warn";
  return "s_good";
}

/* ===== IOI ===== */
function computeIOI(kpi, totalDocs7){
  const oper = clamp(Number(kpi.operativity_percent ?? 0), 0, 100);
  const avg = Number(kpi.avg_cycle_minutes ?? 0);
  const timeScore = clamp(100 - ((avg - 30) * (100 / 210)), 0, 100);

  const overdue = Number(kpi.overdue_docs ?? 0);
  const overdueRate = totalDocs7 > 0 ? (overdue / totalDocs7) : 0;
  const overdueScore = clamp(100 - overdueRate * 200, 0, 100);

  return Math.round(0.5*oper + 0.3*timeScore + 0.2*overdueScore);
}
function ioiHintText(ioi){
  if (ioi >= 85) return "Стан стабільний: обіг інформації контрольований.";
  if (ioi >= 70) return "Є ризики: перевірити вузькі місця та пріоритети.";
  return "Критично: обіг інформації сповільнений, потрібні дії керівника.";
}

function ensureRing(value){
  const ctx = document.getElementById("ioiRing");
  const v = clamp(value, 0, 100);
  if (ringChart) ringChart.destroy();

  ringChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      datasets: [{
        data: [v, 100 - v],
        backgroundColor: [
          v >= 85 ? COLORS.green : (v >= 70 ? COLORS.amber : COLORS.red),
          COLORS.gray
        ],
        borderWidth: 0,
        cutout: "78%"
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display:false }, tooltip:{ enabled:false }, datalabels:{ display:false } },
      animation: { duration: 500 }
    }
  });
}

/* ===== filters ===== */
function getParams() {
  const p = new URLSearchParams();
  ["date_from","date_to","unit_id","sector_id","doc_type_id","status","priority"].forEach(id=>{
    const v = document.getElementById(id)?.value;
    if (v) p.set(id, v);
  });
  return p;
}

async function loadFilters() {
  const r = await fetch(`${API}/api/filters`);
  const data = await r.json();

  const wrap = document.getElementById("filters");
  wrap.innerHTML = "";

  wrap.appendChild(el("input", { id:"date_from", type:"datetime-local" }));
  wrap.appendChild(el("input", { id:"date_to", type:"datetime-local" }));

  const unit = el("select", { id:"unit_id" });
  unit.appendChild(new Option("Підрозділ: всі", ""));
  data.units.forEach(u => unit.appendChild(new Option(u.code, u.unit_id)));
  wrap.appendChild(unit);

  const sector = el("select", { id:"sector_id" });
  sector.appendChild(new Option("Сектор: всі", ""));
  data.sectors.forEach(s => sector.appendChild(new Option(s.name, s.sector_id)));
  wrap.appendChild(sector);

  const type = el("select", { id:"doc_type_id" });
  type.appendChild(new Option("Тип: всі", ""));
  data.types.forEach(t => type.appendChild(new Option(t.code, t.doc_type_id)));
  wrap.appendChild(type);

  const status = el("select", { id:"status" });
  status.appendChild(new Option("Статус: всі", ""));
  ["отримано","в_роботі","доведено","прострочено"].forEach(s => status.appendChild(new Option(s, s)));
  wrap.appendChild(status);

  const priority = el("select", { id:"priority" });
  priority.appendChild(new Option("Пріоритет: всі", ""));
  ["1","2","3"].forEach(p => priority.appendChild(new Option(p, p)));
  wrap.appendChild(priority);

  wrap.querySelectorAll("input,select").forEach(x => x.addEventListener("change", refreshAll));

  document.getElementById("btnRefresh").addEventListener("click", refreshAll);
  document.getElementById("btnFullscreen").addEventListener("click", () => {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
    else document.exitFullscreen?.();
  });

  document.getElementById("q").addEventListener("input", () => renderFeedCache());
  document.getElementById("feedLimit").addEventListener("change", refreshFeedOnly);
}

/* ===== API loaders ===== */
const parseJSON = r => r.json();
async function loadKPI() {
  const p = getParams();
  return parseJSON(await fetch(`${API}/api/kpi?${p.toString()}`));
}
async function loadWeekDynamics() {
  const p = getParams();
  return parseJSON(await fetch(`${API}/api/week_dynamics?${p.toString()}`));
}
async function loadWorkedDocs() {
  const p = getParams();
  const d = await parseJSON(await fetch(`${API}/api/worked_docs?${p.toString()}`));
  return d.rows;
}
async function loadDocsByUnit() {
  const p = getParams();
  const d = await parseJSON(await fetch(`${API}/api/docs_by_unit?${p.toString()}`));
  return d.rows;
}
async function loadControlBoard(){
  return parseJSON(await fetch(`${API}/api/control_board`));
}

/* ===== datalabel presets ===== */
const dlBar = {
  anchor: "end", align: "end", offset: 2,
  color: "rgba(234,240,255,0.92)",
  font: { size: 10, weight: "800" },
  formatter: (v) => (v === null || v === undefined) ? "" : v
};
const dlLine = {
  align: "top", anchor: "end", offset: 2,
  color: "rgba(234,240,255,0.92)",
  font: { size: 10, weight: "800" },
  formatter: (v) => (v === null || v === undefined) ? "" : fmtHMFromMinutes(v)
};

/* ===== charts ===== */
async function paintWeekCharts(d){
  document.getElementById("rangeStamp").textContent = `${d.range.start} → ${d.range.end}`;

  const labels = d.cycle.map(x => new Date(x.day).toLocaleDateString("uk-UA", { day:"2-digit", month:"2-digit" }));
  const avgCycle = d.cycle.map(x => x.avg_cycle_minutes ?? null);
  const totalDocs = d.cycle.map(x => x.total_docs);

  const ctx1 = document.getElementById("cycleWeek");
  if (cycleWeekChart) cycleWeekChart.destroy();
  cycleWeekChart = new Chart(ctx1, {
    data: {
      labels,
      datasets: [
        {
          type:"line",
          label:"T̄ (год:хв)",
          data: avgCycle,
          tension:0.25,
          borderColor: COLORS.cyan,
          backgroundColor: "rgba(0,210,255,0.15)",
          pointBackgroundColor: COLORS.cyan,
          pointRadius: 3,
          datalabels: dlLine
        },
        {
          type:"bar",
          label:"Обсяг",
          data: totalDocs,
          backgroundColor: COLORS.purple,
          borderRadius: 8,
          datalabels: dlBar
        }
      ]
    },
    options: {
      responsive:true,
      animation:{ duration:500 },
      plugins:{
        legend:{ labels:{ boxWidth:10 } },
        tooltip:{
          callbacks:{
            label:(ctx)=>{
              if (ctx.dataset.type === "line"){
                return ` ${ctx.dataset.label}: ${fmtHumanHM(ctx.raw)}`;
              }
              return ` ${ctx.dataset.label}: ${ctx.raw}`;
            }
          }
        },
        datalabels:{ display:true }
      },
      scales:{
        x:{ grid:{ display:false } },
        y:{ grid:{ color:"rgba(28,42,82,0.35)" }, ticks:{ precision:0 } }
      }
    }
  });

  const flowLabels = d.flow.map(x => new Date(x.day).toLocaleDateString("uk-UA", { day:"2-digit", month:"2-digit" }));
  const received = d.flow.map(x => x.received);
  const processed = d.flow.map(x => x.processed);
  const delivered = d.flow.map(x => x.delivered);

  const ctx2 = document.getElementById("flowWeek");
  if (flowWeekChart) flowWeekChart.destroy();
  flowWeekChart = new Chart(ctx2, {
    type:"bar",
    data:{
      labels: flowLabels,
      datasets:[
        { label:"Отримано", data: received, backgroundColor: COLORS.cyan, borderRadius: 8, datalabels: dlBar },
        { label:"Опрацьовано", data: processed, backgroundColor: COLORS.amber, borderRadius: 8, datalabels: dlBar },
        { label:"Доведено", data: delivered, backgroundColor: COLORS.green, borderRadius: 8, datalabels: dlBar }
      ]
    },
    options:{
      responsive:true,
      animation:{ duration:500 },
      plugins:{ legend:{ labels:{ boxWidth:10 } }, datalabels:{ display:true } },
      scales:{ x:{ grid:{ display:false } }, y:{ grid:{ color:"rgba(28,42,82,0.35)" }, ticks:{ precision:0 } } }
    }
  });

  const totalDocs7 = totalDocs.reduce((a,b)=>a+(Number(b)||0), 0);
  return { totalDocs7 };
}

async function paintWorked(rows){
  const labels = rows.map(x => x.doc_type);
  const received = rows.map(x => x.received);
  const processed = rows.map(x => x.processed);
  const delivered = rows.map(x => x.delivered);

  const ctx = document.getElementById("workedChart");
  if (workedChart) workedChart.destroy();
  workedChart = new Chart(ctx, {
    type:"bar",
    data:{
      labels,
      datasets:[
        { label:"Отримано", data: received, backgroundColor: COLORS.cyan, borderRadius: 8, datalabels: dlBar },
        { label:"Опрацьовано", data: processed, backgroundColor: COLORS.amber, borderRadius: 8, datalabels: dlBar },
        { label:"Доведено", data: delivered, backgroundColor: COLORS.green, borderRadius: 8, datalabels: dlBar }
      ]
    },
    options:{
      responsive:true,
      animation:{ duration:450 },
      plugins:{ legend:{ labels:{ boxWidth:10 } }, datalabels:{ display:true } },
      scales:{ x:{ grid:{ display:false } }, y:{ grid:{ color:"rgba(28,42,82,0.35)" }, ticks:{ precision:0 } } }
    }
  });
}

async function paintUnitBar(rows){
  const total = rows.reduce((a,r)=>a+Number(r.cnt||0),0) || 1;
  const sorted = [...rows].sort((a,b)=>Number(b.cnt)-Number(a.cnt));

  const labels = sorted.map(r => r.unit);
  const counts = sorted.map(r => Number(r.cnt||0));
  const perc = sorted.map(r => Math.round((Number(r.cnt||0)/total)*100));

  const ctx = document.getElementById("unitBar");
  if (unitBarChart) unitBarChart.destroy();

  unitBarChart = new Chart(ctx, {
    type:"bar",
    data:{
      labels,
      datasets:[
        {
          label:"% частки",
          data: perc,
          backgroundColor: COLORS.purple,
          borderRadius: 10,
          datalabels:{
            anchor:"end",
            align:"end",
            offset: 2,
            color:"rgba(234,240,255,0.92)",
            font:{ size:10, weight:"900" },
            formatter:(v, ctx)=>{
              const i = ctx.dataIndex;
              return `${v}% (${counts[i]})`;
            }
          }
        }
      ]
    },
    options:{
      indexAxis:"y",
      responsive:true,
      animation:{ duration:450 },
      plugins:{ legend:{ display:false }, datalabels:{ display:true } },
      scales:{
        x:{ min:0, max:100, grid:{ color:"rgba(28,42,82,0.35)" }, ticks:{ callback:(v)=>`${v}%` } },
        y:{ grid:{ display:false } }
      }
    }
  });
}

/* ===== FEED ===== */
let feedCache = [];
function renderFeedCache(){
  const q = (document.getElementById("q").value || "").trim().toLowerCase();
  let rows = feedCache;

  if (q){
    rows = rows.filter(x => {
      const t = `${x.unit} ${x.doc_type} ${x.status} ${x.priority} ${(x.title||"")}`.toLowerCase();
      return t.includes(q);
    });
  }

  const tb = document.querySelector("#docsTable tbody");
  tb.innerHTML = "";
  rows.forEach(x => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${new Date(x.doc_date).toLocaleString("uk-UA")}</td>
      <td><b>${x.unit}</b></td>
      <td>${x.doc_type}</td>
      <td><span class="rowStatus ${statusBadgeClass(x.status)}">${x.status}</span></td>
      <td>${x.priority ?? "—"}</td>
      <td>${fmtHMFromMinutes(x.cycle_minutes)}</td>
      <td>${(x.title ?? "").slice(0,140)}</td>
    `;
    tb.appendChild(tr);
  });
}
async function refreshFeedOnly(){
  const p = getParams();
  const limit = document.getElementById("feedLimit").value || "100";
  p.set("limit", limit);

  const r = await fetch(`${API}/api/documents?${p.toString()}`);
  const d = await r.json();
  feedCache = d.rows || [];
  renderFeedCache();
}

/* ===== TIME BOX (тільки 2 рядки як попросив) ===== */
const FIXED_ASTRO_DATE = "2025-12-18";
const FIXED_OP_DATE = "2025-03-05";

function renderTimeBoxMinimal(){
  const timeBox = document.getElementById("timeBox");
  timeBox.innerHTML = `
    <div class="timeRow">
      <div class="timeLabel">Астрономічний час</div>
      <div class="timeValue">${FIXED_ASTRO_DATE}</div>
    </div>
    <div class="timeRow">
      <div class="timeLabel">Оперативний час</div>
      <div class="timeValue">${FIXED_OP_DATE}</div>
    </div>
  `;
}

/* ===== CONTROL TABLE (Док + Контр + Статус) ===== */
function stClass(status){
  if (status === "виконано") return "ok";
  if (status === "в роботі" || status === "очікується") return "warn";
  if (status === "прострочено") return "bad";
  return "gray";
}

function renderControlTable(cb){
  const tb = document.querySelector("#ctrlTable tbody");
  tb.innerHTML = "";

  (cb.items || []).forEach(x => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><b>${x.doc}</b></td>
      <td>${x.due}</td>
      <td><span class="st ${stClass(x.status)}">${x.status}</span></td>
    `;
    tr.title = x.detail || "";
    tb.appendChild(tr);
  });
}

/* ===== refresh ===== */
function applyKpiVisuals(kpi, totalDocs7){
  document.querySelector("#kpiOper .kpiVal").textContent = `${kpi.operativity_percent ?? 0}%`;
  document.querySelector("#kpiAvg .kpiVal").textContent  = fmtHMFromMinutes(kpi.avg_cycle_minutes);
  document.querySelector("#kpiOver .kpiVal").textContent = `${kpi.overdue_docs ?? 0}`;
  document.querySelector("#kpiVol .kpiVal").textContent  = `${totalDocs7 ?? 0}`;

  const oper = Number(kpi.operativity_percent ?? 0);
  const avg  = Number(kpi.avg_cycle_minutes ?? 9999);
  const over = Number(kpi.overdue_docs ?? 0);

  setKpiClass(document.getElementById("kpiOper"), oper >= 90 ? "good" : oper >= 75 ? "warn" : "bad");
  setKpiClass(document.getElementById("kpiAvg"),  avg <= 60 ? "good" : avg <= 180 ? "warn" : "bad");
  setKpiClass(document.getElementById("kpiOver"), over <= 2 ? "good" : over <= 8 ? "warn" : "bad");
  setKpiClass(document.getElementById("kpiVol"),  (totalDocs7 ?? 0) >= 1 ? "good" : "warn");
}

async function refreshAll() {
  const [kpi, week, workedRows, unitRows, cb] = await Promise.all([
    loadKPI(),
    loadWeekDynamics(),
    loadWorkedDocs(),
    loadDocsByUnit(),
    loadControlBoard()
  ]);

  renderTimeBoxMinimal();
  renderControlTable(cb);

  const flow7 = await paintWeekCharts(week);

  const ioi = computeIOI(kpi, flow7.totalDocs7);
  document.getElementById("ioiValue").textContent = String(ioi);
  document.getElementById("ioiHint").textContent = ioiHintText(ioi);
  ensureRing(ioi);

  applyKpiVisuals(kpi, flow7.totalDocs7);

  await paintWorked(workedRows);
  await paintUnitBar(unitRows);

  await refreshFeedOnly();
}

/* ===== init ===== */
(async function init(){
  await loadFilters();
  await refreshAll();
  setInterval(refreshAll, 30000);
})();
