/* Refine runtime for legacy Anki webviews. Loaded at the start of <body>. */
(function () {
  "use strict";
  if (window.rfApply) return;

  // Live settings: toggle Refine's html classes and swap the token stylesheet.
  window.rfApply = function (p) {
    var d = document.documentElement;
    // card webviews only ever carry the card-layer classes, never tokens
    var cardsOnly = d.dataset.rfScope === "cards";
    Object.keys(p.flags || {}).forEach(function (k) {
      if (cardsOnly && !/^rf-(cards|furigana)-/.test(k)) return;
      d.classList.toggle(k, !!p.flags[k]);
    });
    // pages that reset <html> classes keep a wanted-list (see overview.py)
    if (window.rfKeep) {
      window.rfKeep = window.rfKeep.filter(function (k) {
        return !(k in p.flags) || p.flags[k];
      }).concat(Object.keys(p.flags).filter(function (k) {
        return p.flags[k] && window.rfKeep.indexOf(k) < 0 && /^(refine|rf-s-[\w-]+)$/.test(k);
      }));
    }
    if (p.tokens && p.styleId && !cardsOnly) {
      var s = document.getElementById(p.styleId);
      if (!s) {
        s = document.createElement("style");
        s.id = p.styleId;
        document.head.appendChild(s);
      }
      s.textContent = p.tokens;
    }
  };

  window.rfSetState = function (state) {
    document.documentElement.dataset.rfState = state;
  };

  // Home panels: data arrives from a background query after render.
  window.rfFillHome = function (p) {
    Object.keys(p).forEach(function (key) {
      if (key === "avgMs") {
        window.rfSetAvgMs(p.avgMs);
        return;
      }
      var el = document.querySelector('[data-rf-fill="' + key + '"]');
      if (el) el.innerHTML = p[key];
    });
  };

  // ------------------------------------------------------------- Home
  // Selecting a deck (click anywhere on its row) shows that deck's numbers in
  // the headline; nothing selected shows all decks combined. Everything
  // updates in place; Anki is told in the background (no reload).
  var deckData = null;

  function selectMode() {
    return document.documentElement.classList.contains("rf-click-select");
  }

  function fmtInt(n) {
    return Number(n || 0).toLocaleString("en-US");
  }

  function fmtDuration(ms) {
    var secs = Math.round(ms / 1000);
    if (secs < 60) return secs + "s";
    var mins = Math.round(secs / 60);
    if (mins < 60) return mins + " min";
    var h = Math.floor(mins / 60), m = mins % 60;
    return m ? h + " h " + m + " min" : h + " h";
  }

  function hint(text) {
    var span = document.createElement("span");
    span.className = "rf-hero-hint rf-muted";
    span.textContent = text;
    return span;
  }

  function renderHero() {
    var hero = document.querySelector(".rf-hero:not(.rf-onboarding)");
    if (!hero || !deckData) return;
    var id = deckData.selected;
    var d = id != null ? deckData.decks[String(id)] : null;
    var c = d || deckData.all;
    var due = c["new"] + c.learn + c.review;
    var scope = hero.querySelector(".rf-hero-scope");
    if (scope) scope.textContent = d ? d.name : "All decks";
    var title = hero.querySelector(".rf-hero-title");
    if (title) title.textContent = due ? fmtInt(due) + " card" + (due !== 1 ? "s" : "") + " waiting" : "All caught up";
    ["new", "learn", "review"].forEach(function (k) {
      var b = hero.querySelector('[data-rf="' + k + '"]');
      if (b) b.textContent = fmtInt(c[k]);
    });
    var pace = document.getElementById("rf-pace");
    if (pace) pace.textContent = due && deckData.avgMs > 0 ? "≈ " + fmtDuration(due * deckData.avgMs) + " at your pace" : "";
    var action = hero.querySelector(".rf-hero-action");
    if (!action) return;
    action.textContent = "";
    if (!d) {
      action.appendChild(hint("Choose a deck below to study it"));
    } else if (!due) {
      action.appendChild(hint("Nothing due in " + d.name));
    } else {
      var btn = document.createElement("button");
      btn.className = "rf-btn rf-btn-primary rf-btn-lg";
      btn.title = "Study " + d.name;
      btn.setAttribute("onclick", "return pycmd('refine:deck_browser:study:" + Number(id) + "')");
      btn.appendChild(document.createTextNode("Study "));
      var label = document.createElement("span");
      label.className = "rf-hero-deck";
      label.textContent = d.name;
      btn.appendChild(label);
      action.appendChild(btn);
    }
  }

  function markSelected() {
    var rows = document.querySelectorAll("tr.deck.rf-selected");
    for (var r = 0; r < rows.length; r++) {
      rows[r].classList.remove("rf-selected");
      var old = rows[r].querySelector("a.deck");
      if (old) old.removeAttribute("aria-current");
    }
    if (deckData && deckData.selected != null) {
      var row = document.getElementById(String(deckData.selected));
      if (row) {
        row.classList.add("rf-selected");
        var link = row.querySelector("a.deck");
        if (link) link.setAttribute("aria-current", "true");
      }
    }
  }

  function selectDeck(id) {
    if (!deckData || String(deckData.selected) === String(id)) return;
    deckData.selected = Number(id);
    markSelected();
    renderHero();
    pycmd("refine:deck_browser:select:" + id);
  }

  function deselectDeck() {
    if (!deckData || deckData.selected == null) return;
    deckData.selected = null;
    markSelected();
    renderHero();
    pycmd("refine:deck_browser:deselect");
  }

  // background stats arrive later: keep the headline's pace in step
  window.rfSetAvgMs = function (ms) {
    if (deckData) {
      deckData.avgMs = ms;
      renderHero();
    }
  };

  function isControl(el) {
    return !!(el && el.closest && el.closest("button, a.collapse, td.opts, input, label, select, textarea"));
  }

  var INFO_ICON = '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" ' +
    'stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><circle cx="8" cy="8" r="6"/>' +
    '<path d="M8 7.25V11"/><circle cx="8" cy="5" r="0.6" fill="currentColor" stroke="none"/></svg>';

  // Deck list: annotate rows, wire selection, add Study and info buttons.
  // Anki's own markup, handlers and drag-and-drop are left in place.
  function enhanceDeckRows() {
    var el = document.getElementById("rf-deck-data");
    if (el) {
      try { deckData = JSON.parse(el.textContent); } catch (e) { deckData = null; }
    }
    var rows = document.querySelectorAll("tr.deck");
    for (var i = 0; i < rows.length; i++) {
      var tr = rows[i];
      if (tr.dataset.rfDone) continue;
      tr.dataset.rfDone = "1";
      var td = tr.querySelector("td.decktd");
      var lead = td && td.firstChild && td.firstChild.nodeType === 3 ? td.firstChild.nodeValue : "";
      var nbsp = (lead.match(/ /g) || []).length;
      tr.dataset.rfDepth = String(Math.round(nbsp / 6));
      if (tr.querySelector(".new-count, .learn-count, .review-count")) tr.classList.add("rf-has-due");
      var link = tr.querySelector("a.deck");
      var name = link ? link.textContent.trim() : "";
      var collapse = tr.querySelector("a.collapse");
      if (collapse) {
        var txt = collapse.textContent.trim();
        var open = txt === "−" || txt === "-";
        collapse.classList.add(open ? "rf-open" : "rf-closed");
        collapse.setAttribute("aria-expanded", open ? "true" : "false");
        collapse.setAttribute("aria-label", (open ? "Collapse " : "Expand ") + name);
        collapse.title = open ? "Collapse" : "Expand";
      }
      if (!/^\d+$/.test(tr.id)) continue;
      (function (id, row, nameLink) {
        if (nameLink) {
          // the name link would open the overview (Anki's inline handler);
          // in select mode the row's click handler below selects instead
          nameLink.addEventListener("click", function (ev) {
            if (!selectMode() || ev.shiftKey) return;
            ev.preventDefault();
            ev.stopImmediatePropagation();
          }, true);
        }
        row.addEventListener("click", function (ev) {
          if (!selectMode() || ev.shiftKey || isControl(ev.target)) return;
          ev.preventDefault();
          selectDeck(id);
        });
        row.addEventListener("dblclick", function (ev) {
          if (!selectMode() || isControl(ev.target)) return;
          ev.preventDefault();
          pycmd("open:" + id);
        });
      })(tr.id, tr, link);
      var opts = tr.querySelector("td.opts");
      if (opts) {
        var gear = opts.querySelector("a");
        if (gear) {
          gear.setAttribute("role", "button");
          gear.setAttribute("tabindex", "0");
          gear.setAttribute("aria-label", "Options for " + name);
          gear.title = "Options";
          gear.addEventListener("keydown", function (ev) {
            if (ev.key === "Enter" || ev.key === " ") {
              ev.preventDefault();
              this.click();
            }
          });
        }
        var info = document.createElement("button");
        info.className = "rf-row-info";
        info.type = "button";
        info.innerHTML = INFO_ICON;
        info.title = "Deck details";
        info.setAttribute("aria-label", "Open " + name + " overview");
        info.addEventListener("click", (function (id) {
          return function (ev) {
            ev.stopPropagation();
            pycmd("open:" + id);
          };
        })(tr.id));
        opts.insertBefore(info, gear || null);
        var b = document.createElement("button");
        b.className = "rf-row-study";
        b.type = "button";
        b.textContent = "Study";
        b.setAttribute("aria-label", "Study " + name);
        b.addEventListener("click", (function (id) {
          return function (ev) {
            ev.stopPropagation();
            pycmd("refine:deck_browser:study:" + id);
          };
        })(tr.id));
        opts.insertBefore(b, opts.firstChild);
      }
    }
    markSelected();
    // a click anywhere that isn't a deck row or a control clears the selection
    document.addEventListener("click", function (ev) {
      if (!selectMode() || !deckData) return;
      var t = ev.target;
      if (t && t.closest && (t.closest("tr.deck") || t.closest("button, a, input, label, .rf-shell, .rf-header"))) return;
      deselectDeck();
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && selectMode()) deselectDeck();
    });
  }

  // Ctrl+K focuses the header search (shell pages only; Anki doesn't use it here)
  document.addEventListener("keydown", function (ev) {
    if ((ev.ctrlKey || ev.metaKey) && !ev.altKey && !ev.shiftKey && (ev.key === "k" || ev.key === "K")) {
      var input = document.querySelector(".rf-search input");
      if (input) {
        ev.preventDefault();
        input.focus();
      }
    }
  });

  // Overview: Esc goes back to Home.
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && document.documentElement.classList.contains("rf-page-Overview")) {
      ev.preventDefault();
      pycmd("decks");
    }
  });

  function onReady() {
    if (document.documentElement.classList.contains("rf-page-DeckBrowser")) enhanceDeckRows();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", onReady);
  } else {
    onReady();
  }
})();
