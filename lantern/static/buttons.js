// The figure's buttons in Plotly's modebar: the downloads, the y axes synced across panels, and the zoom tools.

// whether the panels of a figure share one y range; kept for every figure while the page is open
let syncedY = false;

// two bars under one line: panels on one scale
const syncIcon = { width: 16, height: 16, transform: "matrix(1 0 0 1 0 0)", path: "M1 2h14v1.5H1zM2.5 5.5h4v9h-4zM9.5 5.5h4v9h-4z" };

// the y axes of a figure's layout: yaxis, yaxis2, ...
const yAxes = (layout) => Object.keys(layout).filter((key) => /^yaxis\d*$/.test(key));

// the buttons of a figure of the plot id, drawn with the query params: a second camera that downloads the plot as SVG
// next to the PNG one, a disk that downloads the drawn lines as CSV and, where panels have y axes of their own, the
// sync of those, which redraw draws again; then the zoom tools. The selections and hover toggles are left out.
// Synced, every y axis of the layout matches one, so the panels share its range and zoom together, each with its ticks
function modebarButtons(id, params, layout, redraw) {
  const svg = {
    name: "Download plot as SVG", icon: Plotly.Icons.camera,
    click: (gd) => Plotly.downloadImage(gd, { format: "svg", filename: id }),
  };
  const csv = {
    name: "Download data as CSV", icon: Plotly.Icons.disk,
    click: () => window.location.assign(`/api/plots/${encodeURIComponent(id)}.csv?${params}`),
  };
  const sync = {
    name: syncedY ? "Give each panel its own y axis" : "Share one y axis across the panels", icon: syncIcon,
    click: () => { syncedY = !syncedY; redraw(); },
  };
  const zoom = ["zoom2d", "pan2d", "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d"];
  // the axes that fit their own data: those of runs side by side in a row may match one already
  const own = yAxes(layout).filter((axis) => !layout[axis].matches);

  if (own.length < 2) return [["toImage", svg, csv], zoom];

  if (syncedY) {
    for (const axis of yAxes(layout)) if (axis !== own[0]) layout[axis].matches = own[0].replace("axis", "");
  }

  return [["toImage", svg, csv, sync], zoom];
}
