/**
 * Setrum — Option 1: Editorial Field Notes Rail Interactions
 *
 * 1. Toggle right field notes rail (collapse / expand).
 * 2. Hover highlight synchronization between rail cards and chart bands.
 */

(function () {
    "use strict";

    document.addEventListener("click", function (e) {
        var toggleBtn = e.target.closest("#toggle-rail-btn");
        if (toggleBtn) {
            var workbench = document.getElementById("workbench");
            if (workbench) {
                workbench.classList.toggle("rail-collapsed");
                toggleBtn.classList.toggle("active");
            }
        }
    });

    document.addEventListener("mouseover", function (e) {
        var railCard = e.target.closest(".rail-card");
        if (railCard) {
            document.querySelectorAll(".shapelayer path").forEach(function (p) {
                p.classList.add("highlighted-shape");
            });
            document.querySelectorAll(".scatterlayer .textpoint text").forEach(function (t) {
                if (t.textContent && t.textContent.includes("📝")) {
                    t.style.transform = "scale(1.3)";
                    t.style.transition = "transform 150ms ease";
                }
            });
        }
    });

    document.addEventListener("mouseout", function (e) {
        var railCard = e.target.closest(".rail-card");
        if (railCard) {
            document.querySelectorAll(".shapelayer path").forEach(function (p) {
                p.classList.remove("highlighted-shape");
            });
            document.querySelectorAll(".scatterlayer .textpoint text").forEach(function (t) {
                if (t.textContent && t.textContent.includes("📝")) {
                    t.style.transform = "";
                }
            });
        }
    });
})();
