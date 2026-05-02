/* FigJam-style pan/zoom for the annotations canvas.
 *
 * The viewport (`.annotations-canvas-viewport`) is a fixed-size stage with
 * `overflow: hidden`. Inside it sits `.annotations-canvas-content`, which gets
 * a CSS `transform: translate(tx, ty) scale(s)` applied here. `transform-origin`
 * is `0 0` so cursor-anchored zoom math is straightforward.
 *
 * Interactions:
 *   • trackpad two-finger swipe              → pan
 *   • pinch (browser delivers ctrlKey wheel) → zoom around cursor
 *   • ⌘/Ctrl + wheel                         → zoom around cursor
 *   • plain mouse wheel                      → pan vertically
 *   • space + drag, middle-mouse drag,
 *     or drag on empty canvas (primary btn)  → pan
 *   • zoom toolbar buttons                   → zoom in / out / reset / fit
 *
 * Sticky-note drag (in canvas_drag.js) reads `window.__setrumCanvas.getScale()`
 * to convert screen-space pointer deltas into canvas-local pixels, and
 * `window.__setrumCanvas.spaceHeld` so it can yield to canvas pan when space
 * is down.
 */

(function () {
    "use strict";

    const VIEWPORT_SELECTOR = ".annotations-canvas-viewport";
    const CONTENT_SELECTOR  = ".annotations-canvas-content";
    const CANVAS_SELECTOR   = ".annotations-canvas";
    const STICKY_SELECTOR   = ".canvas-sticky";
    const CONTROLS_SELECTOR = ".canvas-zoom-controls";

    const SCALE_MIN  = 0.2;
    const SCALE_MAX  = 3.0;
    const ZOOM_STEP  = 1.2;          // toolbar +/- multiplier
    const WHEEL_ZOOM_K = 0.0015;     // ctrl-wheel sensitivity (per deltaY pixel)
    const PAN_THRESHOLD_PX = 4;

    // Single source of truth for the transform. Always reflects what's on
    // `.annotations-canvas-content` style.transform.
    const state = {
        tx: 0,
        ty: 0,
        scale: 1,
        spaceHeld: false,
        panning: null,    // { startX, startY, startTx, startTy, pointerId, target } or null
    };

    // Expose to the drag module and the rest of the app.
    window.__setrumCanvas = {
        getScale: () => state.scale,
        getTransform: () => ({ tx: state.tx, ty: state.ty, scale: state.scale }),
        get spaceHeld() { return state.spaceHeld; },
        get panning()   { return state.panning != null; },
    };

    function getViewport() { return document.querySelector(VIEWPORT_SELECTOR); }
    function getContent()  { return document.querySelector(CONTENT_SELECTOR);  }

    function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }

    // Base cell sizes for the two stacked dot layers (must match
    // `.annotations-canvas-viewport` background-size in setrum.css).
    const DOT_CELL_A = 36;
    const DOT_CELL_B = 56;

    function applyTransform() {
        const content = getContent();
        if (!content) return;
        content.style.transform =
            `translate(${state.tx}px, ${state.ty}px) scale(${state.scale})`;

        // Tile the dot pattern across the viewport, anchored to canvas
        // (0,0) so dots feel pinned to canvas space and the surface reads
        // as endless. Both size and position track the transform.
        const viewport = getViewport();
        if (viewport) {
            const a = DOT_CELL_A * state.scale;
            const b = DOT_CELL_B * state.scale;
            viewport.style.backgroundSize = `${a}px ${a}px, ${b}px ${b}px`;
            viewport.style.backgroundPosition =
                `${state.tx}px ${state.ty}px, ${state.tx}px ${state.ty}px`;
        }

        const readout = document.querySelector(`${CONTROLS_SELECTOR} .zoom-readout`);
        if (readout) readout.textContent = `${Math.round(state.scale * 100)}%`;
    }

    function setTransform(tx, ty, scale) {
        state.tx = tx;
        state.ty = ty;
        state.scale = clamp(scale, SCALE_MIN, SCALE_MAX);
        applyTransform();
    }

    /* Zoom by `factor`, keeping the world point under (clientX, clientY) fixed. */
    function zoomAt(factor, clientX, clientY) {
        const viewport = getViewport();
        if (!viewport) return;
        const rect = viewport.getBoundingClientRect();
        const vx = clientX - rect.left;        // pointer in viewport coords
        const vy = clientY - rect.top;

        const newScale = clamp(state.scale * factor, SCALE_MIN, SCALE_MAX);
        if (newScale === state.scale) return;

        // World coord under the cursor before the zoom.
        const worldX = (vx - state.tx) / state.scale;
        const worldY = (vy - state.ty) / state.scale;

        state.scale = newScale;
        state.tx = vx - worldX * newScale;
        state.ty = vy - worldY * newScale;
        applyTransform();
    }

    function zoomToCenter(factor) {
        const viewport = getViewport();
        if (!viewport) return;
        const rect = viewport.getBoundingClientRect();
        zoomAt(factor, rect.left + rect.width / 2, rect.top + rect.height / 2);
    }

    function resetView() {
        setTransform(0, 0, 1);
    }

    /* Fit-to-content: bounding box of all `.canvas-sticky`, scaled to fit
       the viewport with a comfortable margin. Falls back to reset if there
       are no notes. */
    function fitToContent() {
        const viewport = getViewport();
        const stickies = document.querySelectorAll(STICKY_SELECTOR);
        if (!viewport || stickies.length === 0) {
            resetView();
            return;
        }
        let minX =  Infinity, minY =  Infinity;
        let maxX = -Infinity, maxY = -Infinity;
        stickies.forEach((el) => {
            const x = parseInt(el.style.left || "0", 10) || 0;
            const y = parseInt(el.style.top  || "0", 10) || 0;
            const w = el.offsetWidth  || 240;
            const h = el.offsetHeight || 200;
            if (x < minX) minX = x;
            if (y < minY) minY = y;
            if (x + w > maxX) maxX = x + w;
            if (y + h > maxY) maxY = y + h;
        });
        const margin = 80;
        const contentW = (maxX - minX) + margin * 2;
        const contentH = (maxY - minY) + margin * 2;
        const rect = viewport.getBoundingClientRect();
        const scale = clamp(
            Math.min(rect.width / contentW, rect.height / contentH),
            SCALE_MIN, SCALE_MAX,
        );
        // Center the bbox in the viewport.
        const bboxCx = (minX + maxX) / 2;
        const bboxCy = (minY + maxY) / 2;
        const tx = rect.width  / 2 - bboxCx * scale;
        const ty = rect.height / 2 - bboxCy * scale;
        setTransform(tx, ty, scale);
    }

    /* ── Wheel: pan by default, zoom with ctrlKey (incl. trackpad pinch) ── */
    function onWheel(e) {
        const viewport = getViewport();
        if (!viewport) return;
        if (!viewport.contains(e.target)) return;
        // Don't hijack scrolling inside floating controls.
        if (e.target.closest(CONTROLS_SELECTOR)) return;

        e.preventDefault();
        if (e.ctrlKey || e.metaKey) {
            // Pinch-zoom (browsers map pinch → ctrlKey wheel) or ⌘/Ctrl + wheel.
            const factor = Math.exp(-e.deltaY * WHEEL_ZOOM_K);
            zoomAt(factor, e.clientX, e.clientY);
        } else {
            state.tx -= e.deltaX;
            state.ty -= e.deltaY;
            applyTransform();
        }
    }

    /* ── Canvas pan: middle-mouse or space+drag ──
       Primary-button on empty canvas is owned by canvas_drag.js (marquee
       select). The trackpad / wheel gestures still pan via onWheel. */
    function shouldStartCanvasPan(e) {
        if (e.button === 1) return true;             // middle mouse
        if (e.button !== 0 && e.button !== undefined) return false;
        if (state.spaceHeld) return true;            // space + any primary
        return false;
    }

    function onPointerDown(e) {
        const viewport = getViewport();
        if (!viewport || !viewport.contains(e.target)) return;
        if (!shouldStartCanvasPan(e)) return;

        state.panning = {
            startX: e.clientX,
            startY: e.clientY,
            startTx: state.tx,
            startTy: state.ty,
            pointerId: e.pointerId,
            moved: false,
        };
        try { viewport.setPointerCapture(e.pointerId); } catch (_) { /* ok */ }
        viewport.classList.add("is-panning");
        // Capture-phase, called before sticky-drag; preventDefault keeps the
        // sticky-drag handler's pointerdown from initiating a note drag.
        e.preventDefault();
        e.stopPropagation();
    }

    function onPointerMove(e) {
        if (!state.panning) return;
        const dx = e.clientX - state.panning.startX;
        const dy = e.clientY - state.panning.startY;
        if (!state.panning.moved && Math.hypot(dx, dy) > PAN_THRESHOLD_PX) {
            state.panning.moved = true;
        }
        state.tx = state.panning.startTx + dx;
        state.ty = state.panning.startTy + dy;
        applyTransform();
    }

    function onPointerUp(e) {
        if (!state.panning) return;
        const viewport = getViewport();
        if (viewport) {
            viewport.classList.remove("is-panning");
            try { viewport.releasePointerCapture(state.panning.pointerId); } catch (_) {}
        }
        state.panning = null;
    }

    /* ── Spacebar: hold to force pan-mode even over sticky notes ── */
    function isTypingTarget(el) {
        if (!el) return false;
        const tag = (el.tagName || "").toLowerCase();
        return tag === "input" || tag === "textarea" || el.isContentEditable;
    }

    function onKeyDown(e) {
        if (e.code !== "Space" || e.repeat) return;
        if (isTypingTarget(e.target)) return;
        // Only act when the canvas is actually mounted on screen.
        const viewport = getViewport();
        if (!viewport) return;
        state.spaceHeld = true;
        viewport.classList.add("is-space-panning");
        e.preventDefault();
    }

    function onKeyUp(e) {
        if (e.code !== "Space") return;
        if (!state.spaceHeld) return;
        state.spaceHeld = false;
        const viewport = getViewport();
        if (viewport) viewport.classList.remove("is-space-panning");
    }

    /* ── Toolbar clicks ── */
    function onControlsClick(e) {
        const btn = e.target.closest("[data-action]");
        if (!btn) return;
        const action = btn.getAttribute("data-action");
        if      (action === "zoom-in")  zoomToCenter(ZOOM_STEP);
        else if (action === "zoom-out") zoomToCenter(1 / ZOOM_STEP);
        else if (action === "reset")    resetView();
        else if (action === "fit")      fitToContent();
    }

    /* ── Mount / re-mount handling ──
       Switching off the Annotations tab unmounts `.annotations-canvas-content`
       from the DOM; switching back creates a fresh element without any inline
       transform. Our `state` object lives in the JS module closure, so it
       survives tab switches — but we have to push it onto the new DOM node,
       otherwise the canvas reads as 100% until the user nudges zoom (at which
       point the state-driven scale snaps back, the "non-smooth jump" bug).

       First time the canvas appears in a session (incl. fresh load / refresh),
       default to fit-to-content rather than scale=1 so the user starts with
       all their notes in view. */
    let hasAppliedInitialFit = false;

    function onCanvasMount() {
        if (!getContent()) return;
        if (hasAppliedInitialFit) {
            // Re-mount within session: push the persisted transform onto the
            // fresh DOM node so it matches what the user had.
            applyTransform();
            return;
        }
        // First mount: fit to content. Sticky notes are rendered by Dash and
        // may not be in the DOM yet on the same tick the container appears,
        // so retry up to ~20 frames (~330ms). fitToContent() handles the
        // empty-board case (no notes) by falling back to resetView().
        let attempts = 0;
        const tryFit = () => {
            if (document.querySelectorAll(STICKY_SELECTOR).length === 0 && attempts < 20) {
                attempts++;
                requestAnimationFrame(tryFit);
                return;
            }
            fitToContent();
            hasAppliedInitialFit = true;
        };
        tryFit();
    }

    function watchForCanvasMount() {
        if (typeof MutationObserver === "undefined") return;
        const obs = new MutationObserver((mutations) => {
            for (const m of mutations) {
                for (const node of m.addedNodes) {
                    if (node.nodeType !== 1) continue;
                    // Match the content container itself or anything that
                    // contains it (Dash sometimes wraps tab content in
                    // additional nodes during route transitions).
                    if (
                        (node.matches && node.matches(CONTENT_SELECTOR)) ||
                        (node.querySelector && node.querySelector(CONTENT_SELECTOR))
                    ) {
                        onCanvasMount();
                        return;
                    }
                }
            }
        });
        obs.observe(document.body, { childList: true, subtree: true });
    }

    function init() {
        // Wheel needs passive:false to call preventDefault.
        document.body.addEventListener("wheel", onWheel, { passive: false, capture: true });
        // Pointer pan: capture-phase so we beat the sticky-drag handler when
        // shouldStartCanvasPan() returns true.
        document.body.addEventListener("pointerdown",   onPointerDown, true);
        document.body.addEventListener("pointermove",   onPointerMove, true);
        document.body.addEventListener("pointerup",     onPointerUp,   true);
        document.body.addEventListener("pointercancel", onPointerUp,   true);
        // Keyboard: window-level so we catch space regardless of focus.
        window.addEventListener("keydown", onKeyDown);
        window.addEventListener("keyup",   onKeyUp);
        // Toolbar (delegated; controls live inside the viewport).
        document.body.addEventListener("click", onControlsClick);

        // Catch every mount/re-mount of the canvas content node. If the
        // Annotations tab is the initial active tab, the node may already
        // be present at init time — handle that case explicitly.
        watchForCanvasMount();
        if (getContent()) onCanvasMount();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
