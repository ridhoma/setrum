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

    // Drag-range selection & hover range preview on the Data Health Coverage Matrix
    var dragStartTile = null;
    var dragCurrentTile = null;

    function highlightPreviewRange(d1, d2) {
        var s = d1 < d2 ? d1 : d2;
        var e = d1 < d2 ? d2 : d1;
        document.querySelectorAll(".dh-hm-cell").forEach(function (el) {
            var dt = el.getAttribute("data-date");
            if (dt && dt >= s && dt <= e) {
                el.classList.add("dh-hm-cell--drag-preview");
            } else {
                el.classList.remove("dh-hm-cell--drag-preview");
            }
        });
    }

    function clearPreviewRange() {
        document.querySelectorAll(".dh-hm-cell--drag-preview").forEach(function (el) {
            el.classList.remove("dh-hm-cell--drag-preview");
        });
    }

    document.addEventListener("mousedown", function (e) {
        var tile = e.target.closest(".dh-hm-cell");
        if (tile) {
            dragStartTile = tile;
            dragCurrentTile = tile;
        }
    });

    document.addEventListener("mouseover", function (e) {
        if (!dragStartTile) return;
        var tile = e.target.closest(".dh-hm-cell");
        if (tile) {
            dragCurrentTile = tile;
            var d1 = dragStartTile.getAttribute("data-date");
            var d2 = dragCurrentTile.getAttribute("data-date");
            if (d1 && d2 && d1 !== d2) {
                highlightPreviewRange(d1, d2);
            }
        }
    });

    document.addEventListener("mouseup", function () {
        if (dragStartTile && dragCurrentTile && dragStartTile !== dragCurrentTile) {
            var startEl = dragStartTile;
            var endEl = dragCurrentTile;
            dragStartTile = null;
            dragCurrentTile = null;
            clearPreviewRange();
            // Dispatch click on start tile, then end tile to select the range in Dash
            startEl.click();
            setTimeout(function () {
                endEl.click();
            }, 90);
            return;
        }
        dragStartTile = null;
        dragCurrentTile = null;
        clearPreviewRange();
    });
})();
