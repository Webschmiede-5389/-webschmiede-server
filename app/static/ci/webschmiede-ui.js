/**
 * Minimal UI helpers for AppShell drawer + modal (no framework).
 * Safe to load only on design-system / future migrated pages.
 */
(function () {
  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function closeDrawer(shell) {
    if (!shell) return;
    shell.classList.remove("is-drawer-open");
    var toggle = qs("[data-ws-menu-toggle]", shell);
    if (toggle) toggle.setAttribute("aria-expanded", "false");
  }

  function openDrawer(shell) {
    shell.classList.add("is-drawer-open");
    var toggle = qs("[data-ws-menu-toggle]", shell);
    if (toggle) toggle.setAttribute("aria-expanded", "true");
  }

  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-ws-menu-toggle]");
    if (t) {
      var shell = t.closest(".ws-app-shell") || qs(".ws-app-shell");
      if (!shell) return;
      if (shell.classList.contains("is-drawer-open")) closeDrawer(shell);
      else openDrawer(shell);
      return;
    }
    if (e.target.matches("[data-ws-drawer-backdrop]")) {
      closeDrawer(e.target.closest(".ws-app-shell") || qs(".ws-app-shell"));
    }
    var openModal = e.target.closest("[data-ws-open-modal]");
    if (openModal) {
      var id = openModal.getAttribute("data-ws-open-modal");
      var backdrop = qs("#" + id);
      if (backdrop) {
        backdrop.hidden = false;
        var dialog = qs(".ws-modal", backdrop);
        if (dialog) dialog.focus();
      }
    }
    var closeModal = e.target.closest("[data-ws-close-modal]");
    if (closeModal) {
      var back = closeModal.closest(".ws-modal-backdrop");
      if (back) back.hidden = true;
    }
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      qsa(".ws-modal-backdrop:not([hidden])").forEach(function (el) { el.hidden = true; });
      closeDrawer(qs(".ws-app-shell.is-drawer-open"));
    }
  });

  qsa(".ws-switch").forEach(function (sw) {
    sw.addEventListener("click", function () {
      var on = sw.getAttribute("aria-checked") === "true";
      sw.setAttribute("aria-checked", on ? "false" : "true");
    });
  });
})();
