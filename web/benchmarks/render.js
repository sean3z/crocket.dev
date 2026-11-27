/* Enhance the pre-rendered results: sort tables, and re-render from data.json
   so a new data file drops in without a full HTML rebuild. */
(function () {
  "use strict";

  function fmtInt(n) {
    if (n == null || Number.isNaN(n)) return "–";
    return Math.round(n).toLocaleString("en-US");
  }

  function fmtDec(n, digits) {
    if (n == null || Number.isNaN(n)) return "–";
    return Number(n).toLocaleString("en-US", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    });
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function frameworkById(data, id) {
    var list = data.frameworks || [];
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return { id: id, name: id, version: "", language: "", highlight: false };
  }

  function resultsForTest(data, testId) {
    return (data.results || []).filter(function (r) { return r.test === testId; });
  }

  function maxOf(rows, key) {
    var m = 0;
    rows.forEach(function (r) {
      var v = r[key];
      if (typeof v === "number" && v > m) m = v;
    });
    return m || 1;
  }

  function flagHtml(row) {
    if (row.flags && row.flags.indexOf("lower-bound") !== -1) {
      return ' <span class="flag">lower bound</span>';
    }
    return "";
  }

  function renderBars(test, rows, data) {
    var max = maxOf(rows, "maxRps");
    var sorted = rows.slice().sort(function (a, b) { return b.maxRps - a.maxRps; });
    var html = '<figure class="bars"><div class="visually-hidden">' +
      esc(test.name) + ", max requests per second</div>";
    sorted.forEach(function (row) {
      var fw = frameworkById(data, row.framework);
      var pct = Math.max(0.5, (row.maxRps / max) * 100);
      var cls = fw.highlight ? " is-crocket" : "";
      html += '<div class="bar-row">' +
        '<p class="bar-name">' + esc(fw.name) +
          (fw.version ? '<span class="ver">' + esc(fw.version) + "</span>" : "") +
        "</p>" +
        '<div class="bar-track">' +
          '<svg class="bar-svg" viewBox="0 0 100 1" preserveAspectRatio="none" aria-hidden="true">' +
            '<rect class="bar-fill' + cls + '" x="0" y="0" width="' + pct.toFixed(2) + '" height="1"></rect>' +
          "</svg>" +
        "</div>" +
        '<p class="bar-n">' + fmtInt(row.maxRps) + '<span class="unit">req/s</span>' +
          flagHtml(row) + "</p>" +
      "</div>";
    });
    return html + "</figure>";
  }

  function missedRate(row) {
    return row.flags && row.flags.indexOf("couldnt-hold-rate") !== -1;
  }

  function latencyCells(row) {
    if (missedRate(row)) {
      if (row.heldP50Ms != null && row.heldP99Ms != null) {
        var rate = "at " + fmtInt(row.heldRate) + " req/s";
        return '<td class="num">' + fmtDec(row.heldP50Ms, 2) + ' ms<span class="held-rate">' + rate + "</span></td>" +
          '<td class="num">' + fmtDec(row.heldP99Ms, 2) + ' ms<span class="held-rate">' + rate + "</span></td>";
      }
      return '<td class="num">–</td><td class="num rate-miss">couldn\'t hold the rate</td>';
    }
    return '<td class="num">' + fmtDec(row.p50Ms, 2) + " ms</td>" +
      '<td class="num">' + fmtDec(row.p99Ms, 2) + " ms</td>";
  }

  function renderTable(test, rows, data) {
    var sorted = rows.slice().sort(function (a, b) { return b.maxRps - a.maxRps; });
    var rate = test.commonRate ? fmtInt(test.commonRate) + " req/s" : "the common rate";
    var html = '<div class="table-wrap"><table class="results" data-test="' + esc(test.id) + '">' +
      "<caption>Latency is at " + rate + "</caption>" +
      "<thead><tr>" +
      '<th data-sort="name" data-type="text">Framework</th>' +
      '<th class="num" data-sort="maxRps" data-type="num" aria-sort="descending">Max req/s<span class="sort-ind" aria-hidden="true">↓</span></th>' +
      '<th class="num" data-sort="cpuUsPerReq" data-type="num">CPU µs/req<span class="sort-ind" aria-hidden="true"></span></th>' +
      '<th class="num" data-sort="p50Ms" data-type="num">p50<span class="sort-ind" aria-hidden="true"></span></th>' +
      '<th class="num" data-sort="p99Ms" data-type="num">p99<span class="sort-ind" aria-hidden="true"></span></th>' +
      '<th class="num" data-sort="peakRssMb" data-type="num">Peak RSS<span class="sort-ind" aria-hidden="true"></span></th>' +
      '<th class="num" data-sort="idleRssMb" data-type="num">Idle RSS<span class="sort-ind" aria-hidden="true"></span></th>' +
      '<th class="num" data-sort="coldStartMs" data-type="num">Cold start<span class="sort-ind" aria-hidden="true"></span></th>' +
      "</tr></thead><tbody>";
    sorted.forEach(function (row) {
      var fw = frameworkById(data, row.framework);
      var trClass = fw.highlight ? ' class="is-crocket"' : "";
      html += "<tr" + trClass +
        ' data-name="' + esc(fw.name) + '"' +
        ' data-max-rps="' + row.maxRps + '"' +
        ' data-cpu-us-per-req="' + row.cpuUsPerReq + '"' +
        ' data-p50-ms="' + (missedRate(row) ? (row.heldP50Ms == null ? "" : row.heldP50Ms) : (row.p50Ms == null ? "" : row.p50Ms)) + '"' +
        ' data-p99-ms="' + (missedRate(row) ? (row.heldP99Ms == null ? "" : row.heldP99Ms) : (row.p99Ms == null ? "" : row.p99Ms)) + '"' +
        ' data-peak-rss-mb="' + row.peakRssMb + '"' +
        ' data-idle-rss-mb="' + (row.idleRssMb == null ? "" : row.idleRssMb) + '"' +
        ' data-cold-start-ms="' + (row.coldStartMs == null ? "" : row.coldStartMs) + '">' +
        '<th scope="row">' + esc(fw.name) +
          (fw.version ? '<span class="ver">' + esc(fw.version) + " · " + esc(fw.language) + "</span>" : "") +
        "</th>" +
        '<td class="num">' + fmtInt(row.maxRps) + flagHtml(row) + "</td>" +
        '<td class="num">' + fmtInt(row.cpuUsPerReq) + "</td>" +
        latencyCells(row) +
        '<td class="num">' + fmtInt(row.peakRssMb) + " MB</td>" +
        '<td class="num">' + (row.idleRssMb == null ? "–" : fmtInt(row.idleRssMb) + " MB") + "</td>" +
        '<td class="num">' + (row.coldStartMs == null ? "–" : fmtInt(row.coldStartMs) + " ms") + "</td>" +
      "</tr>";
    });
    html += "</tbody></table></div>";
    var fa = sorted.filter(function (r) { return r.framework === "fastapi" && missedRate(r); });
    var cr = sorted.filter(function (r) { return r.framework === "crocket" && r.heldP99Ms != null; })[0];
    if (fa.length && cr) {
      html += '<p class="table-note">At FastAPI\'s held rate for this test, crocket\'s p99 was around ' +
        fmtDec(cr.heldP99Ms, 2) + " milliseconds</p>";
    }
    return html;
  }

  function comingLine(data) {
    var coming = data.coming || [];
    if (!coming.length) return "";
    var names = coming.map(function (c) { return typeof c === "string" ? c : c.name; });
    var last = names.pop();
    var list = names.length ? names.join(", ") + ", and " + last : last;
    return '<p class="coming">' + esc(list) + " will show up here when those numbers land</p>";
  }

  function renderTestPanel(test, data) {
    var rows = resultsForTest(data, test.id);
    if (!rows.length || test.status === "pending") {
      return '<p class="pending-panel">' + esc(test.pendingNote || "This test is not in the current run yet") + "</p>";
    }
    var html = '<p class="test-blurb">' + esc(test.blurb) + "</p>" +
      renderBars(test, rows, data) +
      renderTable(test, rows, data);
    if (test.note) html += '<p class="test-note">' + esc(test.note) + "</p>";
    return html;
  }

  function bindSort(table) {
    var heads = table.querySelectorAll("thead th[data-sort]");
    heads.forEach(function (th) {
      th.addEventListener("click", function () {
        var key = th.getAttribute("data-sort");
        var type = th.getAttribute("data-type") || "num";
        var cur = th.getAttribute("aria-sort");
        var dir = cur === "descending" || cur === null || cur === "none" ? "ascending" : "descending";
        if (key === "maxRps" && (cur === null || cur === "none")) dir = "ascending";
        // First click on max (already desc) goes asc; first click on others goes desc (bigger first) for numbers, asc for text.
        if (cur === null || cur === "none") {
          dir = type === "text" ? "ascending" : (key === "maxRps" ? "ascending" : "descending");
        }
        heads.forEach(function (h) {
          h.removeAttribute("aria-sort");
          var ind = h.querySelector(".sort-ind");
          if (ind) ind.textContent = "";
        });
        th.setAttribute("aria-sort", dir);
        var ind = th.querySelector(".sort-ind");
        if (ind) ind.textContent = dir === "ascending" ? "↑" : "↓";
        var attr = {
          name: "data-name",
          maxRps: "data-max-rps",
          cpuUsPerReq: "data-cpu-us-per-req",
          p50Ms: "data-p50-ms",
          p99Ms: "data-p99-ms",
          peakRssMb: "data-peak-rss-mb",
          idleRssMb: "data-idle-rss-mb",
          coldStartMs: "data-cold-start-ms"
        }[key];
        var tbody = table.tBodies[0];
        var rows = Array.prototype.slice.call(tbody.rows);
        rows.sort(function (a, b) {
          var av = a.getAttribute(attr);
          var bv = b.getAttribute(attr);
          var cmp;
          if (type === "text") {
            cmp = (av || "").localeCompare(bv || "", "en", { sensitivity: "base" });
          } else {
            var an = av === "" || av == null ? NaN : Number(av);
            var bn = bv === "" || bv == null ? NaN : Number(bv);
            if (Number.isNaN(an) && Number.isNaN(bn)) cmp = 0;
            else if (Number.isNaN(an)) cmp = 1;
            else if (Number.isNaN(bn)) cmp = -1;
            else cmp = an - bn;
          }
          return dir === "ascending" ? cmp : -cmp;
        });
        rows.forEach(function (r) { tbody.appendChild(r); });
      });
    });
  }

  function bindAllSorts(root) {
    (root || document).querySelectorAll("table.results").forEach(bindSort);
  }

  function applyData(data) {
    var tests = data.tests || [];
    tests.forEach(function (test) {
      var panel = document.getElementById("panel-" + test.id);
      if (!panel) return;
      panel.innerHTML = renderTestPanel(test, data);
    });
    var coming = document.getElementById("coming-note");
    if (coming) coming.innerHTML = comingLine(data);
    bindAllSorts(document);
  }

  bindAllSorts(document);

  fetch("data.json", { cache: "no-store" })
    .then(function (res) { return res.ok ? res.json() : Promise.reject(res.status); })
    .then(applyData)
    .catch(function () { /* keep the pre-rendered markup */ });
})();

/* Memory soak chart: nearest-line hover/tap tooltips, legend focus, highlight the active line. */
(function () {
  function fmtT(t) { var m = Math.floor(t / 60), s = Math.round(t % 60); return m + ":" + (s < 10 ? "0" : "") + s; }
  function init(fig) {
    var svg = fig.querySelector(".soak-svg");
    var tip = fig.querySelector(".soak-tip");
    var cursor = svg.querySelector(".soak-cursor");
    var dot = svg.querySelector(".soak-dot");
    var lines = Array.prototype.slice.call(svg.querySelectorAll(".soak-line"));
    var series = lines.map(function (ln) {
      var pts = ln.getAttribute("points").split(" ").map(function (p) { var a = p.split(","); return [+a[0], +a[1]]; });
      var vals = ln.getAttribute("data-series").split(";").map(function (p) { var a = p.split(":"); return [+a[0], +a[1]]; });
      return { el: ln, fw: ln.getAttribute("data-fw"), name: ln.getAttribute("data-name"), pts: pts, vals: vals };
    });
    function activate(fw) {
      fig.classList.toggle("is-focus", !!fw);
      lines.forEach(function (ln) { ln.classList.toggle("is-active", ln.getAttribute("data-fw") === fw); });
      fig.querySelectorAll(".soak-key").forEach(function (b) { b.classList.toggle("is-active", b.getAttribute("data-fw") === fw); });
    }
    function show(s, i) {
      var p = s.pts[i], v = s.vals[i];
      cursor.setAttribute("x1", p[0]); cursor.setAttribute("x2", p[0]);
      dot.setAttribute("cx", p[0]); dot.setAttribute("cy", p[1]);
      dot.setAttribute("class", "soak-dot is-on " + (s.el.getAttribute("class").match(/series-\S+/) || [""])[0]);
      cursor.classList.add("is-on");
      tip.hidden = false;
      tip.textContent = s.name + " · " + v[1].toFixed(1) + " MB · " + fmtT(v[0]);
      var box = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
      var px = (p[0] / vb.width) * box.width, py = (p[1] / vb.height) * box.height;
      var fr = fig.getBoundingClientRect();
      var left = box.left - fr.left + px, top = box.top - fr.top + py;
      tip.style.left = Math.max(0, Math.min(left + 12, fig.clientWidth - tip.offsetWidth)) + "px";
      tip.style.top = Math.max(0, top - tip.offsetHeight - 10) + "px";
      activate(s.fw);
    }
    function hide() { tip.hidden = true; cursor.classList.remove("is-on"); dot.classList.remove("is-on"); activate(null); }
    function nearest(evt) {
      var box = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
      var e = evt.touches ? evt.touches[0] : evt;
      var x = ((e.clientX - box.left) / box.width) * vb.width, y = ((e.clientY - box.top) / box.height) * vb.height;
      var best = null, bi = 0, bd = Infinity;
      series.forEach(function (s) {
        var i = 0, d = Infinity;
        for (var k = 0; k < s.pts.length; k++) { var dx = Math.abs(s.pts[k][0] - x); if (dx < d) { d = dx; i = k; } }
        var dy = Math.abs(s.pts[i][1] - y);
        if (dy < bd) { bd = dy; best = s; bi = i; }
      });
      if (best) show(best, bi);
    }
    svg.addEventListener("mousemove", nearest);
    svg.addEventListener("touchstart", nearest, { passive: true });
    svg.addEventListener("touchmove", nearest, { passive: true });
    svg.addEventListener("mouseleave", hide);
    fig.querySelectorAll(".soak-key").forEach(function (b) {
      var s = series.filter(function (x) { return x.fw === b.getAttribute("data-fw"); })[0];
      if (!s) return;
      var on = function () { show(s, s.pts.length - 1); };
      b.addEventListener("mouseenter", on); b.addEventListener("focus", on); b.addEventListener("click", on);
      b.addEventListener("mouseleave", hide); b.addEventListener("blur", hide);
    });
  }
  function boot() { document.querySelectorAll("[data-soak-chart]").forEach(init); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
