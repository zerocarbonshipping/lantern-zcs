let syncedY = false;

const syncIcon = { width: 16, height: 16, transform: "matrix(1 0 0 1 0 0)", path: "M1 2h14v1.5H1zM2.5 5.5h4v9h-4zM9.5 5.5h4v9h-4z" };

const yAxes = (layout) => Object.keys(layout).filter((key) => /^yaxis\d*$/.test(key));

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
  // runs side by side may share an axis already, and an axis matching one that matches another breaks Plotly
  const own = yAxes(layout).filter((axis) => !layout[axis].matches);

  if (own.length < 2) return [["toImage", svg, csv], zoom];

  if (syncedY) {
    for (const axis of yAxes(layout)) if (axis !== own[0]) layout[axis].matches = own[0].replace("axis", "");
  }

  return [["toImage", svg, csv, sync], zoom];
}
