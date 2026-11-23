// Types the illustrative exchange once it scrolls into view.
// The HTML already holds the final words, so the page is complete with script off.
(function () {
  var root = document.querySelector("[data-exchange]");
  if (!root) return;

  var promptEl = root.querySelector("blockquote");
  var answerEl = root.querySelector(".exchange-answer");
  var codeEl = root.querySelector("pre code");
  var replay = root.querySelector(".exchange-replay");
  var responseLabel = root.querySelectorAll(".exchange-label")[1];
  if (!promptEl || !answerEl || !codeEl || !replay || !responseLabel) return;

  var promptText = promptEl.textContent;
  var answerText = answerEl.textContent;
  var codeText = codeEl.textContent;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var thoughts = [
    "35.2k req/s and 21 MB on the Heroes rig.",
    "The handler is the review."
  ];

  function showFinal() {
    promptEl.textContent = promptText;
    answerEl.textContent = answerText;
    codeEl.textContent = codeText;
    var think = root.querySelector(".exchange-think");
    if (think) think.remove();
    root.removeAttribute("aria-busy");
  }

  replay.hidden = false;
  if (reduce) {
    replay.addEventListener("click", showFinal);
    return;
  }

  var runId = 0;

  function wait(ms, id) {
    return new Promise(function (resolve) {
      setTimeout(function () { resolve(id === runId); }, ms);
    });
  }

  function stream(el, text, duration, id) {
    return new Promise(function (resolve) {
      var t0 = performance.now();
      function tick(now) {
        if (id !== runId) return resolve(false);
        var p = Math.min(1, (now - t0) / duration);
        var n = p === 1 ? text.length : Math.floor(text.length * p);
        el.textContent = text.slice(0, n);
        var mark = document.createElement("span");
        mark.className = "caret";
        mark.setAttribute("aria-hidden", "true");
        el.appendChild(mark);
        if (p < 1) requestAnimationFrame(tick);
        else {
          mark.remove();
          resolve(true);
        }
      }
      requestAnimationFrame(tick);
    });
  }

  async function play(id) {
    var old = root.querySelector(".exchange-think");
    if (old) old.remove();
    promptEl.textContent = "";
    answerEl.textContent = "";
    codeEl.textContent = "";
    root.setAttribute("aria-busy", "true");

    var mark = document.createElement("span");
    mark.className = "caret";
    mark.setAttribute("aria-hidden", "true");
    promptEl.appendChild(mark);

    if (!(await stream(promptEl, promptText, 1600, id))) return;
    if (!(await wait(200, id))) return;

    var think = document.createElement("ol");
    think.className = "exchange-think";
    responseLabel.before(think);
    for (var i = 0; i < thoughts.length; i++) {
      var li = document.createElement("li");
      li.textContent = thoughts[i];
      think.appendChild(li);
      requestAnimationFrame(function (item) {
        return function () { item.classList.add("is-in"); };
      }(li));
      if (!(await wait(700, id))) return;
    }
    think.classList.add("is-collapsed");
    if (!(await wait(420, id))) return;
    if (id !== runId) return;
    think.remove();

    if (!(await stream(answerEl, answerText, 1800, id))) return;
    if (!(await wait(160, id))) return;
    if (!(await stream(codeEl, codeText, 2200, id))) return;
    if (id !== runId) return;
    var leftover = codeEl.querySelector(".caret");
    if (leftover) leftover.remove();
    root.removeAttribute("aria-busy");
  }

  function start() {
    play(++runId);
  }

  replay.addEventListener("click", function () {
    root.scrollIntoView({ block: "nearest", inline: "nearest" });
    start();
  });

  var started = false;
  if (!("IntersectionObserver" in window)) {
    start();
    return;
  }
  var watcher = new IntersectionObserver(function (entries) {
    if (started || !entries.some(function (entry) { return entry.isIntersecting; })) return;
    started = true;
    watcher.disconnect();
    start();
  }, { threshold: 0.25 });
  watcher.observe(root);
})();
