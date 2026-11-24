// halaman Manage: tombol Browse buka daftar folder DI SERVER (GET /manage/browse?path=...),
// klik folder = masuk ke folder itu sekaligus ngisi kolom New folder, jadi ga perlu ngetik path
(function () {
  "use strict";

  const pageEl = document.getElementById("storage_page");
  if (!pageEl) return;

  document.querySelectorAll("[data-browse-panel]").forEach(function (panelEl) {
    const formEl = panelEl.closest("form");
    const inputEl = formEl.querySelector("input[name=path]");
    const toggleEl = formEl.querySelector("[data-browse-toggle]");
    const pathEl = panelEl.querySelector("[data-browse-path]");
    const listEl = panelEl.querySelector("[data-browse-list]");
    const messageEl = panelEl.querySelector("[data-browse-message]");

    function addItem(label, path) {
      const buttonEl = document.createElement("button");
      buttonEl.type = "button";
      buttonEl.className = "list-group-item list-group-item-action py-1";
      buttonEl.textContent = label;
      buttonEl.addEventListener("click", function () {
        inputEl.value = path;
        load(path);
      });
      listEl.appendChild(buttonEl);
    }

    async function load(path) {
      messageEl.textContent = "Loading...";
      try {
        const response = await fetch(pageEl.dataset.browseUrl + "?path=" + encodeURIComponent(path), {
          headers: { Accept: "application/json" },
          credentials: "same-origin",
        });
        const body = await response.json();
        if (!response.ok || !body.is_success) {
          messageEl.textContent = body.message || "This folder cannot be opened.";
          return;
        }
        const data = body.data;
        pathEl.textContent = data.path;
        listEl.replaceChildren();
        if (data.parent !== data.path) addItem("..", data.parent);
        // pemisah ikut path server (/ di Linux, \ di Windows)
        const separator = data.path.includes("\\") ? "\\" : "/";
        const base = data.path.endsWith(separator) ? data.path : data.path + separator;
        data.folder_list.forEach(function (name) { addItem(name, base + name); });
        messageEl.textContent = data.folder_list.length
          ? "Click a folder to open it and use it as the new folder."
          : "No subfolders here. This folder will be used if it is empty.";
      } catch (error) {
        messageEl.textContent = "Could not reach the server. Try again.";
      }
    }

    toggleEl.addEventListener("click", function () {
      panelEl.hidden = !panelEl.hidden;
      toggleEl.setAttribute("aria-expanded", String(!panelEl.hidden));
      if (!panelEl.hidden) load(inputEl.value.trim() || panelEl.dataset.startPath);
    });
  });
})();
