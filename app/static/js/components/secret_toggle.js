// tombol Show/Hide buat nilai rahasia (access note). Isinya ga ditempel di HTML: diambil dari server (data-secret-url)
// pas pertama kali di-Show / di-Copy, dan tiap ambil dicatat di audit. Abis keambil disimpen di halaman ini aja.
(function () {
  "use strict";

  const MASK_TEXT = "••••••••";

  // ambil nilai rahasia sekali per halaman. Dipake juga copy_button.js (window.AlrSecret)
  async function loadSecret(targetEl) {
    if (targetEl.dataset.secretValue !== undefined || !targetEl.dataset.secretUrl) {
      return targetEl.dataset.secretValue || "";
    }
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const response = await fetch(targetEl.dataset.secretUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfMeta ? csrfMeta.content : "", "Accept": "application/json" },
    });
    const body = await response.json().catch(function () { return {}; });
    if (!response.ok || !body.is_success) throw new Error(body.message || "Could not load the access note");
    targetEl.dataset.secretValue = body.data.access_note;
    return targetEl.dataset.secretValue;
  }

  window.AlrSecret = { load: loadSecret };

  document.querySelectorAll("[data-secret-toggle]").forEach(function (buttonEl) {
    const targetEl = document.getElementById(buttonEl.dataset.secretToggle);
    if (!targetEl) return;
    const labelEl = buttonEl.querySelector("[data-secret-label]");

    buttonEl.addEventListener("click", async function () {
      const isVisible = buttonEl.getAttribute("aria-pressed") === "true";
      let secretValue = "";
      if (!isVisible) {
        try {
          secretValue = await loadSecret(targetEl);
        } catch (error) {
          if (window.AlrFlash) window.AlrFlash.show(error.message, "danger");
          return;
        }
      }
      // pake textContent biar isi password ga pernah dijalanin sebagai HTML
      targetEl.textContent = isVisible ? MASK_TEXT : secretValue;
      buttonEl.setAttribute("aria-pressed", String(!isVisible));
      if (labelEl) labelEl.textContent = isVisible ? "Show" : "Hide";
    });
  });
})();
