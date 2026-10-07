// pusat pengaturan tampilan: nerapin ke halaman, simpen ke localStorage, kirim ke server.
// dipake bareng sama theme_toggle.js & theme_customizer.js (biar ga nulis ulang)
(function () {
  "use strict";

  const STORAGE_KEY = "alr_ui_pref";
  const root = document.documentElement;

  // baca preferensi yg lagi kepasang di <html>
  function readCurrent() {
    return {
      theme_mode: root.dataset.theme,
      accent_key: root.dataset.accent,
      is_compact_view: root.dataset.density === "compact",
      font_family: root.dataset.font
    };
  }

  function writeLocal(uiDict) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(uiDict));
    } catch (error) {
      // localStorage diblok, cuekin aja
    }
  }

  // ganti atribut di <html>, CSS Tabler & app langsung ngikut
  function setAttributes(uiDict) {
    if (uiDict.theme_mode) {
      // data-theme dipake app, data-bs-theme dipake Tabler
      root.dataset.theme = uiDict.theme_mode;
      root.dataset.bsTheme = uiDict.theme_mode;
    }
    if (uiDict.accent_key) root.dataset.accent = uiDict.accent_key;
    if (typeof uiDict.is_compact_view === "boolean") root.dataset.density = uiDict.is_compact_view ? "compact" : "comfortable";
    if (uiDict.font_family) root.dataset.font = uiDict.font_family;

    const currentDict = readCurrent();
    writeLocal(currentDict);
    // kabarin komponen lain (misal customizer) kalau preferensi berubah
    document.dispatchEvent(new CustomEvent("alr:preference-changed", { detail: currentDict }));
  }

  function canAnimate() {
    const isReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    return typeof document.startViewTransition === "function" && !isReducedMotion;
  }

  // pasang preferensi ke halaman (bisa sebagian aja).
  // animasinya pake View Transition: browser motret tampilan lama & baru terus di-crossfade,
  // jadi cuma 1x hitung ulang style. Dulu tiap elemen dikasih transition, itu yg bikin patah-patah
  function apply(uiDict, isAnimated) {
    if (isAnimated && canAnimate()) {
      document.startViewTransition(function () {
        setAttributes(uiDict);
      });
      return;
    }
    setAttributes(uiDict);
  }

  // kirim ke server. Kalau belum login, cukup disimpen lokal.
  // targetUrl opsional: dipake juga buat nyimpen layout tabel (data_table.js), defaultnya URL preferensi tampilan
  async function saveToServer(payloadDict, targetUrl) {
    const prefUrl = targetUrl || root.dataset.prefUrl;
    if (root.dataset.prefSource !== "server" || !prefUrl) {
      return { is_success: true, is_local_only: true };
    }

    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    try {
      const response = await fetch(prefUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfMeta ? csrfMeta.content : ""
        },
        body: JSON.stringify(payloadDict)
      });
      const bodyDict = await response.json().catch(function () {
        return { is_success: false, message: "Respon server tidak valid" };
      });
      if (!response.ok) {
        bodyDict.is_success = false;
      }
      return bodyDict;
    } catch (error) {
      return { is_success: false, message: "Koneksi ke server gagal" };
    }
  }

  // animasi baru dinyalain setelah halaman kegambar (biar ga ada efek "loncat" pas load)
  window.requestAnimationFrame(function () {
    window.requestAnimationFrame(function () {
      root.classList.add("is-ready");
    });
  });

  window.AlrUiPreference = {
    readCurrent: readCurrent,
    apply: apply,
    saveToServer: saveToServer
  };
})();
