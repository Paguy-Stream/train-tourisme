/**
 * assets/nav_active.js
 * ─────────────────────
 * Gestion du lien actif dans la sidebar — Dash 4.0.0 compatible.
 *
 * Dash 4.0.0 utilise l'History API pour la navigation SPA.
 * On intercepte pushState + popstate pour détecter les changements d'URL
 * sans aucune interaction avec le router React interne (évite clean_url).
 */
(function () {
  "use strict";

  function setActiveLink() {
    var path = window.location.pathname;
    var links = document.querySelectorAll("#nav-links .nav-link");

    links.forEach(function (a) {
      var href = a.getAttribute("href") || "";
      var active =
        path === href || (href !== "/" && path.indexOf(href) === 0);
      a.className = active ? "nav-link active" : "nav-link";
    });
  }

  // Initialisation
  function init() {
    setActiveLink();

    // Intercepte la navigation Dash (History API)
    var orig = history.pushState;
    history.pushState = function () {
      orig.apply(history, arguments);
      setTimeout(setActiveLink, 30);
    };
    window.addEventListener("popstate", function () {
      setTimeout(setActiveLink, 30);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Sécurité : relance après chargement complet (composants Dash montés)
  window.addEventListener("load", function () {
    setTimeout(setActiveLink, 300);
  });
})();
