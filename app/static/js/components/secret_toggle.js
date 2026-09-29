// tombol Tampilkan/Sembunyikan buat nilai rahasia (access note)
(function () {
  "use strict";

  const MASK_TEXT = "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022";

  document.querySelectorAll("[data-secret-toggle]").forEach(function (buttonEl) {
    const targetEl = document.getElementById(buttonEl.dataset.secretToggle);
    if (!targetEl) return;
    const labelEl = buttonEl.querySelector("[data-secret-label]");

    buttonEl.addEventListener("click", function () {
      const isVisible = buttonEl.getAttribute("aria-pressed") === "true";
      // pake textContent biar isi password ga pernah dijalanin sebagai HTML
      targetEl.textContent = isVisible ? MASK_TEXT : targetEl.dataset.secretValue;
      buttonEl.setAttribute("aria-pressed", String(!isVisible));
      if (labelEl) labelEl.textContent = isVisible ? "Tampilkan" : "Sembunyikan";
    });
  });
})();