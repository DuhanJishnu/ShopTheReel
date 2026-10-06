---
name: Quiet Editorial Lookbook
colors:
  surface: '#141210'
  surface-dim: '#141311'
  surface-bright: '#3a3936'
  surface-container-lowest: '#0e0e0c'
  surface-container-low: '#1c1c19'
  surface-container: '#20201d'
  surface-container-high: '#2a2a27'
  surface-container-highest: '#353532'
  on-surface: '#e5e2dd'
  on-surface-variant: '#d0c5b7'
  inverse-surface: '#e5e2dd'
  inverse-on-surface: '#31302d'
  outline: '#998f83'
  outline-variant: '#4d463b'
  surface-tint: '#e0c295'
  primary: '#e0c295'
  on-primary: '#402d0d'
  primary-container: '#b99d73'
  on-primary-container: '#483413'
  inverse-primary: '#725b36'
  secondary: '#e0c29a'
  on-secondary: '#3f2d11'
  secondary-container: '#584325'
  on-secondary-container: '#cdb18a'
  tertiary: '#bac7e4'
  on-tertiary: '#243148'
  tertiary-container: '#94a1bd'
  on-tertiary-container: '#2b384f'
  error: '#D9695F'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#fedeaf'
  primary-fixed-dim: '#e0c295'
  on-primary-fixed: '#281900'
  on-primary-fixed-variant: '#584321'
  secondary-fixed: '#fddeb5'
  secondary-fixed-dim: '#e0c29a'
  on-secondary-fixed: '#281901'
  on-secondary-fixed-variant: '#584325'
  tertiary-fixed: '#d7e3ff'
  tertiary-fixed-dim: '#bac7e4'
  on-tertiary-fixed: '#0e1c32'
  on-tertiary-fixed-variant: '#3a475f'
  background: '#141311'
  on-background: '#e5e2dd'
  surface-variant: '#353532'
  bg: '#090907'
  surface-raised: '#1E1A15'
  border: '#2E261C'
  brown-soft: rgba(108, 86, 54, 0.20)
  amber-pressed: '#A38762'
  amber-soft: rgba(185, 157, 115, 0.15)
  text-primary: '#F2EBDD'
  text-secondary: '#A89F8E'
  text-disabled: '#5E574B'
  on-amber: '#090907'
  success: '#8FB573'
  warning: '#D9A441'
typography:
  display:
    fontFamily: Fraunces
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 38px
  display-mobile:
    fontFamily: Fraunces
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 34px
  title-lg:
    fontFamily: Fraunces
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 30px
  title-md:
    fontFamily: Fraunces
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 26px
  body:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
  body-strong:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 22px
  label:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.2px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 1.0px
  caption:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  price:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 20px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 0.75rem
  margin: 1.25rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.25rem
---

## Brand & Style

This design system embodies dark quiet luxury, drawing inspiration from high-fashion editorial lookbooks viewed under intimate evening light. Rather than feeling like a bustling marketplace or discount retail hub, the interface assumes a restrained, confident gallery aesthetic where garment silhouettes and product textures become the vivid heroes against deep, warm darkness.

The visual style blends modern tactile minimalism with refined editorial typography. Every element prioritizes spaciousness, deliberate touch choreography, and one-handed mobile ergonomics. Interfaces employ gentle tonal layering instead of harsh skeuomorphic drop shadows, pairing deeply saturated warm undertones with precision hairline dividers. The emotional resonance is calm, discerning, bespoke, and cinematic.

## Colors

The palette operates in strict dark mode, anchored by deep soot and warm charcoal neutrals that keep screen glare low and product colors vibrant.

- **Primary Accent (`#B99D73` / Burnt Amber):** The sole chromatic focus of the interface, reserved for primary calls-to-action, active icons, match confidence rings, and focal prices. It yields a generous 7.7:1 contrast ratio against the screen base.
- **Secondary Fill (`#6C5636` / Earth Brown):** A grounding earth tone designed strictly for selected container fills, subtle indicators, and tier switches. It is never employed for small body copy over dark surfaces.
- **Surfaces & Neutral (`#090907`, `#141210`, `#1E1A15`):** Three distinct tonal elevation layers provide structured depth without stark contrast. Hairline edges use `#2E261C` to delineate boundaries cleanly.
- **Typography Tones (`#F2EBDD`, `#A89F8E`):** Pure white is forbidden; Warm Ivory serves as primary text, backed by muted sandstone for secondary details and captions.
- **Feedback Signals:** Soft natural pigments (`#8FB573` success, `#D9A441` warning, `#D9695F` error) alert users without clashing against the lookbook atmosphere.

## Typography

The typography pairs an expressive editorial serif with a crisp, geometric sans-serif:

- **Fraunces:** Selected for headline tiers, screen titles, and garment curations. Its organic optical curves impart editorial authority and warmth.
- **Inter:** Serves functional operations, forms, filters, item metadata, and pricing. Tabular figures are enforced for all pricing strings (`₹1,299`) to preserve vertical alignment across list cards.
- **Casing & Hierarchy:** Sentence case governs all titles and UI copy. All-caps is constrained exclusively to miniature overline tags (`label-caps`) with open letter tracking (+1.0px).

## Layout & Spacing

A 4pt rhythm governs every dimension. Screen content is framed by standard 20px (`1.25rem`) horizontal margins to maintain comfortable thumb reach and breathing room on mobile viewports.

- **Grid:** Feed views leverage a single-column sequence for narrative pacing, transitioning into a 2-column layout with 12px (`0.75rem`) gutters when rendering grid-based alternate match lists.
- **Vertical Rhythm:** Gaps scale incrementally: 4px (`space-xs`) for icon-to-label adjacency, 8px (`space-sm`) for compact item groupings, 12px (`space-md`) for container interior insets, 16px (`space-lg`) between distinct content chunks, and 20px–32px for macro-section offsets.
- **Safe Bounds:** Top app bars and bottom interaction ribbons respect device safe areas, guaranteeing hit zones remain at least 44×44px.

## Elevation & Depth

Visual hierarchy is communicated through subtle tonal stacking and tactile border outlines rather than diffuse colored dropshadows:

1. **Base Tier (`bg` / `#090907`):** The foundational canvas for screens and continuous scroll feeds.
2. **Card & Surface Tier (`surface` / `#141210`):** Inset content modules and unselected action tiles, bound by a crisp 1px hairline border in `#2E261C`.
3. **Floating & Modal Tier (`surface-raised` / `#1E1A15`):** Overlays, sticky bottom checkout strips, floating pills, and action sheets. Elevated modals layer a deeply diffused shadow (`box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6)`) coupled with a perimeter hairline.
4. **Imagery Scrims:** Full-bleed image containers employ a progressive vertical scrim gradient transitioning from transparent to 85% opacity `#090907` to maintain text legibility without obscuring apparel styling.

## Shapes

The geometric framework balances organic curve treatments with structural utility:

- **Pill (Radius 999px):** Dedicated to category chips, floating status indicators, tag triggers, and active match confidence badges.
- **Buttons & Form Fields (Radius 14px):** Standard interactive touch points, offering a soft hand-held feel without losing structural presence.
- **Internal Media (Radius 16px):** Garment crop windows and external affiliate product preview images.
- **Cards & Enclosures (Radius 20px):** Primary match containers and outfit summary cards.
- **Bottom Sheets (Radius 28px):** Applied to the top corners of pull-up sheets to echo modern mobile operating-system aesthetics.

## Components

- **Buttons:**
  - *Primary:* Height 52px, radius 14px. Background is Burnt Amber (`#B99D73`), label in Inter 600 `#090907`. Pressed state darkens to `#A38762`. Disabled uses a 20% Earth Brown tint (`rgba(108,86,54,0.20)`) with `#5E574B` text.
  - *Secondary:* Height 52px, radius 14px, transparent interior, 1px border in Earth Brown (`#6C5636`), Warm Ivory text.
  - *Text:* No border or fill, inline Burnt Amber text.

- **Chips & Filters:**
  - Height 36px, full pill (radius 999px). Rest state uses `#141210` fill with 1px `#2E261C` border and Warm Ivory text. Selected state transforms to Earth Brown fill (`#6C5636`) with a 1px Burnt Amber border.

- **Segmented Control (Tiers: Exact / Similar / Budget):**
  - Continuous container height 44px on `#141210`, radius 14px. Active tab slides with `#6C5636` fill, 1px Burnt Amber border, and Burnt Amber label with tabular sub-price text underneath.

- **Product Match Card:**
  - Enclosed in `#141210` with 20px corner radius and 12px padding. Features a dual-image compare layout: detected reel crop (72×96px, radius 12px) linked via a slim amber pointer to the catalog match (96×120px, radius 16px).
  - Metadata block displays brand name (`label-caps`), garment title (`body-strong`), size tag, price (`price` token), match reason italic caption, and inline compact action buttons (♡, ✕, "Wrong item?", Buy 40px height).

- **Match Confidence Badge:**
  - Floating pill anchored on product imagery in `#1E1A15` (90% opacity) showing an amber indicator dot and percentage score (`label`).

- **Total Summary Bar:**
  - Pinned bottom bar in `#1E1A15` with a 1px `#2E261C` top divider. Left: item tally and aggregated sum in Fraunces `title-md`; right: full-bleed amber "Buy all" action.

- **Inputs & Budget Slider:**
  - Inputs feature height 52px, radius 14px, `#141210` fill, and `#2E261C` hairline border, focusing to a 1.5px Burnt Amber outline.
  - Slider leverages `#2E261C` for inactive track, Burnt Amber for active range, and a Warm Ivory thumb with an amber halo.

- **Iconography:**
  - Lucide set rendered at 24px with 1.75 stroke width and rounded joins. Inactive icons sit in `#A89F8E`; selected or active icons illuminate in `#B99D73`.