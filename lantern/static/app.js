const $ = (id) => document.getElementById(id);
const query = (params) => new URLSearchParams(Object.entries(params).flatMap(([k, v]) => [v].flat().filter(Boolean).map((x) => [k, x]))).toString();
let files = [];
let plots = [];
let names = {};
let runs = [];
let current = null;
let panels = [];
let cells = [];
let requests = 0;
let offline = false;
let checking = false;

async function api(path, options) {
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error);
  return body;
}

const allRuns = () => files.flatMap((file) => file.runs);

async function load(state) {
  files = state.files;
  names = state.names;
  const kept = runs.filter((id) => allRuns().includes(id));
  await select(kept.length ? kept : allRuns().slice(0, 1));
}

async function select(next) {
  runs = allRuns().filter((id) => next.includes(id));
  plots = runs.length ? await api(`/api/catalogue?${query({ run: runs })}`) : [];
  render();
}

function pick(id, event) {
  if (!(event.ctrlKey || event.metaKey)) return select([id]);
  const next = runs.includes(id) ? runs.filter((r) => r !== id) : [...runs, id];
  if (next.length) select(next);
}

async function upload(list) {
  const errors = [];
  let state = null;

  for (const file of [...list].filter((f) => f.name.endsWith(".parquet"))) {
    const name = file.name.replace(/\.parquet$/, "");

    try {
      state = await api("/api/files", { method: "POST", headers: { "X-Filename": encodeURIComponent(name) }, body: file });
    } catch (error) {
      errors.push(error.message);
    }
  }

  $("message").textContent = errors.join(" ");
  if (state) await load(state);
}

async function check() {
  if (checking) return;
  checking = true;

  try {
    const state = await api("/api/state");
    if (offline) await load(state);
    offline = false;
  } catch {
    offline = true;
  } finally {
    checking = false;
  }

  $("offline").hidden = !offline;
}

function light(color) {
  const hex = color.length === 4 ? [...color.slice(1)].map((c) => c + c).join("") : color.slice(1);
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return 0.299 * r + 0.587 * g + 0.114 * b > 160;
}

function runButton(id, text) {
  const title = `${text}\nCtrl-click to compare it with the selected runs`;
  const button = Object.assign(document.createElement("button"), { textContent: text, title, className: "run" });
  button.classList.toggle("active", runs.includes(id));
  button.dataset.id = id;
  button.onclick = (event) => pick(id, event);
  return button;
}

function render() {
  $("runs").replaceChildren(...files.map((file) => {
    const item = document.createElement("li");
    const head = document.createElement("div");
    const remove = Object.assign(document.createElement("button"), { textContent: "×", title: `Unload ${file.name}`, className: "remove" });
    remove.onclick = async () => load(await api(`/api/files/${encodeURIComponent(file.name)}`, { method: "DELETE" }));

    if (file.compiled) {
      const tag = Object.assign(document.createElement("small"), { textContent: "compiled" });
      item.className = "compiled";
      head.append(tag, Object.assign(document.createElement("span"), { textContent: file.name, title: file.name }), remove);
      item.append(head, ...file.runs.map((id) => runButton(id, names[id])));
    } else {
      head.append(runButton(file.runs[0], names[file.runs[0]]), remove);
      item.append(head);
    }

    return item;
  }));

  const list = $("plots");
  list.replaceChildren();
  let section = null;

  for (const plot of plots) {
    if (plot.section !== section) {
      section = plot.section;
      list.append(Object.assign(document.createElement("h4"), { textContent: section }));
    }

    const button = Object.assign(document.createElement("button"), { textContent: plot.title, disabled: !plot.available });
    button.dataset.id = plot.id;
    button.onclick = () => show(plot.id);
    list.append(button);
  }

  $("empty").hidden = runs.length > 0;
  $("toolbar").hidden = !runs.length;

  if (!runs.length) {
    Plotly.purge($("figure"));
    $("figure").style.minHeight = "";
    return;
  }

  const available = plots.filter((p) => p.available);
  const next = available.find((p) => p.id === current) || available[0];
  if (next) show(next.id, $("view").value, $("panel").value || null);
}

async function show(id, view, panel = null) {
  const plot = plots.find((p) => p.id === id);
  const request = ++requests;
  current = id;
  view = plot.views.some(([value]) => value === view) ? view : plot.views[0]?.[0];

  for (const button of $("plots").querySelectorAll("button")) button.classList.toggle("active", button.dataset.id === id);
  $("title").textContent = plot.title;
  $("view").hidden = !plot.views.length;
  $("view").replaceChildren(...plot.views.map(([value, title]) => new Option(title, value, false, value === view)));

  const params = query({ run: runs, view, panel });
  const figure = await api(`/api/plots/${encodeURIComponent(id)}?${params}`);
  if (request !== requests) return; // only the latest request is drawn
  ({ panels, cells } = figure.layout.meta);
  if (!panels.some(([value]) => value === panel)) panel = null;

  for (const button of $("runs").querySelectorAll(".run")) {
    const color = figure.layout.meta.colors[button.dataset.id];
    button.classList.toggle("colored", Boolean(color));
    button.style.setProperty("--color", color || "");
    button.style.setProperty("--text", color && light(color) ? "#1d2327" : "#fff");
  }

  $("panel").hidden = panels.length < 2;
  $("panel").replaceChildren(new Option("All panels", ""), ...panels.map(([value, title]) => new Option(title, value, false, value === panel)));

  // a panel grid taller than the window keeps its height and scrolls
  $("figure").style.minHeight = `${figure.layout.height}px`;
  Object.assign(figure.layout, size(), dark() ? darkLayout(figure.layout) : {});
  // a redraw of the same view keeps the zoom
  figure.layout.uirevision = JSON.stringify([id, runs, view, panel, syncedY]);
  const config = {
    displaylogo: false, toImageButtonOptions: { filename: id, scale: 2 },
    modeBarButtons: modebarButtons(id, params, figure.layout, () => show(id, view, panel)),
  };
  await Plotly.react($("figure"), figure.data, figure.layout, config);
  $("figure").removeAllListeners("plotly_click");
  if (!panel && panels.length > 1) $("figure").on("plotly_click", enlarge);
}

const systemDark = matchMedia("(prefers-color-scheme: dark)");
const dark = () => document.documentElement.dataset.theme === "dark" || (document.documentElement.dataset.theme !== "bright" && systemDark.matches);

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;

  try {
    localStorage.setItem("lantern.theme", theme);
  } catch {}

  if (current && runs.length) show(current, $("view").value, $("panel").value || null);
}

// JS reads a light-dark() variable as its text, so an element resolves it
function pageColor(name) {
  const probe = document.body.appendChild(document.createElement("i"));
  probe.style.color = `var(${name})`;
  const color = getComputedStyle(probe).color;
  probe.remove();
  return color;
}

function darkLayout(layout) {
  const [fg, surface, line, muted] = ["--fg", "--surface", "--line", "--muted"].map(pageColor);
  const base = layout.template.layout;
  const axis = { gridcolor: line, linecolor: line, zerolinecolor: line };
  const template = {
    ...layout.template,
    layout: {
      ...base, paper_bgcolor: surface, plot_bgcolor: surface,
      xaxis: { ...base.xaxis, ...axis }, yaxis: { ...base.yaxis, ...axis },
      hoverlabel: { bgcolor: surface, bordercolor: line, font: { color: fg } },
      modebar: { bgcolor: "rgba(0, 0, 0, 0)", color: muted, activecolor: fg },
    },
  };

  // a font colour from plots.yaml would win over the template's
  return { template, font: { ...layout.font, color: fg } };
}

// plotly measures its box on the first draw only, so every draw and resize passes the box's size
function size() {
  return { width: $("figure").clientWidth, height: $("figure").clientHeight };
}

// a trace on axis x7 is in the seventh cell
function enlarge(event) {
  const axis = event.points[0].data.xaxis || "x";
  show(current, $("view").value, cells[Number(axis.slice(1) || 1) - 1]);
}

$("files").onchange = (e) => { upload(e.target.files); e.target.value = ""; };
const themeRadio = $("theme").querySelector(`input[value="${document.documentElement.dataset.theme}"]`);
(themeRadio || $("theme").querySelector('input[value="system"]')).checked = true;
$("theme").onchange = (e) => setTheme(e.target.value);
systemDark.onchange = () => setTheme($("theme").querySelector(":checked").value);
$("view").onchange = (e) => show(current, e.target.value);
$("panel").onchange = (e) => show(current, $("view").value, e.target.value || null);
window.onkeydown = (e) => { if (e.key === "Escape" && $("panel").value) show(current, $("view").value); };
$("refresh").onclick = async (e) => {
  e.target.disabled = true;

  try {
    await load(await api("/api/refresh", { method: "POST" }));
    $("message").textContent = "";
  } catch (error) {
    $("message").textContent = error.message;
  }

  e.target.disabled = false;
};
window.onresize = () => { if ($("figure").data) Plotly.relayout($("figure"), size()); };

function widths(set = null) {
  try {
    if (set) localStorage.setItem("lantern.columns", JSON.stringify(set));
    return JSON.parse(localStorage.getItem("lantern.columns")) || {};
  } catch {
    return {};
  }
}

for (const [column, width] of Object.entries(widths())) document.body.style.setProperty(`--${column}`, `${width}px`);

for (const gutter of document.querySelectorAll(".gutter")) {
  const column = gutter.dataset.column;
  const sign = column === "nav" ? 1 : -1;
  gutter.onpointerdown = (down) => {
    const start = document.querySelector(column).offsetWidth;
    let width = start;
    gutter.setPointerCapture(down.pointerId);
    gutter.classList.add("dragging");
    document.body.classList.add("resizing");
    gutter.onpointermove = (move) => {
      width = Math.min(Math.max(start + sign * (move.clientX - down.clientX), 140), 600);
      document.body.style.setProperty(`--${column}`, `${width}px`);
      requestAnimationFrame(window.onresize);
    };
    gutter.onpointerup = () => {
      gutter.onpointermove = gutter.onpointerup = null;
      gutter.classList.remove("dragging");
      document.body.classList.remove("resizing");
      widths({ ...widths(), [column]: width });
    };
  };
}
window.ondragover = (e) => e.preventDefault();
window.ondrop = (e) => { e.preventDefault(); upload(e.dataTransfer.files); };

api("/api/state").then(load);
setInterval(check, 2000);
