// sidebar: desktop bisa diciutin, HP/tablet jadi laci geser dari kiri
(function () {
  "use strict";

  const SIDEBAR_KEY = "alr_sidebar_collapsed";
  const desktopQuery = window.matchMedia("(min-width: 961px)");
  const root = document.documentElement;
  const shellEl = document.querySelector("[data-sidebar-shell]");
  const sidebarEl = document.querySelector("[data-sidebar]");
  const toggleButton = document.querySelector("[data-sidebar-toggle]");
  if (!shellEl || !sidebarEl || !toggleButton) return;

  function isDesktop() {
    return desktopQuery.matches;
  }

  function isMobileOpen() {
    return shellEl.classList.contains("is-sidebar-open");
  }

  // sidebar yg ketutup di HP ga boleh kena tab keyboard
  function syncAccessibility() {
    if (isDesktop()) {
      sidebarEl.inert = false;
      toggleButton.setAttribute("aria-expanded", String(root.dataset.sidebar !== "collapsed"));
    } else {
      sidebarEl.inert = !isMobileOpen();
      toggleButton.setAttribute("aria-expanded", String(isMobileOpen()));
    }
  }

  function setMobileOpen(isOpen) {
    shellEl.classList.toggle("is-sidebar-open", isOpen);
    document.body.classList.toggle("is-scroll-locked", isOpen);
    syncAccessibility();
    if (isOpen) {
      const firstLink = sidebarEl.querySelector(".nav-link[href]");
      if (firstLink) firstLink.focus();
    }
  }

  function setCollapsed(isCollapsed) {
    if (isCollapsed) {
      root.dataset.sidebar = "collapsed";
    } else {
      delete root.dataset.sidebar;
    }
    try {
      localStorage.setItem(SIDEBAR_KEY, isCollapsed ? "1" : "0");
    } catch (error) {
      // localStorage diblok, cuekin
    }
    syncAccessibility();
  }

  toggleButton.addEventListener("click", function () {
    if (isDesktop()) {
      setCollapsed(root.dataset.sidebar !== "collapsed");
    } else {
      setMobileOpen(!isMobileOpen());
    }
  });

  // tombol X & area gelap di belakang sidebar
  document.querySelectorAll("[data-sidebar-close]").forEach(function (closeEl) {
    closeEl.addEventListener("click", function () {
      setMobileOpen(false);
    });
  });

  // tombol Esc buat nutup laci
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && isMobileOpen()) {
      setMobileOpen(false);
      toggleButton.focus();
    }
  });

  // pindah ukuran layar (misal rotate tablet) -> laci ditutup
  desktopQuery.addEventListener("change", function () {
    setMobileOpen(false);
  });

  syncAccessibility();
})();