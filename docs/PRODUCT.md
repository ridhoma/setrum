# Setrum — Product Overview

> A personal energy analyser that turns the raw half-hourly meter data your
> electricity supplier already collects into a tool you can actually
> *think with*.

---

## 1. What is Setrum?

Setrum is a **local web app** that connects to your Octopus Energy account,
pulls every half-hourly consumption reading and tariff price you've ever
been charged, stores it in a small database on your laptop, and lets you
explore it in three complementary ways:

1. **As charts** — daily cost, daily kWh, and a half-hourly profile showing
   the spikes and dips of every 30-minute window in your home's electricity
   life.
2. **As annotations** — sticky-note style observations you pin to specific
   periods ("induction hob: stir-fry", "trip to Bristol", "boiler failed
   here"). Each note is computed against the underlying meter data so you
   immediately see how much that period actually cost in kWh and pounds.
3. **As insights** *(coming soon)* — patterns Setrum surfaces from your
   accumulated annotations and consumption history.

The app runs **entirely on your machine**. Your meter data never leaves your
laptop. No subscription, no cloud account, no analytics tracking.

---

## 2. The concept in one picture

```
                ┌──────────────────────────────────┐
                │     OCTOPUS ENERGY API           │
                │  (your account — read-only key)  │
                └────────────────┬─────────────────┘
                                 │  fetched once on
                                 │  every "Refresh"
                                 ▼
   ┌────────────────────────────────────────────────────┐
   │             SETRUM (running on your laptop)         │
   │                                                     │
   │   ┌──────────┐    ┌────────────┐    ┌────────────┐ │
   │   │  fetch   │ →  │  SQLite    │ →  │  charts +  │ │
   │   │  +       │    │  database  │    │  annotation│ │
   │   │ analyse  │    │ (setrum.db)│    │   canvas   │ │
   │   └──────────┘    └────────────┘    └────────────┘ │
   │                                                     │
   └────────────────────────────────────────────────────┘
                                 ▲
                                 │
                          ┌──────┴──────┐
                          │     YOU     │
                          │  (browser)  │
                          └─────────────┘
```

You hit **Refresh** every now and then; Setrum talks to Octopus, brings
new data home, transforms it into something analysable, and renders the
dashboard in your browser. That's the whole loop.

---

## 3. Why does this exist?

Energy suppliers technically *give* you all this data — most of them have a
download button somewhere or a CSV export. But the experience usually stops
at "here is a CSV". You can stare at numbers, you can throw them into Excel,
but it's hard to **reason** about your energy use because:

- The data is dense (48 readings per day, every day) and the patterns are
  multi-scale: hour-of-day, day-of-week, season, life events.
- The bill you actually pay is a *combination* of consumption × unit
  price + standing charge + VAT, which most tools flatten into a single
  pence/kWh average.
- Real life happens. You bought a heat pump in March, you went away for a
  week in April, the kettle died and got replaced with something more
  efficient in May. Without notes attached to specific periods, those
  facts vanish into the average.

Setrum's pitch is that **observations + data, in the same view, is more
than the sum of the two**. Once you can write "tried baking bread today"
on a Saturday afternoon and see exactly what the oven cost, you stop
treating your bill as an opaque number.

---

## 4. The features

### 4.1 Three-tab dashboard

```
┌─────────────────────────────────────────────────────────┐
│ ⚡ Setrum Analyser    [📈 Consumptions] [📝 Annotations]│
│                       [✨ Insights]                     │
├──────────────┬──────────────────────────────────────────┤
│              │                                          │
│  DATA STATUS │           main content area              │
│  ✅ Up to    │           (tab-dependent)                │
│     date     │                                          │
│              │                                          │
│  [Refresh]   │                                          │
│              │                                          │
│              │                                          │
│  Powered by  │                                          │
│  Octopus     │                                          │
└──────────────┴──────────────────────────────────────────┘
```

The **header** carries the app identity and the three top-level tabs.
The **sidebar** carries a single, focused thing: data freshness. You see
when the data was last synced, and you trigger a new sync from there.
The **main content** swaps based on the active tab.

### 4.2 Consumptions tab

Two charts stacked vertically:

**Daily Cost and Consumption** — area chart, one row per day. Two views
toggleable from the header:
- **£** view: stacked area showing Standing Charge / Consumption / VAT.
- **kWh** view: single area showing total kilowatt-hours consumed.

Above the chart sit four KPI cards (Total Consumption / Total Cost / Avg
Price / Avg Standing Charge). The cards are **scoped to the date filter**
— change the filter from "Last 30 days" to "Last 90 days" and the cards
update.

**Half-Hourly Depth Profile** — bar chart, one bar per 30-minute bucket.
Lets you see exactly when your kettle, oven, heat pump, or whatever is
running. Mondays are dashed gridlines so you can find your week.

Both charts are **interactive** — you can box-select or click bars to
mark a period, then turn that selection into an annotation.

### 4.3 Annotations tab — the sticky-note canvas

The killer feature. Imagine a corkboard:

- Every annotation you've ever saved is a sticky note pinned to the board.
- Each note shows the **period** it covers, your **comment**, the
  **kWh and £ that period actually cost** (computed live from the meter
  data, not a snapshot), and any **tags** you've attached.
- Notes have a colour and a slight tilt — the board feels physical, not a
  spreadsheet.
- **You can drag notes around freely**. Want all your "breakfast" notes in
  the top-left? Drag them there. Want a chronological wall? Arrange them
  left-to-right by date. The positions persist across sessions.
- Each note has a small ✏️ button (edit) and 🗑 button (delete) that
  appear on hover, and a `+ New` button at the top to create from scratch.

```
┌───────────────────────────────────────────────────────────────┐
│  Annotations                                       [+ New]   │
├───────────────────────────────────────────────────────────────┤
│   ┌─────────┐                                                 │
│   │ DAILY 🗑│   ┌──────────┐                                  │
│   │Sun 12 Apr│   │ HH    ✏️ │       ┌─────────────┐           │
│   │Day's out│   │Wed 22 Apr│       │ HH       🗑 │           │
│   │6.58 kWh │   │04:30→5:30│       │ Wed 22 Apr  │           │
│   │£1.64    │   │1.73 kWh  │       │ 12:30→13:00 │           │
│   │[trip]   │   │£0.43     │       │ 0.33 kWh    │           │
│   └─────────┘   │[heater]  │       │ Coffee      │           │
│                 └──────────┘       │ [coffee]    │           │
│                                    └─────────────┘           │
└───────────────────────────────────────────────────────────────┘
```

### 4.4 Two ways to create an annotation

**A. From a chart selection.** Drag a box on either chart, click the ✏️
icon that appears in the live readout, and a floating form pops up with
the period, kWh, and £ already calculated. Type a comment, add tags, save.
The new sticky appears on the board, *and* a yellow band marks the period
on the chart.

**B. From the manager.** Hit `+ New` on the Annotations tab. A modal
opens where you pick:
- Whether the annotation belongs to the **daily** chart or the
  **half-hourly** chart.
- The period: from-date and to-date (plus hour + minute pickers if it's
  half-hourly).
- Tags (creatable — type a new one and it's saved).
- A free-text comment.

Save, and the sticky appears on the board *and* the yellow band shows
on whichever chart you assigned it to.

### 4.5 Tags — the analytics primitive of the future

Every annotation can carry one or more tags. Tags are case-insensitive
("breakfast" and "Breakfast" merge), and the same tag can be used on
hundreds of annotations.

The vision: once you've built up a tag vocabulary ("breakfast", "oven",
"away", "induction-hob", etc.) over months of use, the **Insights tab**
will let you ask things like:

- *"How much electricity did breakfast cost me last quarter?"*
- *"Which tag has been growing the most over time?"*
- *"What did our last 'away' period save us?"*

The data primitives are already there (every annotation has tags, and a
SQL join can sum kWh per tag). The Insights UI is the next thing to build.

### 4.6 Refresh, data freshness, and accuracy

Tap **Refresh** in the sidebar and a background sync runs:
1. Re-fetches your account / meter / tariff metadata.
2. Pulls every new half-hourly consumption reading since the last sync.
3. Pulls every new tariff price (unit rate + standing charge) since the
   last sync.
4. Rebuilds two pre-computed analytics tables that the dashboard reads
   from.
5. The sidebar pill turns green and shows when the latest data point is
   from.

The sync is **non-blocking** — you can keep using the dashboard while it
runs. Octopus typically lags 1–2 days behind real-time, so even a fresh
sync will leave you with data ending yesterday.

---

## 5. Expected usage experience

### Day 1
- You set up the app (`uv run python run.py`).
- You hit Refresh once. After a minute or two of progress bar, the
  charts populate.
- You play with the date filter. The 30-day view shows your typical
  weekly rhythm; the 90-day view shows seasonal drift.
- You don't really know what your spike at 18:00 every Friday is.

### Week 1
- You start brushing 18:00–18:30 windows on Fridays and pinning notes
  ("dinner", "induction hob"). After 3 weeks of doing this you can
  filter your annotations to "induction hob" and see exactly what your
  cooking habit costs.
- You realise you have a phantom load at 4 AM. You annotate it
  ("immersion heater?") and confirm next time.

### Month 1+
- You go away for a week. Tag the period "away". Compare it to a normal
  week — that's your baseline.
- You replace an appliance. Annotate the day. Compare consumption
  before/after.
- The sticky-note board becomes your **personal energy lab notebook** —
  the artefacts of your investigation, not just the numbers.

---

## 6. Design principles

1. **Local-first.** Your data never leaves your machine.
2. **The annotation is the unit of insight.** Charts show patterns; only
   annotations capture *why*. The product invests in making annotation
   creation, viewing, and arrangement frictionless.
3. **Precision matters.** Every aggregation refers to *actual half-hourly
   data points*, never to pixel-interpolated cursor positions. When you
   select 06:00–07:30, the kWh shown is the sum of those exact three
   buckets — not "approximately that range".
4. **Visualisations should never lie.** Annotation overlays line up
   pixel-perfectly with the bars they describe. Date axes are tz-aware
   UTC end-to-end so periods don't drift by your local timezone offset.
5. **The corkboard is yours.** Note positions are persistent, the
   layout is free-form, the colours are slightly different per note.
   Setrum doesn't impose order — it lets you organise your notes the
   way your brain actually thinks.

---

## 7. What Setrum is *not*

- **Not a billing tool.** It can show you what your consumption costs at
  current tariff rates, but it doesn't manage payments.
- **Not multi-user.** One household, one Octopus account, one laptop.
- **Not real-time.** Half-hourly data is pushed to Octopus by your
  smart meter typically once a day; Setrum can only see what they have.
- **Not a smart-home integrator.** It works with the data Octopus
  already collects — it doesn't read directly from your meter or HEMS.

---

## 8. Glossary

- **Half-hourly (HH) data** — the 48 consumption readings your smart
  meter records every day, one per 30-minute interval. Octopus's
  consumption API returns these.
- **Standing charge** — the daily fixed fee on your tariff, regardless
  of consumption. Typically ~50p/day.
- **Unit rate** — the price per kWh on your tariff. Sometimes flat,
  sometimes time-of-use (Agile, Go).
- **VAT** — value-added tax (UK). 5% on domestic electricity, currently.
- **Annotation** — a user-created note pinned to a specific time period.
  Has a comment, optional tags, and is assigned to either the daily or
  half-hourly chart.
- **Source (of an annotation)** — `daily` or `half-hourly`. Determines
  which chart shows the yellow overlay band.
