# Setrum — AI Agent Onboarding Guide

> You're picking up a real project that's been through 30+ iteration cycles
> with a real user. This guide is the institutional memory: what to do, what
> not to do, and the gotchas that have already cost an afternoon to debug.

Read `PRODUCT.md` for *what* the product is and `ARCHITECTURE.md` for
*how it's built*. This document is *how to behave* while changing it.

---

## 0. Read these first, in order

1. `docs/PRODUCT.md` — 5 minutes. So you know what the user actually wants.
2. `docs/ARCHITECTURE.md` — 15 minutes. Skim §3 (high-level), §4
   (data plane), §5.4 (callback graph), §7 (hacks). You'll come back
   to it.
3. `core/services/annotations.py` and `core/services/consumption.py`
   — the API surface every UI callback touches.
4. `dash_app/layout.py` — the shell. 30 lines.
5. `dash_app/callbacks/__init__.py` — the list of every callback
   module. If a callback doesn't appear here, it isn't registered.

Now you can be useful.

---

## 1. What the user values

In rough priority order based on actual feedback:

1. **Visual precision** — yellow annotation bands must align pixel-perfectly
   with bars. Selection times must snap to data points, never to mid-bucket
   pixel positions. They've sent screenshots multiple times pointing out
   sub-bucket misalignment.

2. **The annotation flow.** The user is building this *for* the annotation
   feature. Anything that breaks the chart-brush → form → save → sticky
   loop is a regression.

3. **Honest data.** "Up to date" should mean *actually* up to date, not
   "we tried to sync recently". The status pill was rewritten because of
   exactly this complaint.

4. **Local-first, single-user.** No multi-tenant abstractions, no auth.
   Don't introduce them.

5. **Tasteful defaults.** The user has visual opinions and will tell you
   immediately if something looks off (font weight, badge size, hover
   colour). Read screenshots carefully.

6. **Iterative shipping.** They prefer "do task A, ship, then task B"
   over "plan everything for an hour first". Auto-mode is enabled most
   sessions.

---

## 2. Conventions to keep

### 2.1 Architectural rules (do not violate)

- **Callbacks call services. Services call queries / orchestrator.
  Nothing above the service layer touches raw SQL.** If you find
  yourself writing SQL inside a callback module, stop and add a service
  function instead.

- **Versioned stores fan out re-renders.** When you add a new feature
  that depends on annotation state, listen to `ANNOTATIONS_VERSION`,
  not to individual save/edit/delete events. Bumping the version is
  the canonical "annotation state changed" signal.

- **Service functions accept an optional `conn=None` parameter** for
  testability and transaction reuse. Follow the existing pattern in
  `core/services/annotations.py`.

- **Source values are validated centrally.** Never hardcode
  `"daily"` or `"half-hourly"` strings outside the constants in
  `core/services/annotations.py:VALID_SOURCES`.

### 2.2 UI conventions

- **Tab content modules go in `dash_app/components/tabs/`.** Each
  exports `render() -> html.Div`. The tab router (`tab_router.py`)
  dispatches on `main-tabs.value`.

- **Layout-level components (always mounted regardless of tab) live
  directly in `dash_app/components/`.** Examples: `header.py`,
  `sidebar.py`, `annotation_form.py`, `annotation_manager_form.py`.
  These keep working when you switch tabs.

- **All custom CSS goes in `dash_app/assets/setrum.css`.** Don't add
  more `assets/*.css` files; one is easier to reason about.

- **All clientside JS goes in `dash_app/assets/`** and Dash auto-loads
  it. Use event delegation on `document.body` for handlers that need
  to survive tab swaps and component remounts.

- **`dcc.Store` IDs live in `dash_app/stores.py` as constants.** Don't
  inline string IDs in callbacks; that's how typos become silent
  no-op bugs.

### 2.3 Patterns

- **Single-owner state machines for modal/form visibility.** One
  callback owns `Output("ann-mgr-modal", "is_open")` and
  `Output("ann-form-card", "style")`. All triggers (click open, click
  close, save, cancel) become `Input`s on that one callback. See
  `dash_app/callbacks/annotation_manager.py:manage_modal`.

- **Pattern-matched IDs for dynamic lists.** Sticky note buttons use
  `id={"type": "ann-edit-btn", "id": ann_id}`. Listen with
  `Input({"type": "ann-edit-btn", "id": ALL}, "n_clicks")`. Always
  guard against the initial-mount fire:

  ```python
  if not any(c for c in (n_clicks_list or []) if c):
      return no_update
  ```

- **Format helpers in `dash_app/components/annotation_format.py`.** When
  you need a period label or hover text, import from there — don't
  duplicate the formatting logic.

### 2.4 Service layer signatures

Read these once and remember them:

```python
# core/services/annotations.py
create(account_id, period_start_utc, period_end_utc, source, comment=None, tag_names=None) -> int
update(annotation_id, comment=None, tag_names=None, period_start_utc=None,
       period_end_utc=None, source=None) -> None
delete(annotation_id) -> None
get_by_id(annotation_id) -> dict | None
list_in_range(start_utc, end_utc, account_id=None, source=None) -> DataFrame
list_all_with_aggregates(account_id=None) -> DataFrame      # used by board
set_position(annotation_id, x, y) -> None                   # used by canvas drag
snap_to_half_hour(ts_iso, direction="down"|"up") -> str

# core/services/consumption.py
get_half_hourly(start_utc, end_utc, account_id=None) -> DataFrame
get_daily_summary(start_date, end_date, account_id=None) -> DataFrame
aggregate_period(start_utc, end_utc, account_id=None) -> dict
get_summary_metrics(start_date, end_date, account_id=None) -> dict
get_data_extent(account_id=None) -> dict

# core/services/sync.py
run_sync(progress_cb=None) -> dict
get_sync_status() -> dict
```

If you need a function that doesn't exist, **add it as a service**
rather than calling raw queries from a callback.

---

## 3. Things that have already gone wrong (don't repeat)

### 3.1 macOS multiprocess fork → spawn

Symptom: "Refresh button does nothing." Worker process appears as
`<defunct>` in `ps`. No log output from the sync.

Fix already applied: `dash_app/app.py` calls `multiprocess.set_start_method("spawn", force=True)`
before constructing `DiskcacheManager`. **Do not remove this**, and if
you change anything in `dash_app/app.py` make sure this runs before
the `DiskcacheManager` import.

### 3.2 Tz-naive vs tz-aware date axes

Symptom: yellow annotation rect drifts ~1 hour to the right of the bar
it's supposed to overlay (in BST).

Fix already applied: `core/services/consumption.get_daily_summary`
calls `.dt.tz_localize("UTC")` on the `date` column. Never strip this.

### 3.3 Plotly `xperiodalignment` doesn't honour typed-array data

Symptom: bars centred on x even with `xperiod=86400000, xperiodalignment="start"`.

Fix already applied: bars use `offset=0, width=N` instead. See
`hh_chart.py:39-58` and `daily_cost_chart.py:_build_cost_figure`.

### 3.4 Selection x is the bar's *visual centre*, not its data x

Symptom: in-chart readout says "06:15 → 12:45" when the user selected
06:00–12:30 bars.

Fix: `dash_app/callbacks/selection.py:_extract_range` floors every
emitted x to the bucket frequency (`30min` for HH, `1D` for daily).
**Never use `selectedData.points[i].x` directly without flooring.**

### 3.5 Plotly shapes don't fire click or hover events

Symptom: clicking the yellow band did nothing.

Fix: each annotation band has a `mode="text"` scatter trace (📝 emoji)
at its centre, with `customdata=[ann_id]`. The trace fires `clickData`;
shapes still provide the visual rect.

### 3.6 Annotation icon click vs bar click

Symptom: clicking a bar opened the annotation modal.

Fix: `_annotation_id_from_click` differentiates by customdata shape —
scalar int = annotation icon, list `[a, b]` = bar/area data point.
If you add new traces with their own customdata shapes, extend this
function.

### 3.7 Hovering "fill" didn't show tooltip text

Symptom: hovering the yellow band showed only the trace name "annotation"
instead of the comment.

Fix: use `hovertemplate=text + "<extra></extra>"` rather than
`hoverinfo="text"` + `hovertext=text`. The `<extra></extra>` strips
the trace-name side label.

### 3.8 Pattern-matched callbacks fire on initial mount with `n_clicks=None`

Symptom: opening the page deleted random annotations.

Fix: every pattern-matched click handler guards with
`if not any(c for c in (n_clicks_list or []) if c): return no_update`.

### 3.9 SQL NULL becomes pandas NaN, not None

Symptom: `(row.get("comment") or "").strip()` raised
`AttributeError: 'float' object has no attribute 'strip'`.

Fix: use `_safe_str(value)` from `dash_app/components/annotation_format.py`,
which treats `NaN` as `""`.

### 3.10 Dash background-callback cacheKey

Symptom: when probing the background callback via curl with `cacheKey`
in the JSON body, every poll spawned a new worker.

Fix: `cacheKey` and `job` are **URL query parameters** in Dash 4, not
body fields. The browser does this correctly; only synthetic probes
need to know.

### 3.11 Drag flicker after persist

Symptom: dragging a sticky and dropping it caused a one-frame jump
back-then-forward.

Fix: the `persist_sticky_position` callback writes to the DB but
**does not bump `ANNOTATIONS_VERSION`**. The DOM is already where the
user dropped it; bumping the version would re-render and flicker.

### 3.12 Plotly daily area chart with stacked traces

Symptom: switching from bars to stacked area gave Plotly trouble with
selection events.

What works: `add_scatter(mode="lines", line=dict(width=0.5, color=…),
fillcolor=…, stackgroup="cost")`. Each component is its own scatter
trace with the same `stackgroup`. Selection still works because each
trace's `selectedData` returns the same x-coords.

### 3.13 Plotly typed-array `selectedData` may emit numeric ms-since-epoch

Symptom: `pd.to_datetime(x_value)` interpreted ms as nanoseconds and
returned year ~1970.

Fix: `_to_utc_ts` helper in `dash_app/callbacks/selection.py` checks
`isinstance(value, (int, float))` and uses `unit="ms"` explicitly.

---

## 4. Things to watch out for when adding features

### 4.1 New chart with brush selection?

You'll need to:
1. Set `dragmode="select"`, `selectdirection="h"`, `clickmode="event+select"` on the figure.
2. Use `offset=0, width=<bucket_ms>` on bar traces (or no offset for
   area / line traces — those work natively).
3. Add a `capture_<chart>_brush` callback writing to `SELECTED_RANGE`
   with `allow_duplicate=True` if `capture_hh_brush` is already wired.
4. Implement `_extract_range` with `floor` to bucket boundaries.
5. Update `prefill_annotation_form` to handle the new source.

### 4.2 New tab?

1. Add a content module under `dash_app/components/tabs/`.
2. Add the tab to `dash_app/components/header.py`.
3. Extend `dash_app/callbacks/tab_router.py` to dispatch.

### 4.3 New annotation field?

1. Migration in `core/database.py:init_db()` — `ALTER TABLE` guarded
   by `PRAGMA table_info` check.
2. Add column to `annotations.create()`, `update()`, `list_in_range()`,
   `list_all_with_aggregates()`.
3. Add field to manager modal form (`annotation_manager_form.py`).
4. Wire into `manage_modal` callback's `_open_for_edit` and save branches.
5. Render in sticky note (`annotations_board.py:_sticky_note`).

### 4.4 New service function?

1. Put it in the right `core/services/*.py` module.
2. Match the existing signature pattern: optional `conn=None`,
   typed inputs, validate at the boundary.
3. Return DataFrames for collections, dicts for singletons / aggregates.
4. Don't forget to write a sanity script in the conversation if the
   user asks "does this work?".

### 4.5 New chart annotation overlay?

1. The visual rect is a shape: `dict(type="rect", xref="x", yref="paper",
   x0=…, x1=…, y0=0, y1=1, fillcolor=…, opacity=0.18, line_width=0,
   layer="below")`.
2. Hover/click target is a separate `mode="text"` scatter trace with
   `customdata=[ann_id]` and a hovertemplate.
3. Click handler in `manage_modal` already handles this — just make
   sure your new chart's `clickData` is wired in the callback inputs.

---

## 5. Working patterns the user appreciates

### 5.1 Probe via the live `/_dash-update-component` endpoint

When you've made a change and want to verify it works, the user
restarts the app themselves. To verify *before* asking them, hit:

```bash
uv run python run.py --port 8050 &
until curl -fsS http://127.0.0.1:8050 -o /dev/null 2>/dev/null; do sleep 1; done

# Verify a callback by faking its inputs
curl -fsS -X POST http://127.0.0.1:8050/_dash-update-component \
  -H 'Content-Type: application/json' \
  -d '{"output": "<id>.<prop>", ...}'
```

For multi-output callbacks, find the output id at
`/_dash-dependencies` (the URL with the hash appended for
`allow_duplicate=True` outputs).

### 5.2 Always smoke-test data path before claiming done

Pattern: after changing a service function, run a one-liner like:

```bash
uv run python -c "
from core.services import annotations
df = annotations.list_all_with_aggregates(account_id=YOUR_ACCOUNT_ID)
print(df)
"
```

This catches schema / typo bugs before they hit the UI.

### 5.3 Plant + clean up test data

When you create a test annotation in DB to verify a flow, delete it
afterward via SQL. The user notices garbage rows in their data.

### 5.4 Kill the server before they restart

When the user says "restart it" or "I'll restart", run `pkill -f
run.py` so port 8050 is free. They'll thank you for it.

### 5.5 Auto-mode means just go

When auto-mode is on (system reminders will tell you), don't ask
"should I proceed?". Make reasonable assumptions, do the work,
present the result. The user prefers minor course corrections over
ten back-and-forth questions.

### 5.6 Don't claim hours of work

The user pushed back when I said "this will take 3 hours". Time
estimates of mine are just relative effort — say "this is a chunky
change" or "small change", not "n hours". The actual elapsed time is
typically 5–30 minutes of dialogue.

### 5.7 Visual verification of UI changes

The agent runs blind by default — it can't see what it ships. Playwright
is installed as a dev dep (`uv add --dev playwright` + `uvx playwright
install chromium`) so you can drive a real browser, take screenshots,
and read them back. **Use this strategically.** Every screenshot you
`Read` costs tokens (~1.5K for a 1600×900 viewport, ~3–5K for a long
full-page capture). Don't reach for it on every CSS tweak.

**Decide first** — does the change actually need a browser to verify?

| Change | Verify with Playwright? |
|---|---|
| Color/hex/font-weight/padding/margin tweak | No — code-diff is enough |
| Text or copy edit | No |
| Class rename, removing unused CSS | No |
| Backend logic / callback wiring / new service function | No (probe via §5.1 / §5.2 instead) |
| Layout change (flex/grid/positioning, header, sidebar, modal) | **Yes** |
| New component or rearrangement | **Yes** |
| New interaction (click, drag, keyboard, hover) | **Yes — scripted, not just screenshot** |
| Override of `dcc.*` or Plotly internals | **Yes** — vendor defaults can fight your CSS in ways the diff won't reveal (we hit this with the tab strip rendering bottom-right instead of bottom-left despite `align-items: flex-end`) |

The "verify yes" cases share a property: the rendered DOM has variables
the code can't predict — vendor markup, browser layout quirks, the
empty tab-content panel `dcc.Tabs` adds underneath the trigger row, etc.

**Static screenshot** — for "is the layout right" checks. Cheapest mode:

```bash
# App must be running on :8050. Tight viewport = fewer image tokens.
uv run playwright screenshot http://127.0.0.1:8050 /tmp/setrum.png \
    --viewport-size=1600,900 --wait-for-timeout=1500
# then Read /tmp/setrum.png
```

Crop to the changed strip with a small height (`--viewport-size=1600,200`
for the header alone) when you don't need the whole page. Use
`--full-page` only when you genuinely need everything below the fold.

**Scripted interaction** — for click/drag/keyboard/hover flows. Inline
via `uv run python -c '…'`, no committed harness needed:

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    page = p.chromium.launch().new_page()
    page.on("console", lambda m: print("[js]", m.text))   # surface JS errors
    page.goto("http://127.0.0.1:8050")
    page.click("text=Annotations")
    page.locator("#canvas-sticky-21").click()
    page.keyboard.down("Shift")
    page.locator("#canvas-sticky-20").click()
    page.keyboard.up("Shift")
    print("selected:", page.locator(".canvas-sticky.selected").count())
    page.screenshot(path="/tmp/setrum.png")
```

For drag, use raw `page.mouse.move/down/up` — Playwright's high-level
`drag_to` doesn't fire `pointermove` the way our canvas JS expects.

**Discipline**:
- Re-use `/tmp/setrum.png` (single file, overwritten). Same path within
  5 minutes → prompt-cache hit when you re-`Read` it.
- One screenshot per iteration is plenty. If you're taking three to
  compare, you're tweaking too small — step back.
- A scripted interaction *is* the verification. Don't take a screenshot
  unless the visual outcome is the point — `count()` and `text_content()`
  assertions are token-free.
- `pkill -f run.py` when you're done. Don't leave the server running.

---

## 6. Things to NOT do

- ❌ **Don't add Streamlit / Flask / FastAPI back into the project.**
  This was a deliberate migration *away* from Streamlit. The user
  doesn't want a hybrid.

- ❌ **Don't introduce Redis, PostgreSQL, or any non-SQLite backend.**
  Single-user laptop app. SQLite is the answer.

- ❌ **Don't touch `core/transformations.py:MODELS` lightly.** It's the
  ELT contract; many callbacks depend on the column shapes there.

- ❌ **Don't add tests at every turn.** The user values working features
  and visible progress over green CI bars. Add tests when fixing a
  recurrence-prone bug; don't gold-plate.

- ❌ **Don't decorate with emojis in code or commit messages.** Use them
  sparingly in UI strings (where the user has already added them) or
  in CLI output. Avoid in code comments.

- ❌ **Don't refactor for the sake of it.** If a function works and
  isn't a bug source, leave it. The user has explicitly preferred
  shipping over polishing on multiple occasions.

- ❌ **Don't write multi-paragraph docstrings.** One short paragraph
  explaining *why*, not *what*. The codebase favours terse, dense
  comments.

- ❌ **Don't add tasks for trivial work.** Use `TaskCreate` only for
  3+ step or non-trivial work. The user gets pinged on every task.

- ❌ **Don't run destructive operations without explicit ok.**
  `rm`, `git reset --hard`, schema drops, etc. Even when auto-mode is
  on, anything destructive needs a yes.

- ❌ **Don't bump `ANNOTATIONS_VERSION` after a position-only update.**
  See §3.11.

- ❌ **Don't add hover-on-fill in Plotly.** It's unreliable. Use a
  scatter `mode="text"` icon trace as the click/hover target. See §3.5.

- ❌ **Don't put SQL inside callbacks.** Add a service function.

---

## 7. Where to look when something breaks

| Symptom | First place to look |
|---|---|
| Refresh button does nothing | `dash_app/app.py` → confirm `set_start_method("spawn")` is still there. Then read `b<id>.output` for sync logs. |
| Annotation overlay misaligned with bar | `_build_cost_figure` / `_build_kwh_figure` / `hh_chart.build_consumption_figure` → confirm `offset=0, width=N` is set on bar/area traces. Confirm `get_daily_summary` localizes to UTC. |
| Sticky note position not persisting | `dash_app/callbacks/canvas.py:persist_sticky_position`. Then check `dash_app/assets/canvas_drag.js` — the `set_props` line. |
| Modal opens at random times | Check `dash_app/callbacks/annotation_manager.py:manage_modal` — usually a missing `prevent_initial_call` or a missing pattern-match guard. |
| Selection in-chart readout shows mid-bucket times | `dash_app/callbacks/selection.py:_extract_range` — confirm `floor(bucket_freq)` is applied on both points and range paths. |
| KPI cards don't update with date filter | `dash_app/callbacks/summary.py:render_summary` should `Input("daily-resolved-range", "data")` — not `DATA_VERSION` only. |
| Sticky note board flickers | A callback is bumping `ANNOTATIONS_VERSION` for a position update. Check `canvas.py` — it should be a side-effect-only callback. |

---

## 8. Final checklist before claiming "done"

- [ ] Did you add a service function for any new SQL? (No raw SQL in callbacks.)
- [ ] Did you wire the new callback into `dash_app/callbacks/__init__.py`?
- [ ] Does the data flow round-trip end-to-end? (Plant → render → re-render.)
- [ ] Did you handle pandas NaN where SQL NULL is possible?
- [ ] Did you verify with a synthetic probe to `_dash-update-component`?
- [ ] If the change touched layout, positioning, or interactions: did you
      visually verify with Playwright? (Not "did the code compile" —
      *did the pixels look right*, *did the click do what you wanted*.)
      See §5.7 for when this is and isn't worth it.
- [ ] Did you stop the test server (`pkill -f run.py`)?
- [ ] Did you clean up test data (annotations, tags) you planted?
- [ ] Are timestamps tz-aware UTC end-to-end?
- [ ] If you touched chart bars: `offset=0, width=N` confirmed?
- [ ] If you touched selection: `floor(bucket_freq)` applied?
- [ ] If new pattern-matched callback: initial-mount guard present?
- [ ] Did you respect the user's preference for shipping over planning?

If yes to all, you're good. Ship it.

---

## 9. Welcome aboard

This codebase is small but the user has put real care into it. They're
collaborative, opinionated, and quick to give feedback — both positive
and corrective. Read their messages closely (especially screenshots),
proceed with reasonable confidence, and pause for confirmation only on
choices that have lasting consequences (architecture, data model,
destructive ops).

The previous agents (myself included) made mistakes. Don't repeat them.
Make new ones.
