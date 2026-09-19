/* NOVAREL — interactions. Vanilla, sans dépendance, chargé en defer.
   Tout est optionnel : la page reste entièrement lisible et utilisable sans JS. */

(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------------------------------------------------------- Thème */

  function initTheme() {
    var btn = document.querySelector("[data-theme-toggle]");
    if (!btn) return;

    btn.addEventListener("click", function () {
      var next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      btn.setAttribute("aria-pressed", String(next === "dark"));
      try {
        localStorage.setItem("novarel-theme", next);
      } catch (e) {
        /* stockage indisponible (navigation privée) : le thème reste valable pour la session */
      }
    });

    btn.setAttribute("aria-pressed", String(document.documentElement.dataset.theme === "dark"));
  }

  /* ------------------------------------------------------- Tiroir mobile */

  function initDrawer() {
    var drawer = document.getElementById("drawer");
    var openBtn = document.querySelector("[data-drawer-open]");
    var closeBtn = document.querySelector("[data-drawer-close]");
    if (!drawer || !openBtn || !closeBtn) return;

    var lastFocus = null;

    function focusables() {
      return Array.prototype.filter.call(
        drawer.querySelectorAll("a[href], button:not([disabled])"),
        function (el) { return el.offsetParent !== null; }
      );
    }

    function isOpen() {
      return drawer.dataset.open === "true";
    }

    function open() {
      lastFocus = document.activeElement;
      drawer.dataset.open = "true";
      drawer.removeAttribute("inert");
      document.body.dataset.navOpen = "true";
      openBtn.setAttribute("aria-expanded", "true");
      // Le tiroir passe de visibility:hidden à visible. Lire une métrique force le
      // recalcul du style : sans ça, focus() viserait un élément encore non rendu.
      void drawer.offsetWidth;
      closeBtn.focus();
    }

    function close() {
      drawer.dataset.open = "false";
      drawer.setAttribute("inert", "");
      document.body.dataset.navOpen = "false";
      openBtn.setAttribute("aria-expanded", "false");
      if (lastFocus) lastFocus.focus();
    }

    openBtn.addEventListener("click", open);
    closeBtn.addEventListener("click", close);

    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape" || !isOpen()) return;
      e.preventDefault();
      close();
    });

    drawer.addEventListener("keydown", function (e) {
      if (e.key !== "Tab") return;

      var items = focusables();
      if (!items.length) return;
      var first = items[0];
      var last = items[items.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });

    drawer.setAttribute("inert", "");
  }

  /* --------------------------------------------------------- Comparateur */

  function initCompare() {
    var table = document.querySelector("[data-compare]");
    if (!table) return;

    var tbody = table.querySelector("tbody");
    var buttons = table.querySelectorAll("[data-sort-index]");

    function cellValue(row, index, type) {
      var cell = row.children[index];
      if (!cell) return type === "number" ? Infinity : "";
      var raw = cell.dataset.value !== undefined ? cell.dataset.value : cell.textContent.trim();
      if (type !== "number") return raw.toLocaleLowerCase("fr");
      var num = parseFloat(raw);
      return isNaN(num) ? Infinity : num;
    }

    Array.prototype.forEach.call(buttons, function (btn) {
      btn.addEventListener("click", function () {
        var index = parseInt(btn.dataset.sortIndex, 10);
        var type = btn.dataset.sortType || "text";
        var current = btn.getAttribute("aria-sort");
        var dir = current === "ascending" ? "descending" : "ascending";

        Array.prototype.forEach.call(buttons, function (other) {
          other.setAttribute("aria-sort", "none");
        });
        btn.setAttribute("aria-sort", dir);

        var rows = Array.prototype.slice.call(tbody.rows);
        rows.sort(function (a, b) {
          var va = cellValue(a, index, type);
          var vb = cellValue(b, index, type);
          var cmp;
          if (type === "number") {
            cmp = va - vb;
          } else {
            cmp = va.localeCompare(vb, "fr");
          }
          return dir === "ascending" ? cmp : -cmp;
        });

        rows.forEach(function (row) { tbody.appendChild(row); });
      });
    });
  }

  /* -------------------------------------------------------- Sommaire actif */

  function initToc() {
    var links = document.querySelectorAll("[data-toc-link]");
    if (!links.length || !("IntersectionObserver" in window)) return;

    var map = {};
    var targets = [];

    Array.prototype.forEach.call(links, function (link) {
      var id = link.getAttribute("href").slice(1);
      var target = document.getElementById(id);
      if (!target) return;
      map[id] = link;
      targets.push(target);
    });

    var visible = {};

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          visible[entry.target.id] = entry.isIntersecting;
        });

        var activeId = null;
        for (var i = 0; i < targets.length; i++) {
          if (visible[targets[i].id]) { activeId = targets[i].id; break; }
        }

        Array.prototype.forEach.call(links, function (link) {
          link.dataset.active = "false";
        });
        if (activeId && map[activeId]) map[activeId].dataset.active = "true";
      },
      { rootMargin: "-20% 0px -65% 0px", threshold: 0 }
    );

    targets.forEach(function (t) { observer.observe(t); });
  }

  /* --------------------------------------------------- Barre de progression */

  function initProgress() {
    var bar = document.querySelector("[data-progress]");
    var article = document.querySelector("[data-article]");
    if (!bar || !article) return;

    var ticking = false;

    function update() {
      var rect = article.getBoundingClientRect();
      var total = rect.height - window.innerHeight;
      var scrolled = total > 0 ? Math.min(1, Math.max(0, -rect.top / total)) : 0;
      bar.style.transform = "scaleX(" + scrolled + ")";
      bar.style.width = "100%";
      ticking = false;
    }

    function onScroll() {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(update);
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    update();
  }

  /* ---------------------------------------------------- Barre d'achat mobile */

  function initBuybar() {
    var bar = document.querySelector("[data-buybar]");
    var trigger = document.querySelector("[data-buybar-after]");
    if (!bar) return;

    document.body.dataset.hasBuybar = "true";

    if (!trigger || !("IntersectionObserver" in window)) {
      bar.dataset.visible = "true";
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        bar.dataset.visible = String(entries[0].boundingClientRect.top < 0);
      },
      { threshold: 0 }
    );

    observer.observe(trigger);
  }

  /* --------------------------------------------------------- Apparitions */

  function initReveal() {
    var items = document.querySelectorAll("[data-reveal]");
    if (!items.length) return;

    if (reduced || !("IntersectionObserver" in window)) {
      Array.prototype.forEach.call(items, function (el) { el.dataset.revealed = "true"; });
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.dataset.revealed = "true";
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "200px 0px 0px 0px", threshold: 0.01 }
    );

    Array.prototype.forEach.call(items, function (el) { observer.observe(el); });

    // Filet de sécurité : rien ne doit rester masqué si l'observateur ne se
    // déclenche pas (onglet en arrière-plan, capture d'écran, navigateur exotique).
    window.setTimeout(function () {
      Array.prototype.forEach.call(items, function (el) { el.dataset.revealed = "true"; });
    }, 2500);
  }

  /* ------------------------------------------------------------------ Init */

  initTheme();
  initDrawer();
  initCompare();
  initToc();
  initProgress();
  initBuybar();
  initReveal();
})();
