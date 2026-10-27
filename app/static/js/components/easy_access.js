// layar Home: folder buka/tutup ngasih tau pembaca layar lewat aria-expanded
(function () {
  "use strict";

  const rootEl = document.querySelector("[data-easy-access]");
  if (!rootEl) return;

  rootEl.querySelectorAll("details.ea-folder").forEach(function (folderEl) {
    folderEl.addEventListener("toggle", function () {
      folderEl.querySelector("summary").setAttribute("aria-expanded", String(folderEl.open));
    });
  });
})();
