// halaman Link Monitoring: selama pemeriksaan masih nunggu / jalan, progresnya diperbarui sendiri
// (nanya GET /link-monitoring/status tiap 3 detik). Begitu selesai / gagal, halaman dimuat ulang
// biar ringkasan status & tombol "Cek Semua" ikut keupdate.
(function () {
  "use strict";

  const POLL_INTERVAL_MS = 3000;
  const panelEl = document.getElementById("monitor_status");
  if (!panelEl || panelEl.dataset.isActive !== "true") return;

  const messageEl = panelEl.querySelector("[data-monitor-message]");
  const progressEl = panelEl.querySelector("[data-monitor-progress]");
  const barEl = panelEl.querySelector("[data-monitor-progress-bar]");
  const warningEl = document.querySelector("[data-monitor-warning]");
  const warningTextEl = document.querySelector("[data-monitor-warning-text]");
  let timerId = null;
  let isPolling = false;
  let isStopped = false;

  function render(status) {
    messageEl.textContent = status.message;
    progressEl.hidden = status.state !== "running";
    barEl.style.width = status.percent + "%";
    barEl.setAttribute("aria-valuenow", String(status.percent));
    warningEl.hidden = !status.warning;
    warningTextEl.textContent = status.warning || "";
  }

  function schedule() {
    if (isStopped || document.hidden || timerId !== null) return;
    timerId = window.setTimeout(poll, POLL_INTERVAL_MS);
  }

  async function poll() {
    timerId = null;
    if (isPolling) return;
    isPolling = true;
    try {
      const response = await fetch(panelEl.dataset.statusUrl, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const body = await response.json();
      if (!response.ok || !body.is_success) {
        // sesi habis / bukan admin lagi: berhenti nanya, kasih tau alasannya
        isStopped = true;
        messageEl.textContent = body.message || "Status pemeriksaan tidak bisa diambil. Muat ulang halaman.";
        return;
      }
      if (!body.data.is_active) {
        isStopped = true;
        window.location.reload();
        return;
      }
      render(body.data);
    } catch (error) {
      // jaringan putus / balasan bukan JSON: coba lagi di putaran berikutnya
    } finally {
      isPolling = false;
      schedule();
    }
  }

  // tab disembunyiin -> berhenti nanya (hemat request), dibuka lagi -> langsung nanya
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
      window.clearTimeout(timerId);
      timerId = null;
    } else if (!isStopped && timerId === null) {
      poll();
    }
  });

  schedule();
})();
