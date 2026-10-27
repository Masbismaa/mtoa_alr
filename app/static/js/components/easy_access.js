// layar Easy Access: garis pemisah pohon menu | gambar bisa digeser (mouse / panah kiri-kanan), lebarnya diinget.
// folder buka/tutup ngasih tau pembaca layar lewat aria-expanded
(function () {
  "use strict";

  const rootEl = document.querySelector("[data-easy-access]");
  if (!rootEl) return;
  const splitterEl = rootEl.querySelector("[data-easy-access-splitter]");
  const WIDTH_KEY = "alr_easy_access_width";
  const MIN_WIDTH = 220;
  const KEY_STEP = 24;

  function applyWidth(width) {
    const maxWidth = rootEl.clientWidth - 160;
    const clampedWidth = Math.round(Math.min(Math.max(width, MIN_WIDTH), Math.max(MIN_WIDTH, maxWidth)));
    rootEl.style.setProperty("--ea-tree-width", clampedWidth + "px");
    splitterEl.setAttribute("aria-valuenow", String(clampedWidth));
    return clampedWidth;
  }

  function saveWidth(width) {
    try { localStorage.setItem(WIDTH_KEY, String(width)); } catch (error) {}
  }

  try {
    const storedWidth = parseInt(localStorage.getItem(WIDTH_KEY), 10);
    if (storedWidth > 0) applyWidth(storedWidth);
  } catch (error) {
    // tanpa penyimpanan browser lebarnya pake bawaan CSS
  }

  splitterEl.addEventListener("pointerdown", function (event) {
    event.preventDefault();
    splitterEl.setPointerCapture(event.pointerId);
    const left = rootEl.getBoundingClientRect().left;
    let width = 0;
    function onMove(moveEvent) { width = applyWidth(moveEvent.clientX - left); }
    function onUp() {
      splitterEl.removeEventListener("pointermove", onMove);
      splitterEl.removeEventListener("pointerup", onUp);
      if (width) saveWidth(width);
    }
    splitterEl.addEventListener("pointermove", onMove);
    splitterEl.addEventListener("pointerup", onUp);
  });

  splitterEl.addEventListener("keydown", function (event) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const currentWidth = rootEl.querySelector(".ea-tree-panel").getBoundingClientRect().width;
    saveWidth(applyWidth(currentWidth + (event.key === "ArrowRight" ? KEY_STEP : -KEY_STEP)));
  });

  rootEl.querySelectorAll("details.ea-folder").forEach(function (folderEl) {
    folderEl.addEventListener("toggle", function () {
      folderEl.querySelector("summary").setAttribute("aria-expanded", String(folderEl.open));
    });
  });
})();
