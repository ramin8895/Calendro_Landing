/* Calendro landing — small progressive enhancements. The site works without JS. */
(function () {
  "use strict";

  var header = document.querySelector("[data-header]");
  var toggle = document.querySelector("[data-nav-toggle]");

  // Mobile navigation
  if (header && toggle) {
    var setOpen = function (open) {
      header.classList.toggle("nav-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    };
    toggle.addEventListener("click", function () {
      setOpen(!header.classList.contains("nav-open"));
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && header.classList.contains("nav-open")) {
        setOpen(false);
        toggle.focus();
      }
    });
    header.addEventListener("click", function (e) {
      if (e.target.closest(".main-nav a")) setOpen(false);
    });
    window.matchMedia("(min-width: 1024px)").addEventListener("change", function (mq) {
      if (mq.matches) setOpen(false);
    });
  }

  // Header border once the page scrolls
  if (header) {
    var onScroll = function () {
      header.classList.toggle("is-scrolled", window.scrollY > 8);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  // Table of contents starts collapsed on small screens so content comes first
  if (window.matchMedia("(max-width: 1079.98px)").matches) {
    document.querySelectorAll(".toc details[open]").forEach(function (d) { d.removeAttribute("open"); });
  }

  // Copy buttons (SMS templates)
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var target = document.getElementById(btn.getAttribute("data-copy"));
      if (!target) return;
      var text = target.innerText.trim();
      var label = btn.querySelector("[data-label]");
      var done = function () {
        btn.setAttribute("data-copied", "");
        if (label) label.textContent = "کپی شد";
        setTimeout(function () {
          btn.removeAttribute("data-copied");
          if (label) label.textContent = "کپی متن";
        }, 1800);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done);
      } else {
        var ta = document.createElement("textarea");
        ta.value = text;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); done(); } catch (err) { /* ignore */ }
        document.body.removeChild(ta);
      }
    });
  });
})();
