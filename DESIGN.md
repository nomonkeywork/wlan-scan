---
name: Freds LAN
description: A calm slate and indigo working tool that shows the home network as a 3D map around the router.
colors:
  indigo-600: "#4f46e5"
  indigo-700: "#4338ca"
  indigo-300: "#a5b4fc"
  indigo-100: "#e0e7ff"
  indigo-50: "#eef2ff"
  sky-500: "#0ea5e9"
  emerald-500: "#10b981"
  amber-700: "#b45309"
  amber-200: "#fde68a"
  amber-50: "#fffbeb"
  rose-700: "#be123c"
  rose-500: "#f43f5e"
  rose-200: "#fecdd3"
  rose-50: "#fff1f2"
  white: "#ffffff"
  slate-50: "#f8fafc"
  slate-100: "#f1f5f9"
  slate-200: "#e2e8f0"
  slate-300: "#cbd5e1"
  slate-400: "#94a3b8"
  slate-500: "#64748b"
  slate-600: "#475569"
  slate-700: "#334155"
  slate-900: "#0f172a"
  logo-violet: "#7c3aed"
typography:
  headline:
    fontFamily: "JetBrains Mono, ui-monospace, Menlo, monospace"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "-0.02em"
  title:
    fontFamily: "JetBrains Mono, ui-monospace, Menlo, monospace"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "-0.02em"
  title-small:
    fontFamily: "JetBrains Mono, ui-monospace, Menlo, monospace"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "-0.02em"
  body:
    fontFamily: "JetBrains Mono, ui-monospace, Menlo, monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
  body-strong:
    fontFamily: "JetBrains Mono, ui-monospace, Menlo, monospace"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: 1.45
  label:
    fontFamily: "JetBrains Mono, ui-monospace, Menlo, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.45
  label-strong:
    fontFamily: "JetBrains Mono, ui-monospace, Menlo, monospace"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.3
rounded:
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "14px"
  2xl: "18px"
  full: "50%"
spacing:
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "12px"
  2xl: "14px"
  3xl: "16px"
components:
  button:
    backgroundColor: "{colors.white}"
    textColor: "{colors.slate-700}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.lg}"
    padding: "0 12px"
    height: "36px"
  button-hover:
    backgroundColor: "{colors.slate-50}"
  button-primary:
    backgroundColor: "{colors.indigo-600}"
    textColor: "{colors.white}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.lg}"
    padding: "0 12px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "{colors.indigo-700}"
  segment:
    textColor: "{colors.slate-600}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.lg}"
    padding: "0 10px"
    height: "28px"
  segment-pressed:
    backgroundColor: "{colors.indigo-50}"
    textColor: "{colors.indigo-700}"
  input:
    backgroundColor: "{colors.white}"
    textColor: "{colors.slate-900}"
    typography: "{typography.body}"
    rounded: "{rounded.xl}"
    padding: "0 12px"
    height: "36px"
  pulldown-trigger:
    backgroundColor: "{colors.white}"
    textColor: "{colors.slate-700}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.xl}"
    padding: "0 12px"
    height: "36px"
    width: "232px"
  pulldown-option:
    textColor: "{colors.slate-600}"
    typography: "{typography.body}"
    padding: "8px 14px"
  pulldown-option-active:
    backgroundColor: "{colors.slate-100}"
    textColor: "{colors.slate-900}"
  pulldown-option-selected:
    textColor: "{colors.indigo-700}"
    typography: "{typography.body-strong}"
  card:
    backgroundColor: "{colors.white}"
    rounded: "{rounded.2xl}"
  map-card:
    backgroundColor: "{colors.slate-100}"
    rounded: "{rounded.2xl}"
  device-panel:
    backgroundColor: "{colors.white}"
    rounded: "{rounded.2xl}"
    width: "340px"
  device-row:
    textColor: "{colors.slate-900}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.lg}"
    padding: "7px 8px"
  device-row-hover:
    backgroundColor: "{colors.slate-100}"
  device-row-current:
    backgroundColor: "{colors.indigo-50}"
    textColor: "{colors.indigo-700}"
  map-chip:
    backgroundColor: "{colors.white}"
    textColor: "{colors.slate-900}"
    typography: "{typography.label-strong}"
    rounded: "{rounded.md}"
    padding: "4px 10px"
  map-chip-selected:
    backgroundColor: "{colors.indigo-50}"
    textColor: "{colors.indigo-700}"
  new-mark:
    backgroundColor: "{colors.amber-50}"
    textColor: "{colors.amber-700}"
    rounded: "{rounded.sm}"
    padding: "0 6px"
  notice:
    backgroundColor: "{colors.rose-50}"
    textColor: "{colors.rose-700}"
    typography: "{typography.body}"
    rounded: "{rounded.xl}"
    padding: "12px 16px"
  table-header:
    backgroundColor: "{colors.white}"
    textColor: "{colors.slate-600}"
    typography: "{typography.label-strong}"
    padding: "0 12px"
    height: "38px"
  table-cell:
    textColor: "{colors.slate-700}"
    typography: "{typography.label}"
    padding: "0 12px"
    height: "36px"
---

# Design System: Freds LAN

## Overview

**Creative North Star: "The Quiet Workbench"**

Freds LAN is a tool for looking something up, then getting on with the day. It belongs to the user's ffa product family: a pale slate room, white cards with hairline borders, one indigo voice, and a single typeface doing every job. The chrome stays quiet so that the network itself, drawn as a real 3D arrangement around the router, is the only thing with presence.

The density is that of a small desktop utility rather than a web page. The window never scrolls as a whole: a white toolbar sits above two working cards that fill the rest of the height, text is 12 to 13px, and controls are 36px tall. Lists and the table scroll inside their own cards.

The system refuses a themed costume of any kind. The 3D map earns its place by stating facts: bearing comes from the last IP octet, height from how many addresses a device answers on, and colour from its role.

**Key Characteristics:**
- JetBrains Mono for all text, bundled so the app works offline.
- Slate neutrals, with indigo reserved for action, focus, selection and the router.
- White cards on a slate-50 page, separated by 1px borders and very soft shadows.
- A radius scale of 6, 8, 10, 14 and 18px, with the outermost container roundest.
- Light only.

## Colors

Tailwind's slate and indigo, with sky and emerald for device roles and amber and rose for state.

### Primary
- **Working Indigo** (#4f46e5): The Scan button, the router on the map, the scan arc, the link to the selected device, checkmarks and sort arrows. The hover and pressed-text partner is **Deep Indigo** (#4338ca).
- **Focus Periwinkle** (#a5b4fc): The border of a focused or open control.
- **Focus Halo** (#e0e7ff): The 4px ring around a focused or open control, and the text selection background.
- **Selection Wash** (#eef2ff): The fill of whatever is currently selected: a pressed segment, the current device row, a selected table row, a selected map chip.

### Secondary
- **Access Point Sky** (#0ea5e9): Devices with the access point role, on the map and as list and legend dots.
- **This Mac Emerald** (#10b981): The user's own Mac on the map and as a dot. It also marks a device that answers ping in the table.

### Tertiary
- **New Amber** (#b45309 text on #fffbeb, #fde68a border): The "New" mark on a device that has not been clicked yet.
- **Alarm Rose** (#be123c text on #fff1f2, #fecdd3 border): Notices and form errors. **Ping Rose** (#f43f5e) is the table's dot for a device that does not answer ping.

### Neutral
- **Page Slate** (#f8fafc): The page behind the cards, and button and table-header hover.
- **Map Slate** (#f1f5f9): The map card's ground, list and option hover, and table row rules.
- **Card White** (#ffffff): Toolbar, cards, inputs, buttons, chips and the map's disc.
- **Hairline** (#e2e8f0): Every resting border, and the disc's rim.
- **Strong Hairline** (#cbd5e1): Border on hover, scrollbars, the drop lines under devices on the map.
- **Line Slate** (#94a3b8): Map rings, ticks and leader lines, and the pulldown chevron. Not for text.
- **Quiet Ink** (#64748b): Secondary text: IP addresses, field labels, status line, placeholders.
- **Soft Ink** (#475569): Guessed and unnamed names, inactive segments, table headers, rim numerals, and devices with no special role on the map.
- **Control Ink** (#334155): Default button text and table cells.
- **Ink** (#0f172a): Primary text, confirmed device names, and the colour of every lifting shadow.

### Brand Asset
- **Logo Violet** (#7c3aed): The smiling monkey mark, taken from the fill of `assets/monkey-purple.svg`. The app icon, `assets/AppIcon.png` with its `assets/AppIcon.icns` build, sets this mark in violet on a white rounded square. It identifies the app in the Dock, the menu bar and the app bundle, and does not appear inside the window.

### Named Rules
**The Indigo Earns It Rule.** Indigo appears only on the primary action, on focus, on selection and on the router and scan. If nothing is being acted on or chosen, it is not indigo.

**The State Colour Rule.** Amber says a device is new. Rose says something failed or does not answer. Neither is ever decoration.

**The Logo Is Not An Accent Rule.** Logo Violet belongs to the mark. Interface accents stay Working Indigo, even though the two are close.

## Typography

**Display Font:** JetBrains Mono (with ui-monospace, Menlo, monospace)
**Body Font:** JetBrains Mono
**Label/Mono Font:** JetBrains Mono

**Character:** One variable monospace face, loaded from local files, carries the app name, the prose and the addresses alike. Hierarchy comes from small steps in size and weight, and from colour.

### Hierarchy
- **Headline** (600, 18px, 1.45, -0.02em): The app name in the toolbar.
- **Title** (600, 16px, 1.45, -0.02em): The heading of the device list.
- **Title Small** (600, 14px): Notice headings and the router's name on the map.
- **Body** (400, 13px, 1.45): Base text, inputs, options and the detail panel's empty state.
- **Body Strong** (500, 13px, 1.45): Buttons, segments and device names in the list.
- **Label** (400, 12px, 1.45): Status line, field labels, the detail facts, IP addresses and table cells.
- **Label Strong** (600, 12px, 1.3): Names on map chips and table headers.

### Named Rules
**The One Family Rule.** All text is JetBrains Mono, including the numerals drawn into the 3D scene. Hierarchy never comes from a second typeface.

**The Guess Reads Lighter Rule.** A name the user gave carries weight and full ink. A guessed or missing name is regular weight in Soft Ink, so a guess never looks like a fact.

**The 12px Floor Rule.** No interface text goes below 12px.

## Layout

The window is a fixed-height column that does not scroll. A white toolbar (10px vertical and 16px horizontal padding, 10px gap) holds the app name, the network pulldown, Scan, Export and the Map/Table switch, with the status line taking the remaining width, right-aligned and truncated.

Below it, the workspace has 16px padding and a 16px gap. The map or the table flexes to fill the left, and a fixed 340px panel holds the device list above the details. The map and the table occupy the same slot, never side by side. In the table view the list gives way: the panel appears only once a device is selected, and its details fill it.

Spacing moves in small steps from 4 to 16px: 4 to 6px inside a line or between a label and its field, 8 to 12px between controls, 14 to 16px for card padding. Each scrolling region scrolls itself with a thin slate scrollbar. Below a 1100px window width the map's drag hint drops out and the legend stays. Past 14 devices the map's chips drop the address line, and an unnamed device shows its last octet.

## Elevation & Depth

A hybrid in which borders do the structural work. Cards and standalone controls have a 1px border, and lifting shadows are only ever a slate-900 tint, kept low. The 3D map is the one place with real depth: a thick white disc under soft cast shadows, lit from above.

### Shadow Vocabulary
- **Card** (`box-shadow: 0 1px 2px 0 rgb(15 23 42 / 0.05)`): All cards at rest.
- **Chip** (`box-shadow: 0 1px 3px 0 rgb(15 23 42 / 0.1)`): Map chips, which float over the scene.
- **Menu** (`box-shadow: 0 10px 15px -3px rgb(15 23 42 / 0.1), 0 4px 6px -4px rgb(15 23 42 / 0.1)`): The open pulldown, the only overlay.
- **Focus Halo** (`box-shadow: 0 0 0 4px #e0e7ff`): Focused controls and the open pulldown trigger. Inside the table's header it becomes a 2px inset line in Focus Periwinkle, so it is not clipped.

### Named Rules
**The Lift Follows Distance Rule.** The further something floats above the page, the larger its shadow: card, then chip, then menu. Nothing else gets a lifting shadow.

## Shapes

Soft, rounded rectangles on ffa's scale, which derives from a 10px base. Containers are rounder than what they hold: cards at 18px, then fields, the pulldown, the view switch and notices at 14px, buttons, segments and list rows at 10px, chips and code blocks at 8px, and the "New" mark and small icon buttons at 6px. Dots are full circles at 10px. Icons are 16px stroked outlines (14px in dense spots) with round caps and joins, stroke width 2 on a 24-unit grid, drawn inline.

### Named Rules
**The Nested Radius Rule.** A control is never rounder than the container that holds it.

## Components

### Buttons
Plain and confident, with a single filled button in the window.
- **Shape:** Gently rounded (10px), 36px tall, 12px side padding, with a 6px gap to any icon.
- **Primary:** White text on Working Indigo with a matching border and a 124px minimum width, so the label can change to "Scanning…" without moving the toolbar. Its icon spins while busy.
- **Default:** Control Ink on white with a Hairline border.
- **Hover / Focus:** Border and fill shift over 150ms ease-out: default to Page Slate with a Strong Hairline border, primary to Deep Indigo. Focus sets a Focus Periwinkle border and the 4px Focus Halo.
- **Disabled:** 50% opacity, default cursor.
- **Icon button:** A borderless 24px square with a 6px radius and a 14px icon, used to open a device's page. Hover is Selection Wash with Deep Indigo.

### Segmented Switch
A white 14px pill with a Hairline border and 3px padding, holding 28px borderless segments at 10px radius. Pressed is Selection Wash with Deep Indigo, and hover on the others is Map Slate. It switches between Map and Table, and sets a device's role in the detail panel, where it stretches to the full width at 12px text.

### Pulldown
The network selector, a custom listbox. The trigger is 232px wide at 14px radius, with a Line Slate chevron that turns 180 degrees over 150ms when open and keeps the focus treatment while open. The menu sits 6px below at the same width and radius, with the Menu shadow, up to 320px tall. Options have 8px and 14px padding, the active one on Map Slate with Ink, the selected one in medium-weight Deep Indigo with a check at the right.

### Cards
- **Corner Style:** Softly rounded (18px).
- **Background:** Card White, except the map card, which sits on Map Slate so its white disc reads.
- **Shadow Strategy:** The Card shadow.
- **Border:** 1px Hairline.
- **Internal Padding:** 14px and 16px, set by the content rather than the card. Regions inside are divided by a 1px Hairline.

### Inputs
- **Style:** White, 1px Hairline, 14px radius, 36px tall, 12px side padding, Quiet Ink placeholder.
- **Focus:** Focus Periwinkle border and the 4px Focus Halo, the same as buttons.
- **Error:** A 12px line of Alarm Rose text beneath the field.

### Device List
Rows in a 12px dot column, a name and the address beneath it, at 10px radius with 7px and 8px padding and no border. Hover is Map Slate. The current row is Selection Wash with its name in Deep Indigo. The router sorts first, then ascending IP. Details below use a 72px label column at 12px, with Quiet Ink labels.

### Map Chips
White 8px labels with a Hairline border and the Chip shadow, up to 190px wide, tied to their device by a 1px Line Slate leader. They show the name, the address beneath it, and a "New" mark when due. Selected chips take Selection Wash, a Focus Periwinkle border and a Deep Indigo name. The router's chip is centred with a 14px name. A translucent white legend and hint sit in the bottom corners, also at 8px.

### New Mark
A small amber tag (6px radius, 6px side padding, 12px medium text) that stays on a device until it is clicked, in both the list and the map.

### Notice
A full-width rose banner under the toolbar (14px radius, 12px and 16px padding) with a 14px heading. A command the user needs to run sits in a white 8px block, selectable in one click.

### Device Table
A dense sortable table on a card: a sticky 38px header in Soft Ink at 12px weight 600, 36px rows divided by Map Slate lines, and a sticky first column separated by a 1px Hairline. Hover is Page Slate, the selected row is Selection Wash with its name in Deep Indigo. The sort column shows a 14px indigo arrow. Ping is a 10px dot, hollow when a device doesn't answer, emerald for an answer, Ping Rose for none and Strong Hairline for unknown.

### Network Map
The signature component. A white disc with real thickness rests in the map card, with the router above its centre as an indigo sphere and ring. Faint Line Slate rings and spokes divide the disc, and the rim reads in last IP octets, numbered every 32. Devices are small role-coloured spheres on thin drop lines, holding a stable bearing from their address as others join, with extra addresses shown as smaller linked points. Selecting a device draws an indigo ring around it and an indigo curve back to the router.

During a scan an indigo arc turns over the disc (2.4 seconds per turn). Each device briefly swells and flushes indigo as the arc crosses (0.7 seconds), and new ones appear as it passes (0.55 seconds). With reduced motion the arc and the Scan spinner do not run, and camera moves are immediate. Drag turns the view and scrolling zooms, with no panning.

## Do's and Don'ts

### Do:
- **Do** use exactly one filled Working Indigo button in a view.
- **Do** mark selection the same way everywhere: Selection Wash (#eef2ff) with Deep Indigo (#4338ca) text.
- **Do** give every focusable control the Focus Periwinkle border and 4px Focus Halo.
- **Do** write labels in sentence case, and keep guessed names in the lighter style.
- **Do** bundle every font and asset locally; the app must work offline.
- **Do** use `assets/AppIcon.png` for the app's icon as supplied, and `assets/monkey-purple.svg` as the source of the mark.
- **Do** let position, height and colour on the map state real facts from the scan.

### Don't:
- **Don't** dress the app in a themed costume; it is a working tool in the ffa family.
- **Don't** use a typeface other than JetBrains Mono.
- **Don't** use amber or rose for anything but state.
- **Don't** use Logo Violet (#7c3aed) as an interface accent.
- **Don't** set Line Slate (#94a3b8) as text; it falls below reading contrast on white.
- **Don't** add a corner radius outside the 6, 8, 10, 14 and 18px scale; full circles are for dots.
