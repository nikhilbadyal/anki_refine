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
      if (key === "retention") {
        if (deckData) {
          deckData.retention = p.retention;
          renderRetention();
        }
        return;
      }
      if (key === "progress" || key === "leeches") {
        if (deckData) {
          deckData[key] = p[key];
          renderDeckExtras();
          renderHero();
        }
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

  // mirrors home.eta_text: days under 14 days, weeks up to 16 weeks, then months
  function etaText(p) {
    if (!p || !(p.left > 0) || !(p.perDay > 0)) return "";
    var days = Math.ceil(p.left / p.perDay), span;
    if (days < 14) span = days + " day" + (days !== 1 ? "s" : "");
    else if (days <= 112) span = Math.round(days / 7) + " weeks";
    else span = Math.round(days / 30) + " months";
    return "≈ " + span + " to finish new cards at " + fmtInt(p.perDay) + "/day";
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
    var eta = document.getElementById("rf-eta");
    if (eta) eta.textContent = d ? etaText(deckData.progress && deckData.progress[String(id)]) : "";
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

  // Retention column: Anki's true retention over the last 30 days (review
  // answers that weren't Again), including subdecks; "—" when too few.
  function renderRetention() {
    if (!deckData) return;
    var map = deckData.retention || {};
    var cells = document.querySelectorAll("td.rf-ret");
    for (var i = 0; i < cells.length; i++) {
      var cell = cells[i];
      var id = cell.parentNode.id;
      var pct = map[id];
      cell.textContent = "";
      if (pct === undefined || pct === null) {
        var none = document.createElement("span");
        none.className = "rf-ret-val rf-ret-none";
        none.textContent = "—";
        none.title = "Not enough reviews in the last 30 days";
        cell.appendChild(none);
        continue;
      }
      var bar = document.createElement("span");
      bar.className = "rf-ret-bar" + (pct < 85 ? " rf-ret-low" : "");
      bar.setAttribute("aria-hidden", "true");
      var fill = document.createElement("i");
      // 60-100% scale, as in the design: differences that matter stay visible
      fill.style.width = Math.max(4, Math.min(100, (pct - 60) * 2.5)) + "%";
      bar.appendChild(fill);
      var val = document.createElement("span");
      val.className = "rf-ret-val";
      val.textContent = pct + "%";
      cell.title = pct + "% of reviews remembered (last 30 days)";
      cell.appendChild(bar);
      cell.appendChild(val);
    }
  }

  // Per-deck extras under/after the name: "N new left · P% introduced" with a
  // thin bar, and a leech pill that opens the Browser on those cards.
  function renderDeckExtras() {
    if (!deckData) return;
    var prog = deckData.progress || {}, leeches = deckData.leeches || {};
    var rows = document.querySelectorAll("tr.deck");
    for (var i = 0; i < rows.length; i++) {
      var tr = rows[i];
      if (!/^\d+$/.test(tr.id)) continue;
      var td = tr.querySelector("td.decktd");
      var link = tr.querySelector("a.deck");
      if (!td || !link) continue;
      var old = td.querySelectorAll(".rf-prog, .rf-leech");
      for (var o = 0; o < old.length; o++) old[o].remove();
      var name = link.textContent.trim();
      var n = leeches[tr.id];
      if (n > 0) {
        var lb = document.createElement("button");
        lb.type = "button";
        lb.className = "rf-leech";
        lb.textContent = n + " leech" + (n !== 1 ? "es" : "");
        lb.title = "Show leech cards in the Browser";
        lb.setAttribute("aria-label", "Show " + n + " leech card" + (n !== 1 ? "s" : "") + " in " + name);
        lb.addEventListener("click", (function (id) {
          return function (ev) {
            ev.stopPropagation();
            ev.preventDefault();
            pycmd("refine:deck_browser:leeches:" + id);
          };
        })(tr.id));
        link.insertAdjacentElement("afterend", lb);
      }
      var p = prog[tr.id];
      if (p && p.left > 0 && p.total > 0) {
        var pct = Math.round(100 * (p.total - p.left) / p.total);
        var box = document.createElement("div");
        box.className = "rf-prog";
        var pad = parseFloat(getComputedStyle(td).paddingLeft) || 0;
        box.style.marginInlineStart = Math.max(0, link.offsetLeft - pad) + "px";
        var txt = document.createElement("span");
        txt.className = "rf-prog-text";
        txt.textContent = fmtInt(p.left) + " new left · " + pct + "% introduced";
        var track = document.createElement("span");
        track.className = "rf-prog-bar";
        track.setAttribute("aria-hidden", "true");
        var fill = document.createElement("i");
        fill.style.width = pct + "%";
        track.appendChild(fill);
        box.appendChild(txt);
        box.appendChild(track);
        td.appendChild(box);
      }
    }
  }

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
      if (opts && !tr.querySelector("td.rf-ret")) {
        var ret = document.createElement("td");
        ret.className = "rf-ret";
        tr.insertBefore(ret, opts);
      }
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
    var optsHead = document.querySelector("th.optscol");
    if (optsHead && !document.querySelector("th.rf-ret-h")) {
      var th = document.createElement("th");
      th.className = "count rf-ret-h";
      th.textContent = "Retention";
      th.title = "Reviews remembered in the last 30 days";
      optsHead.parentNode.insertBefore(th, optsHead);
    }
    var spacer = document.querySelector("tr.top-level-drag-row td");
    if (spacer) spacer.colSpan = 7;
    renderRetention();
    renderDeckExtras();
    renderHero();
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
