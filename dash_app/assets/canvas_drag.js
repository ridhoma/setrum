/* Sticky-note drag for the Annotations canvas.
 *
 * Uses pointer events so it works for mouse and (later) touch. Event delegation
 * on document.body means newly-mounted notes pick up drag automatically.
 *
 * On drop (pointerup), the new (x, y) is published to the `sticky-position-store`
 * Dash component via `dash_clientside.set_props`, which fires a server callback
 * that persists to SQLite.
 *
 * Drag is suppressed when the pointer started inside an interactive element
 * (button) so the ✏️ / 🗑 icons keep working as clicks.
 */

(function () {
    "use strict";

    const STICKY_SELECTOR = ".canvas-sticky";
    const ACTION_SELECTOR = "button, .sticky-action-btn, a";
    const MOVE_THRESHOLD_PX = 4;          // <= treats short movements as a click

    let drag = null;

    function onPointerDown(e) {
        if (e.button !== 0 && e.button !== undefined) return;   // left mouse only
        // Yield to canvas pan/zoom: space-held = pan-mode, or pan already active.
        const cv = window.__setrumCanvas;
        if (cv && (cv.spaceHeld || cv.panning)) return;
        if (e.defaultPrevented) return;                         // pan handler claimed it
        const sticky = e.target.closest(STICKY_SELECTOR);
        if (!sticky) return;
        if (e.target.closest(ACTION_SELECTOR)) return;          // let buttons handle clicks

        const annId = parseInt((sticky.id || "").replace("canvas-sticky-", ""), 10);
        if (!Number.isFinite(annId)) return;

        const startLeft = parseInt(sticky.style.left || "0", 10) || 0;
        const startTop  = parseInt(sticky.style.top  || "0", 10) || 0;

        drag = {
            sticky,
            annId,
            pointerId: e.pointerId,
            startLeft,
            startTop,
            startX: e.clientX,
            startY: e.clientY,
            moved: false,
        };

        try { sticky.setPointerCapture(e.pointerId); } catch (_) { /* ok */ }
        sticky.classList.add("dragging");
        e.preventDefault();
    }

    function onPointerMove(e) {
        if (!drag) return;
        const cv = window.__setrumCanvas;
        // Convert screen-space pointer delta to canvas-local pixels, otherwise
        // at scale=2 the note travels twice as far as the cursor.
        const scale = (cv && typeof cv.getScale === "function") ? cv.getScale() : 1;
        const safeScale = scale > 0 ? scale : 1;
        const dx = (e.clientX - drag.startX) / safeScale;
        const dy = (e.clientY - drag.startY) / safeScale;
        if (!drag.moved && Math.hypot(dx, dy) * safeScale > MOVE_THRESHOLD_PX) {
            drag.moved = true;
        }
        if (drag.moved) {
            const left = Math.max(0, drag.startLeft + dx);
            const top  = Math.max(0, drag.startTop  + dy);
            drag.sticky.style.left = left + "px";
            drag.sticky.style.top  = top  + "px";
        }
    }

    function onPointerUp(e) {
        if (!drag) return;
        const sticky = drag.sticky;
        sticky.classList.remove("dragging");
        try { sticky.releasePointerCapture(drag.pointerId); } catch (_) { /* ok */ }

        if (drag.moved) {
            const left = parseInt(sticky.style.left || "0", 10) || 0;
            const top  = parseInt(sticky.style.top  || "0", 10) || 0;
            // Notify Dash so the server can persist (and other callbacks can react).
            // Include a timestamp so back-to-back drops always look like a new event.
            if (window.dash_clientside && window.dash_clientside.set_props) {
                window.dash_clientside.set_props("sticky-position-store", {
                    data: { id: drag.annId, x: left, y: top, ts: Date.now() },
                });
            }
        }
        drag = null;
    }

    function init() {
        // Use capture so we beat any inner pointer-listener that might stop propagation.
        document.body.addEventListener("pointerdown", onPointerDown, true);
        document.body.addEventListener("pointermove", onPointerMove, true);
        document.body.addEventListener("pointerup",   onPointerUp,   true);
        document.body.addEventListener("pointercancel", onPointerUp, true);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
