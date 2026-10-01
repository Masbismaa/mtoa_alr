// angka di dashboard naik pelan dari 0 pas halaman dibuka (biar kerasa hidup)
(function () {
  "use strict";

  const DURATION_MS = 700;
  const reduceMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reduceMotionQuery.matches) return;

  function animate(targetEl) {
    const finalValue = parseInt(targetEl.textContent.trim(), 10);
    if (!Number.isFinite(finalValue) || finalValue <= 0) return;
    const startTime = performance.now();

    function step(now) {
      const progress = Math.min((now - startTime) / DURATION_MS, 1);
      // ease-out: cepet di awal, melambat di akhir
      const easedProgress = 1 - Math.pow(1 - progress, 3);
      targetEl.textContent = String(Math.round(finalValue * easedProgress));
      if (progress < 1) window.requestAnimationFrame(step);
    }

    targetEl.textContent = "0";
    window.requestAnimationFrame(step);
  }

  document.querySelectorAll("[data-count-up]").forEach(animate);
})();
