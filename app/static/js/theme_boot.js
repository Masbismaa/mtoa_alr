// dijalanin paling awal (di <head>, tanpa defer) biar tema langsung kepasang sebelum halaman tampil
(function () {
  "use strict";

  var STORAGE_KEY = "alr_ui_pref";
  var SIDEBAR_KEY = "alr_sidebar_collapsed";
  var root = document.documentElement;

  try {
    // posisi sidebar (diciutin/nggak) diinget per browser
    if (localStorage.getItem(SIDEBAR_KEY) === "1") {
      root.dataset.sidebar = "collapsed";
    }

    // user udah login: preferensi dari server yg dipake, sekalian disalin ke localStorage
    // biar halaman login tetep pake tema yg sama abis logout
    if (root.dataset.prefSource === "server") {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        theme_mode: root.dataset.theme,
        accent_key: root.dataset.accent,
        is_compact_view: root.dataset.density === "compact",
        font_family: root.dataset.font
      }));
      return;
    }

    // belum login: ambil dari localStorage
    var saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (saved) {
      if (saved.theme_mode) root.dataset.theme = saved.theme_mode;
      if (saved.accent_key) root.dataset.accent = saved.accent_key;
      if (typeof saved.is_compact_view === "boolean") root.dataset.density = saved.is_compact_view ? "compact" : "comfortable";
      if (saved.font_family) root.dataset.font = saved.font_family;
    } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      // belum pernah milih: ikut setting gelap/terang Windows
      root.dataset.theme = "dark";
    }
  } catch (error) {
    // localStorage bisa diblok browser, ya udah pake default aja
  }
})();