// SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
// SPDX-License-Identifier: Apache-2.0

const $ = (id) => document.getElementById(id);
let state = { runs: [], plots: [] };
let current = null;
let minHeight = 0;

async function api(path, options) {
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error);
  return body;
}

// upload {file, path} entries; a run is named by its path, without the extension
async function upload(entries) {
  const errors = [];

  for (const { file, path } of entries.filter((e) => e.path.endsWith(".parquet"))) {
    const name = path.replace(/\.parquet$/, "");

    try {
      state = await api("/api/runs", { method: "POST", headers: { "X-Filename": encodeURIComponent(name) }, body: file });
    } catch (error) {
      errors.push(error.message);
    }
  }

  $("message").textContent = errors.join(" ");
  render();
}

// a picked folder's files carry their path below the folder
function picked(files) {
  return [...files].map((file) => ({ file, path: file.webkitRelativePath.split("/").slice(1).join("/") || file.name }));
}

// walk dropped files and folders recursively
async function dropped(items) {
  const entries = [];
  const read = (reader) => new Promise((resolve, reject) => reader.readEntries(resolve, reject));

  async function walk(entry, prefix) {
    if (entry.isFile) {
      entries.push({ file: await new Promise((resolve, reject) => entry.file(resolve, reject)), path: prefix + entry.name });
      return;
    }

    const reader = entry.createReader();
    for (let batch = await read(reader); batch.length; batch = await read(reader)) {
      for (const child of batch) await walk(child, prefix === null ? "" : `${prefix}${entry.name}/`);
    }
  }

  const roots = [...items].map((item) => item.webkitGetAsEntry()).filter(Boolean);
  for (const root of roots) await walk(root, root.isFile ? "" : null);

  return entries;
}

function render() {
  const sidebar = $("sidebar");
  sidebar.replaceChildren();
  let section = null;

  for (const plot of state.plots) {
    if (plot.section !== section) {
      section = plot.section;
      sidebar.append(Object.assign(document.createElement("h4"), { textContent: section }));
    }

    const button = Object.assign(document.createElement("button"), { textContent: plot.title, disabled: !plot.available });
    button.dataset.id = plot.id;
    button.onclick = () => show(plot.id);
    sidebar.append(button);
  }

  $("runs").replaceChildren(...state.runs.map((name) => {
    const item = document.createElement("li");
    const remove = Object.assign(document.createElement("button"), { textContent: "×", title: `Unload ${name}` });
    remove.onclick = async () => { state = await api(`/api/runs/${encodeURIComponent(name)}`, { method: "DELETE" }); render(); };
    item.append(Object.assign(document.createElement("span"), { textContent: name, title: name }), remove);
    return item;
  }));

  const loaded = state.runs.length > 0;
  $("empty").hidden = loaded;
  $("toolbar").hidden = !loaded;

  if (!loaded) {
    Plotly.purge($("figure"));
    return;
  }

  const available = state.plots.filter((p) => p.available);
  const next = available.find((p) => p.id === current) || available[0];
  if (next) show(next.id, $("node").value);
}

async function show(id, node) {
  const plot = state.plots.find((p) => p.id === id);
  current = id;
  node = plot.nodes.includes(node) ? node : plot.nodes[0];

  for (const button of $("sidebar").querySelectorAll("button")) button.classList.toggle("active", button.dataset.id === id);
  $("title").textContent = plot.title;
  $("node").hidden = !plot.nodes.length;
  $("node").replaceChildren(...plot.nodes.map((n) => new Option(n, n, false, n === node)));

  const figure = await api(`/api/plots/${encodeURIComponent(id)}${node ? `?node=${encodeURIComponent(node)}` : ""}`);
  if (current !== id) return;

  // fill the window below the toolbar; a taller panel grid keeps its own height and scrolls
  minHeight = figure.layout.height;
  figure.layout.height = Math.max(minHeight, fitHeight());
  Plotly.react($("figure"), figure.data, figure.layout, { responsive: true, displaylogo: false });
}

function fitHeight() {
  return window.innerHeight - $("figure").getBoundingClientRect().top - 24;
}

$("files").onchange = (e) => { upload(picked(e.target.files)); e.target.value = ""; };
$("folder").onchange = (e) => { upload(picked(e.target.files)); e.target.value = ""; };
$("node").onchange = (e) => show(current, e.target.value);
window.ondragover = (e) => e.preventDefault();
window.ondrop = (e) => { e.preventDefault(); dropped(e.dataTransfer.items).then(upload); };
window.onresize = () => {
  if ($("figure").data) Plotly.relayout($("figure"), { height: Math.max(minHeight, fitHeight()) });
};

api("/api/state").then((s) => { state = s; render(); });
