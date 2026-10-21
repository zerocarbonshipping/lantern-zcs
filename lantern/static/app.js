// SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
// SPDX-License-Identifier: Apache-2.0

const $ = (id) => document.getElementById(id);
// a list goes as the key repeated, empty values not at all
const query = (params) => new URLSearchParams(Object.entries(params).flatMap(([k, v]) => [v].flat().filter(Boolean).map((x) => [k, x]))).toString();
let files = [];
let plots = [];
let runs = [];
let current = null;
let panels = [];
let cells = [];
let requests = 0;
let polling = false;
let version = null;

async function api(path, options) {
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error);
  return body;
}

// every loaded run, in the order of the sidebar
const allRuns = () => files.flatMap((file) => Object.keys(file.runs));

// take the loaded files from the server; the selected runs stay selected while they are loaded
async function load(state) {
  files = state.files;
  version = state.version;
  $("refresh").hidden = !state.refreshable;
  const kept = runs.filter((id) => allRuns().includes(id));
  await select(kept.length ? kept : allRuns().slice(0, 1));
}

async function select(next) {
  runs = allRuns().filter((id) => next.includes(id));
  plots = runs.length ? await api(`/api/catalogue?${query({ run: runs })}`) : [];
  render();
}

// a click selects a run alone, a ctrl- or cmd-click adds it to the selection or takes it out, keeping one
function pick(id, event) {
  if (!(event.ctrlKey || event.metaKey)) return select([id]);
  const next = runs.includes(id) ? runs.filter((r) => r !== id) : [...runs, id];
  if (next.length) select(next);
}

// upload results files, which the server then loads in the background; a file is named after itself, without the extension
async function upload(list) {
  const errors = [];
  let state = null;

  for (const file of [...list].filter((f) => f.name.endsWith(".parquet"))) {
    const name = file.name.replace(/\.parquet$/, "");
    progress({ loading: { text: `Uploading ${name}` } });

    try {
      state = await api("/api/files", { method: "POST", headers: { "X-Filename": encodeURIComponent(name) }, body: file });
    } catch (error) {
      errors.push(error.message);
    }
  }

  state = state || await api("/api/state");
  await watch(state);
  if (errors.length) $("message").textContent = errors.join(" ");
}

// show the progress of a load underway and poll it until no load is left, taking the files as each plot is prepared
async function watch(state) {
  progress(state);
  if (!state.loading || polling) return;
  polling = true;

  while (state.loading) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    state = await api("/api/state");
    progress(state);
    if (state.version !== version) await load(state);
  }

  polling = false;
  await load(state);
}

// the progress bar shows the steps of the file loading, or runs to and fro until it knows them; an error replaces it
function progress(state) {
  const loading = state.loading;
  $("loading").hidden = !loading;
  $("refresh").disabled = Boolean(loading);
  $("message").textContent = state.error || "";
  if (!loading) return;

  $("step").textContent = $("step").title = loading.text;

  if (loading.total) {
    $("progress").max = loading.total;
    $("progress").value = loading.done;
  } else {
    $("progress").removeAttribute("value");
  }
}

function runButton(id, text, representative) {
  const sample = representative ? `\nRepresentative sample: ${representative}` : "";
  const title = `${text}${sample}\nCtrl-click to compare it with the selected runs`;
  const button = Object.assign(document.createElement("button"), { textContent: text, title, className: "run" });
  button.classList.toggle("active", runs.includes(id));
  button.onclick = (event) => pick(id, event);
  return button;
}

function render() {
  // a file of one run is that run; a compiled file lists its runs with their number of samples
  $("runs").replaceChildren(...files.map((file) => {
    const item = document.createElement("li");
    const head = document.createElement("div");
    const remove = Object.assign(document.createElement("button"), { textContent: "×", title: `Unload ${file.name}`, className: "remove" });
    remove.onclick = async () => load(await api(`/api/files/${encodeURIComponent(file.name)}`, { method: "DELETE" }));
    // a file still loading would come back with its next plot
    remove.hidden = file.loading;

    if (file.compiled) {
      const tag = Object.assign(document.createElement("small"), { textContent: "compiled" });
      item.className = "compiled";
      head.append(tag, Object.assign(document.createElement("span"), { textContent: file.name, title: file.name }), remove);
      item.append(head, ...Object.entries(file.runs).map(([id, samples]) =>
        runButton(id, `${id.slice(file.name.length + 1)} · ${samples} sample${samples > 1 ? "s" : ""}`, file.representatives[id])));
    } else {
      head.append(runButton(Object.keys(file.runs)[0], file.name), remove);
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
  if (next) show(next.id, $("node").value, $("panel").value || null);
}

// show a plot, or one panel of it enlarged; only the latest request is drawn
async function show(id, node, panel = null) {
  const plot = plots.find((p) => p.id === id);
  const request = ++requests;
  current = id;
  node = plot.nodes.some(([value]) => value === node) ? node : plot.nodes[0]?.[0];

  for (const button of $("plots").querySelectorAll("button")) button.classList.toggle("active", button.dataset.id === id);
  $("title").textContent = plot.title;
  $("node").hidden = !plot.nodes.length;
  $("node").replaceChildren(...plot.nodes.map(([value, title]) => new Option(title, value, false, value === node)));

  // the figure lists the full plot's panels, [value, title], for the panel select, and the panel of each cell
  // for a click on it; an enlarged panel stays enlarged in other runs that have it, else the server draws all panels
  const figure = await api(`/api/plots/${encodeURIComponent(id)}?${query({ run: runs, node, panel })}`);
  if (request !== requests) return;
  ({ panels, cells } = figure.layout.meta);
  if (!panels.some(([value]) => value === panel)) panel = null;

  $("panel").hidden = panels.length < 2;
  $("panel").replaceChildren(new Option("All panels", ""), ...panels.map(([value, title]) => new Option(title, value, false, value === panel)));

  // plotly fills the space below the toolbar; a taller panel grid keeps its own height and scrolls
  $("figure").style.minHeight = `${figure.layout.height}px`;
  Object.assign(figure.layout, size());
  // a redraw of the same view, as when a load publishes more plots, keeps the zoom
  figure.layout.uirevision = JSON.stringify([id, runs, node, panel]);
  await Plotly.react($("figure"), figure.data, figure.layout, { displaylogo: false });
  $("figure").removeAllListeners("plotly_click");
  if (!panel && panels.length > 1) $("figure").on("plotly_click", enlarge);
}

// plotly measures its box on the first draw only, so every draw and resize passes the box's size
function size() {
  return { width: $("figure").clientWidth, height: $("figure").clientHeight };
}

// a trace on axis x7 is in the seventh cell
function enlarge(event) {
  const axis = event.points[0].data.xaxis || "x";
  show(current, $("node").value, cells[Number(axis.slice(1) || 1) - 1]);
}

$("files").onchange = (e) => { upload(e.target.files); e.target.value = ""; };
$("node").onchange = (e) => show(current, e.target.value);
$("panel").onchange = (e) => show(current, $("node").value, e.target.value || null);
window.onkeydown = (e) => { if (e.key === "Escape" && $("panel").value) show(current, $("node").value); };
$("refresh").onclick = async () => {
  try {
    await watch(await api("/api/refresh", { method: "POST" }));
  } catch (error) {
    $("message").textContent = error.message;
  }
};
window.onresize = () => { if ($("figure").data) Plotly.relayout($("figure"), size()); };
window.ondragover = (e) => e.preventDefault();
window.ondrop = (e) => { e.preventDefault(); upload(e.dataTransfer.files); };

api("/api/state").then(async (state) => { await load(state); await watch(state); });
