/* Sticky-note selection + drag for the Annotations canvas.
 *
 *   click on a sticky                → single-select (replaces selection)
 *   shift+click on a sticky          → toggle in/out of selection
 *   drag on a sticky                 → move all selected stickies together
 *                                      (the dragged sticky is added to
 *                                      selection first if not already in)
 *   drag on empty canvas             → marquee select (replaces selection,
 *                                      or unions with shift held)
 *   click on empty canvas, no shift  → clear selection
 *   Escape                           → clear selection
 *
 * Pan / zoom is owned by canvas_pan_zoom.js — middle-mouse, space+drag,
 * and wheel/trackpad. We yield to it when `window.__setrumCanvas` reports
 * spaceHeld or panning.
 *
 * On drop, all moved stickies are published as a single batched payload
 * `{updates: [{id, x, y}, ...]}` to `sticky-position-store`, which the
 * Python callback turns into one transactional UPDATE.
 */

(function () {
    "use strict";

    const VIEWPORT_SELECTOR = ".annotations-canvas-viewport";
    const STICKY_SELECTOR   = ".canvas-sticky";
    const ACTION_SELECTOR   = "button, .sticky-action-btn, a";
    const CONTROLS_SELECTOR = ".canvas-zoom-controls";
    const MARQUEE_CLASS     = "canvas-marquee";
    const SELECTED_CLASS    = "selected";
    const DRAG_THRESHOLD_PX = 4;

    // Selection is in-memory only; matches the FigJam model where viewport
    // state (selection, zoom, pan) doesn't persist across reloads.
    const selection = new Set();        // ann_id (int)

    // Pointer state machine — one of:
    //   null
    //   { kind: "sticky-pending", ann_id, shift, startX, startY, sticky }
    //   { kind: "sticky-drag",    items: [...], startX, startY }
    //   { kind: "marquee",        startX, startY, base, shift, rect, viewport, moved }
    let pointer = null;

    function getViewport() { return document.querySelector(VIEWPORT_SELECTOR); }

    function annIdOf(el) {
        const m = (el && el.id || "").match(/^canvas-sticky-(\d+)$/);
        return m ? parseInt(m[1], 10) : null;
    }

    function getScale() {
        const cv = window.__setrumCanvas;
        return (cv && typeof cv.getScale === "function") ? cv.getScale() : 1;
    }

    /* ── Selection helpers ───────────────────────────────────────────────── */
    function applySelectionClasses() {
        document.querySelectorAll(STICKY_SELECTOR).forEach((el) => {
            const id = annIdOf(el);
            if (id == null) return;
            el.classList.toggle(SELECTED_CLASS, selection.has(id));
        });
    }

    function setSelection(ids) {
        selection.clear();
        ids.forEach((id) => selection.add(id));
        applySelectionClasses();
    }

    function clearSelection() {
        if (selection.size === 0) return;
        selection.clear();
        applySelectionClasses();
    }

    function setEquals(a, b) {
        if (a.size !== b.size) return false;
        for (const v of a) if (!b.has(v)) return false;
        return true;
    }

    /* ── Pointer down ────────────────────────────────────────────────────── */
    function onPointerDown(e) {
        if (e.button !== 0 && e.button !== undefined) return;     // primary only
        // Pan owns space-drag and middle-button; bail.
        const cv = window.__setrumCanvas;
        if (cv && (cv.spaceHeld || cv.panning)) return;
        if (e.defaultPrevented) return;

        const viewport = getViewport();
        if (!viewport || !viewport.contains(e.target)) return;
        if (e.target.closest(CONTROLS_SELECTOR)) return;          // toolbar
        if (e.target.closest(ACTION_SELECTOR))   return;          // ✏️ / 🗑

        const sticky = e.target.closest(STICKY_SELECTOR);
        if (sticky) {
            const ann_id = annIdOf(sticky);
            if (ann_id == null) return;
            pointer = {
                kind: "sticky-pending",
                ann_id,
                shift: !!e.shiftKey,
                startX: e.clientX,
                startY: e.clientY,
                sticky,
                pointerId: e.pointerId,
            };
            try { sticky.setPointerCapture(e.pointerId); } catch (_) { /* ok */ }
            e.preventDefault();
            return;
        }

        // Empty canvas → marquee.
        const rect = document.createElement("div");
        rect.className = MARQUEE_CLASS;
        viewport.appendChild(rect);
        pointer = {
            kind: "marquee",
            startX: e.clientX,
            startY: e.clientY,
            base: e.shiftKey ? new Set(selection) : new Set(),
            shift: !!e.shiftKey,
            rect,
            viewport,
            moved: false,
            pointerId: e.pointerId,
        };
        try { viewport.setPointerCapture(e.pointerId); } catch (_) { /* ok */ }
        e.preventDefault();
    }

    /* ── Pointer move ────────────────────────────────────────────────────── */
    function promoteToStickyDrag(p) {
        // Lock in the selection before we start moving things. If the dragged
        // sticky isn't already part of the selection, it joins (replacing
        // unless shift is held).
        if (!selection.has(p.ann_id)) {
            if (p.shift) selection.add(p.ann_id);
            else { selection.clear(); selection.add(p.ann_id); }
            applySelectionClasses();
        }
        const items = [];
        selection.forEach((id) => {
            const el = document.getElementById(`canvas-sticky-${id}`);
            if (!el) return;
            items.push({
                el,
                ann_id: id,
                startLeft: parseInt(el.style.left || "0", 10) || 0,
                startTop:  parseInt(el.style.top  || "0", 10) || 0,
            });
            el.classList.add("dragging");
        });
        return {
            kind: "sticky-drag",
            items,
            startX: p.startX,
            startY: p.startY,
        };
    }

    function onPointerMove(e) {
        if (!pointer) return;

        if (pointer.kind === "sticky-pending") {
            const dx = e.clientX - pointer.startX;
            const dy = e.clientY - pointer.startY;
            if (Math.hypot(dx, dy) <= DRAG_THRESHOLD_PX) return;
            pointer = promoteToStickyDrag(pointer);
            // fall through to apply the first delta
        }

        if (pointer.kind === "sticky-drag") {
            const scale = getScale() || 1;
            const dx = (e.clientX - pointer.startX) / scale;
            const dy = (e.clientY - pointer.startY) / scale;
            pointer.items.forEach((s) => {
                s.el.style.left = (s.startLeft + dx) + "px";
                s.el.style.top  = (s.startTop  + dy) + "px";
            });
            return;
        }

        if (pointer.kind === "marquee") {
            const x0 = Math.min(pointer.startX, e.clientX);
            const y0 = Math.min(pointer.startY, e.clientY);
            const x1 = Math.max(pointer.startX, e.clientX);
            const y1 = Math.max(pointer.startY, e.clientY);
            if (Math.hypot(x1 - x0, y1 - y0) > DRAG_THRESHOLD_PX) pointer.moved = true;

            const vrect = pointer.viewport.getBoundingClientRect();
            pointer.rect.style.left   = (x0 - vrect.left) + "px";
            pointer.rect.style.top    = (y0 - vrect.top)  + "px";
            pointer.rect.style.width  = (x1 - x0) + "px";
            pointer.rect.style.height = (y1 - y0) + "px";
            pointer.rect.style.display = "block";

            // Hit-test in screen coords using getBoundingClientRect — that
            // already accounts for the canvas transform, so this works at
            // any zoom level.
            const hits = new Set(pointer.base);
            document.querySelectorAll(STICKY_SELECTOR).forEach((el) => {
                const r = el.getBoundingClientRect();
                if (r.right < x0 || r.left > x1 || r.bottom < y0 || r.top > y1) return;
                const id = annIdOf(el);
                if (id != null) hits.add(id);
            });
            if (!setEquals(hits, selection)) setSelection(hits);
        }
    }

    /* ── Pointer up / cancel ─────────────────────────────────────────────── */
    function onPointerUp(e) {
        if (!pointer) return;
        const p = pointer;
        pointer = null;

        if (p.kind === "sticky-pending") {
            // Pure click — selection toggle / replace.
            if (p.shift) {
                if (selection.has(p.ann_id)) selection.delete(p.ann_id);
                else selection.add(p.ann_id);
            } else {
                selection.clear();
                selection.add(p.ann_id);
            }
            applySelectionClasses();
            try { p.sticky.releasePointerCapture(p.pointerId); } catch (_) {}
            return;
        }

        if (p.kind === "sticky-drag") {
            const updates = [];
            p.items.forEach((s) => {
                const left = parseInt(s.el.style.left || "0", 10) || 0;
                const top  = parseInt(s.el.style.top  || "0", 10) || 0;
                s.el.classList.remove("dragging");
                if (left !== s.startLeft || top !== s.startTop) {
                    updates.push({ id: s.ann_id, x: left, y: top });
                }
            });
            if (updates.length && window.dash_clientside && window.dash_clientside.set_props) {
                window.dash_clientside.set_props("sticky-position-store", {
                    data: { updates, ts: Date.now() },
                });
            }
            return;
        }

        if (p.kind === "marquee") {
            try { p.rect.remove(); } catch (_) {}
            try { p.viewport.releasePointerCapture(p.pointerId); } catch (_) {}
            // Click on empty canvas (no drag) clears unless shift held.
            if (!p.moved && !p.shift) clearSelection();
            return;
        }
    }

    /* ── Keyboard ────────────────────────────────────────────────────────── */
    function isTypingTarget(el) {
        if (!el) return false;
        const tag = (el.tagName || "").toLowerCase();
        return tag === "input" || tag === "textarea" || el.isContentEditable;
    }

    function onKeyDown(e) {
        if (isTypingTarget(e.target)) return;
        if (e.key === "Escape") clearSelection();
    }

    /* ── Re-apply .selected after Dash re-renders the board ──────────────── */
    function watchForRerender() {
        if (typeof MutationObserver === "undefined") return;
        const obs = new MutationObserver(() => applySelectionClasses());
        obs.observe(document.body, { childList: true, subtree: true });
    }

    function init() {
        document.body.addEventListener("pointerdown",   onPointerDown, true);
        document.body.addEventListener("pointermove",   onPointerMove, true);
        document.body.addEventListener("pointerup",     onPointerUp,   true);
        document.body.addEventListener("pointercancel", onPointerUp,   true);
        window.addEventListener("keydown", onKeyDown);
        watchForRerender();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
