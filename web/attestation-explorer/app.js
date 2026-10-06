/* Load the one current data file. The app itself is never generated. */
(function (global) {
  "use strict";
  const DATA_URL = "../../data/attestations.json";
  const {expandData} = typeof module !== "undefined" && module.exports ?
    require("./explorer.js") : global.AttestationExplorer;

  async function loadData(fetcher = global.fetch.bind(global)) {
    const response = await fetcher(DATA_URL, {cache: "no-store"});
    if (!response.ok) throw new Error(`Collection request failed (${response.status})`);
    return expandData(await response.json());
  }

  function start(doc = global.document, explorer = global.AttestationExplorer, fetcher) {
    const loader = doc.getElementById("collection-loader");
    const root = doc.getElementById("attestation-app");
    const status = loader.querySelector('[data-load="status"]');
    const retry = loader.querySelector('[data-load="retry"]');
    const fileLabel = loader.querySelector('[data-load="file-label"]');
    const file = loader.querySelector('[data-load="file"]');
    let app;

    function show(data) {
      // Validate before replacing a working view. Source strings are rendered as text.
      explorer.createModel(data);
      app?.destroy();
      root.hidden = false;
      app = explorer.mount(root, data);
      loader.hidden = true;
    }
    function failed() {
      root.hidden = true;
      loader.hidden = false;
      status.textContent = "The collection could not be loaded. Try again, or choose data/attestations.json from this project.";
      retry.hidden = false;
      fileLabel.hidden = false;
    }
    async function load() {
      status.textContent = "Loading the collection…";
      retry.hidden = true;
      try { show(await loadData(fetcher)); } catch { failed(); }
    }
    retry.addEventListener("click", load);
    file.addEventListener("change", async () => {
      if (!file.files[0]) return;
      try { show(expandData(JSON.parse(await file.files[0].text()))); } catch { failed(); }
    });
    return load();
  }

  if (typeof module !== "undefined" && module.exports) module.exports = {DATA_URL, loadData, start};
  else start();
})(typeof globalThis !== "undefined" ? globalThis : this);
