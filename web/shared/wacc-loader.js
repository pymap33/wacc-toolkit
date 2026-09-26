// Shared Pyodide/manifest loading logic used by every calculator page in
// web/. Factored out 2026-09-27 when the site moved from a single
// calculator page to a hub + one page per calculator, so this loading
// logic (and its manifest-driven file list, added 2026-09-26 to fix the
// 2026-09-09 ModuleNotFoundError regression) isn't duplicated per page.
//
// All fetch paths below are relative to the *calling page's* URL, not this
// script's URL — browsers resolve fetch() against document location, so
// this file only works correctly imported from a page that itself lives
// directly under web/ (e.g. web/calculator-bottom-up-beta.html), one level
// below the repo root, same as the manifest/data/wacc directories expect.

export async function loadWaccPackage(pyodide) {
  const manifestRes = await fetch("../wacc/manifest.json");
  if (!manifestRes.ok) {
    throw new Error("wacc/manifest.json not found — run scripts/generate_manifest.py and commit it.");
  }
  const manifest = await manifestRes.json();

  pyodide.FS.mkdirTree("/wacc_pkg/wacc");
  pyodide.FS.mkdirTree("/wacc_pkg/data");
  for (const f of manifest.modules) {
    const res = await fetch(`../wacc/${f}`);
    const text = await res.text();
    pyodide.FS.writeFile(`/wacc_pkg/wacc/${f}`, text);
  }
  for (const f of manifest.data) {
    const res = await fetch(`../data/${f}`);
    const text = await res.text();
    pyodide.FS.writeFile(`/wacc_pkg/data/${f}`, text);
  }
  pyodide.runPython(`
import sys
sys.path.insert(0, "/wacc_pkg")
import wacc
`);
}

export function daysSince(isoDate) {
  if (!isoDate) return null;
  const then = new Date(isoDate);
  if (isNaN(then)) return null;
  return Math.floor((Date.now() - then.getTime()) / 86400000);
}

// Returns the raw freshness data; DOM rendering (which input field to
// prefill, banner text) stays page-specific since each calculator's form
// differs.
export async function fetchDataFreshness() {
  const [rfRes, betaRes] = await Promise.all([
    fetch("../data/risk_free_rate.json"),
    fetch("../data/industry_betas.json"),
  ]);
  const rfData = await rfRes.json();
  const betaData = await betaRes.json();

  // Treasury's _as_of is MM/DD/YYYY (as stored by scripts/update_data.py,
  // or a manual fallback update in the same format); industry betas' is
  // ISO (YYYY-MM-DD).
  const rfParts = (rfData._as_of || "").split("/");
  const rfIso = rfParts.length === 3 ? `${rfParts[2]}-${rfParts[0]}-${rfParts[1]}` : null;
  const rfAge = daysSince(rfIso);
  const betaAge = daysSince(betaData._as_of);

  // Rf is a daily series — flag if the committed snapshot is over a month
  // old. Damodaran's industry betas update roughly annually.
  const rfStale = rfAge === null || rfAge > 30;
  const betaStale = betaAge === null || betaAge > 400;

  return { rfData, betaData, rfAge, betaAge, rfStale, betaStale };
}

export function pct(x) {
  return (x * 100).toFixed(2) + "%";
}
