// tombol mata di login: tampil/sembunyiin password (CSP ngelarang onclick inline)
(function () {
  "use strict";

  const buttonEl = document.querySelector("[data-password-toggle]");
  if (!buttonEl) return;
  const inputEl = document.getElementById(buttonEl.dataset.passwordToggle);

  buttonEl.addEventListener("click", function () {
    const isShown = inputEl.type === "password";
    inputEl.type = isShown ? "text" : "password";
    buttonEl.setAttribute("aria-pressed", String(isShown));
    buttonEl.setAttribute("aria-label", isShown ? "Hide password" : "Show password");
    buttonEl.title = buttonEl.getAttribute("aria-label");
    buttonEl.querySelector("[data-icon-show]").classList.toggle("d-none", isShown);
    buttonEl.querySelector("[data-icon-hide]").classList.toggle("d-none", !isShown);
  });
})();
