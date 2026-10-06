# ShopTheReel — Design System

## 1. Overview

**Product:** a mobile app (Expo / React Native) that turns a shared fashion reel into a shoppable, full outfit.
**Personality:** quiet luxury, editorial, warm, confident. Think a menswear/womenswear lookbook at night, not a bright discount marketplace. The clothes are the hero; the UI stays dark and calm so product imagery glows.
**Platform:** mobile-first, portrait, one-handed use. Dark theme only for v1.
**Keywords:** earthy, premium, minimal, tactile, cinematic.

---

## 2. Colour

### 2.1 Brand palette (given)

| Name | Hex | Role |
|---|---|---|
| Charcoal | `#090907` | App background, deepest surface |
| Earth Brown | `#6C5636` | Secondary fills, borders, selected-state backgrounds, tier/segment highlights. **Never for body text on Charcoal** (contrast ≈ 2.9:1) |
| Burnt Amber | `#B99D73` | Primary accent: primary buttons, active icons, links, price highlights, focus rings (contrast on Charcoal ≈ 7.7:1) |

### 2.2 Derived neutrals and states (derived from the palette; adjust if you like)

| Token | Hex | Use |
|---|---|---|
| `bg` | `#090907` | Screen background |
| `surface` | `#141210` | Cards, sheets |
| `surface-raised` | `#1E1A15` | Elevated cards, modals, bottom bar |
| `border` | `#2E261C` | Hairline dividers, card outlines |
| `brown` | `#6C5636` | Selected chip/segment background, progress track fill |
| `brown-soft` | `#6C563633` | Brown at 20% for tinted backgrounds |
| `amber` | `#B99D73` | Primary accent |
| `amber-pressed` | `#A38762` | Pressed state of amber |
| `amber-soft` | `#B99D7326` | Amber at 15% for subtle highlights |
| `text-primary` | `#F2EBDD` | Headings, key text (warm ivory) |
| `text-secondary` | `#A89F8E` | Supporting text, captions |
| `text-disabled` | `#5E574B` | Disabled text/icons |
| `on-amber` | `#090907` | Text/icons on amber buttons |
| `success` | `#8FB573` | Confirmations, "in stock" |
| `warning` | `#D9A441` | Low stock, over budget flag |
| `error` | `#D9695F` | Errors, "wrong item" |

### 2.3 Rules
- Backgrounds: `bg` for screens, `surface` for cards, `surface-raised` for overlays. Use at most 3 elevation levels.
- Amber is the **only** strong accent. One primary amber action per screen.
- Earth Brown is for *fills and states*, not text.
- No pure white or pure black. Text is ivory (`#F2EBDD`).
- Gradients: only subtle `bg → surface` vertical fades and a dark scrim (`#090907` 0 → 85%) over images behind text.

---

## 3. Typography

| Role | Font | Weight | Size / line-height |
|---|---|---|---|
| Display | Fraunces (serif) | 600 | 32 / 38 |
| Title L | Fraunces | 600 | 24 / 30 |
| Title M | Fraunces | 500 | 20 / 26 |
| Body | Inter | 400 | 15 / 22 |
| Body strong | Inter | 600 | 15 / 22 |
| Label | Inter | 500 | 13 / 18, letter-spacing +0.2 |
| Caption | Inter | 400 | 12 / 16 |
| Price | Inter (tabular numerals) | 600 | 16 / 20 |

- Serif for emotional/editorial headings (screen titles, outfit names, tier titles). Inter for everything functional.
- Currency format: `₹1,299` (rupee sign, Indian digit grouping). Original price struck through in `text-disabled`.
- Max 2 font families. Sentence case everywhere, no ALL CAPS except tiny overlines (Label, +1.0 tracking).

---

## 4. Layout, spacing, shape

- **Spacing scale (4pt):** 4, 8, 12, 16, 20, 24, 32, 40, 56.
- **Screen padding:** 20 horizontal. Respect safe areas.
- **Corner radius:** chips 999 (pill), buttons 14, cards 20, images in cards 16, bottom sheets 28 (top corners).
- **Borders:** 1px `border`. Selected = 1.5px `amber`.
- **Elevation:** dark UIs rely on surface tone, not shadows. Use `surface-raised` + 1px `border`. Only modals get a soft shadow (`0 12 32 #00000099`).
- **Touch targets:** min 44×44.
- **Grid:** single column feed; product cards in a 2-column grid with 12 gutter where used.

---

## 5. Components

**Primary button:** amber fill, `on-amber` label (Inter 600, 15), height 52, radius 14, full width in forms. Pressed: `amber-pressed`. Disabled: `brown-soft` fill, `text-disabled` label.
**Secondary button:** transparent, 1px `brown` border, ivory label. Pressed: `brown-soft` fill.
**Text button:** amber label, no container.
**Chips (style tags, sizes, colours):** pill, height 36, `surface` fill, 1px `border`, ivory text. Selected: `brown` fill, 1px `amber` border, ivory text.
**Segmented control (tiers: Exact / Similar / Budget):** `surface` track, radius 14, height 44. Active segment: `brown` fill with amber label and a 1px amber border. Show a small price under each tier label (e.g. "₹7,490").
**Product item card:** `surface`, radius 20, padding 12. Left: detected crop from the reel (72×96, radius 12) with a thin amber connector/arrow to the matched product image (right, 96×120). Below: brand (Label, secondary), title (Body strong, 2 lines max), size chip, price (Price, amber if best value), "why this match" one-liner in italic Caption, secondary colour. Actions row: ♡ like, ✕ dislike, "Wrong item?" text button, and **Buy** primary button (compact, height 40).
**Match confidence badge:** pill on the product image, `surface-raised` at 90% with amber dot + "92% match". Low confidence (<60%) uses the `warning` dot.
**Bounding-box overlay (items view):** 1.5px amber rounded rectangle on the frame with a small label pill (category) in `surface-raised`.
**Total bar (sticky bottom of outfit screen):** `surface-raised`, top 1px `border`, left: "Total · 5 items" + price (Title M, ivory), right: amber "Buy all" button. Over-budget shows a `warning` chip "₹ 640 over budget".
**Bottom tab bar:** 4 tabs (Home, Looks, Add [centre, amber circle 56px], Profile). Inactive icons `text-secondary`, active `amber`, label 11px. Background `surface-raised`, top border `border`.
**Bottom sheet:** `surface-raised`, top radius 28, grabber 36×4 `border`.
**Progress (processing screen):** vertical stepper; completed steps amber check, current step amber pulsing dot, upcoming `text-disabled`. Each step has a one-line status (e.g. "Spotting garments…").
**Inputs:** height 52, `surface` fill, 1px `border`, radius 14, focus 1.5px amber, label above in Label style.
**Slider (budget):** track `border`, active range `amber`, thumb ivory with amber ring; value labels in Price style.
**Toasts:** `surface-raised`, left 3px accent bar (success/warning/error), bottom, above the tab bar.
**Empty states:** simple line illustration in `brown`/`amber` strokes, Title M headline, one-line helper, one primary action.

---

## 6. Iconography and imagery

- Icon set: Lucide (stroke 1.75, rounded caps). 24px default, amber for active, `text-secondary` inactive.
- Product and reel imagery is never recoloured or filtered. Round corners only. Use a dark scrim under overlaid text.
- Placeholder imagery: warm dark-grey blocks (`surface-raised`) with a subtle shimmer from `surface-raised` to `#262019`.

---

## 7. Motion

- Durations: 150 ms (press), 250 ms (transitions), 400 ms (sheet/segmented).
- Easing: standard ease-out; spring (damping ~18) for sheets and card reveals.
- Outfit results: items fade-and-rise in with a 60 ms stagger. Tier switch cross-fades the list.
- Haptics: light impact on like/dislike, success notification when the outfit is ready.
- Respect "reduce motion".

---

## 8. Accessibility

- Text contrast ≥ 4.5:1 (ivory and secondary on all surfaces pass; amber passes on `bg`, `surface`, `surface-raised`).
- Never rely on colour alone: pair status colours with icons/labels.
- Support dynamic type up to 130% without clipping; cards grow vertically.
- Every image has an accessibility label (e.g. "Olive green oversized t-shirt, matched product").

---

## 9. Screens (v1)

1. **Onboarding:** gender, sizes, budget slider, style chips (visual, big tappable tiles)
2. **Home:** recent looks, empty state "Share a reel to get started"
3. **Share receiver:** media preview, kind selector, Analyse button; link-only variant prompting for a screen recording
4. **Processing:** stepper with live stage status
5. **Detected items:** frames with bounding-box overlays, list of items
6. **Outfit result (hero):** reel crop strip, tier segmented control, item cards, "Complete the look" section, sticky total bar
7. **Alternatives sheet:** swap candidates for one item
8. **Saved looks and boards**
9. **Profile and Style DNA**

---

## 10. Design tokens for React Native (`apps/mobile/src/theme/tokens.ts`)

```ts
export const colors = {
  bg: '#090907',
  surface: '#141210',
  surfaceRaised: '#1E1A15',
  border: '#2E261C',
  brown: '#6C5636',
  brownSoft: 'rgba(108,86,54,0.20)',
  amber: '#B99D73',
  amberPressed: '#A38762',
  amberSoft: 'rgba(185,157,115,0.15)',
  textPrimary: '#F2EBDD',
  textSecondary: '#A89F8E',
  textDisabled: '#5E574B',
  onAmber: '#090907',
  success: '#8FB573',
  warning: '#D9A441',
  error: '#D9695F',
} as const;

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 24, xxxl: 32 } as const;
export const radius = { chip: 999, button: 14, card: 20, image: 16, sheet: 28 } as const;

export const fonts = {
  display: 'Fraunces_600SemiBold',
  titleM: 'Fraunces_500Medium',
  body: 'Inter_400Regular',
  bodyStrong: 'Inter_600SemiBold',
  label: 'Inter_500Medium',
} as const;
```

Agent notes: load fonts with `@expo-google-fonts/fraunces` and `@expo-google-fonts/inter`; use these tokens only (no hard-coded colours in screens); build components as reusable primitives (`Button`, `Chip`, `SegmentedControl`, `ProductCard`, `TotalBar`, `Sheet`) before screens.

---

## 11. Do and don't

**Do:** keep screens spacious, let imagery lead, use serif sparingly for moments of delight, show the reason behind each match, make the price and size obvious.
**Don't:** add extra accent colours, use bright white, use heavy shadows, use cramped lists, or show fake purchase links without the "Demo partner" badge.
