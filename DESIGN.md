# Design System: Bev Watch

This document records the implemented Bev Watch tokens, component patterns, and responsive behavior for consistent future interface work.

## Overview

Bev Watch extends the existing application's blue and neutral interface with a compact red beverage mark. The implemented system combines large, tightly tracked public headings with a denser workspace built from lists, restrained panels, visible labels, and source context.

This record captures the public website, five-step onboarding, and browser-local preview from source. Those surfaces explicitly use a light color scheme. The existing local application retains its separate semantic light and dark theme tokens. No rendered verification was available for this documentation pass.

**Key Characteristics:**

- Navy actions and selection treatments on pale blue-gray surfaces.
- System sans typography with Georgia emphasis on public headings and briefing paper.
- Thin dividers, compact tags, and modest corner radii.
- Larger public composition and compact task-oriented workspace density.

```yaml
name: Bev Watch
description: The implemented blue and neutral visual system for Bev Watch.
colors:
  bw-navy: "#183e56"
  bw-ink: "#1b303c"
  bw-muted: "#526674"
  bw-line: "#d8e1e6"
  bw-paper: "#f7f9fa"
  raised: "#ffffff"
  brand-red: "#b33a36"
  focus: "#1d5a92"
  button-hover: "#285c79"
  light-hover: "#e9f1f5"
  outline-hover: "#eaf0f4"
  control-border: "#8b9da9"
  tag-surface: "#e7f0f5"
  tag-ink: "#24536d"
  priority-surface: "#f8ebe5"
  priority-ink: "#8d4026"
  choice-border: "#a9bac4"
  choice-selected-border: "#376d8a"
  choice-selected-surface: "#edf4f8"
  error-surface: "#fff0e9"
  error-ink: "#933e25"
  notice-surface: "#e8f3ed"
  notice-ink: "#285d46"
  selection-surface: "#dcebf3"
  scrollbar: "#9babb5"
  editorial-ink: "#2a617b"
  outline-border: "#7a8e9c"
  text-action: "#1d5a79"
  feature-shadow: "#17395119"
  preview-label: "#d6e6ee"
  live-dot: "#bad7e6"
  source-strip: "#f0f4f6"
  step-number: "#607481"
  closing-emphasis: "#c6dce8"
  closing-copy: "#d8e6ee"
  plan-icon: "#2b647c"
  plan-surface: "#ecf2f6"
  placeholder: "#5d6f7b"
  note-surface: "#edf3f7"
  note-ink: "#31536a"
  nav-hover: "#f2f6f8"
  banner-border: "#d5e2ea"
  banner-surface: "#eef4f7"
  banner-ink: "#34566c"
  review-hover: "#286d91"
  context-surface: "#edf2f5"
  tab-selected: "#dfebf2"
  review-copy: "#435c6c"
  empty-icon: "#698391"
  monogram-surface: "#e5edf2"
  monogram-ink: "#335a71"
typography:
  display:
    fontFamily: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif'
    fontSize: "clamp(40px, 5.3vw, 74px)"
    fontWeight: 550
    lineHeight: 1.1
    letterSpacing: "-.035em"
  headline:
    fontSize: "48px"
    fontWeight: 550
    lineHeight: 1.1
    letterSpacing: "-.035em"
  title:
    fontSize: "30px"
    fontWeight: 550
    lineHeight: 1.25
    letterSpacing: "-.03em"
  body:
    fontSize: "15px"
    lineHeight: 1.65
  label:
    fontSize: "13px"
    fontWeight: 600
  editorial:
    fontFamily: "Georgia, serif"
    fontWeight: 400
rounded:
  tag: "4px"
  field: "5px"
  control: "6px"
  context: "8px"
  form: "10px"
  feature: "14px"
spacing:
  compact: "8px"
  field-gap: "10px"
  control-gap: "12px"
  action-gap: "22px"
  panel: "24px"
  section: "32px"
  onboarding-panel: "38px"
components:
  button-primary:
    backgroundColor: "{colors.bw-navy}"
    textColor: "{colors.raised}"
    rounded: "{rounded.control}"
    padding: "12px 22px"
  button-primary-hover:
    backgroundColor: "{colors.button-hover}"
  button-small:
    padding: "10px 18px"
  button-light:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.bw-navy}"
    rounded: "{rounded.control}"
    padding: "12px 22px"
  button-outline:
    textColor: "{colors.bw-navy}"
    rounded: "{rounded.control}"
    padding: "12px 22px"
  field:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.bw-ink}"
    rounded: "{rounded.field}"
    padding: "10px 12px"
  tag:
    backgroundColor: "{colors.tag-surface}"
    textColor: "{colors.tag-ink}"
    rounded: "{rounded.tag}"
    padding: "3px 8px"
  tag-priority:
    backgroundColor: "{colors.priority-surface}"
    textColor: "{colors.priority-ink}"
  choice-selected:
    backgroundColor: "{colors.choice-selected-surface}"
    rounded: "{rounded.control}"
    padding: "13px"
  onboarding-panel:
    backgroundColor: "{colors.raised}"
    rounded: "{rounded.feature}"
    padding: "{spacing.onboarding-panel}"
```

## Colors

### Primary

Muted navy carries primary actions, active navigation, progress markers, and the closing public section. The primary button hover color is a lighter blue. The focus token supplies a visible keyboard outline across controls.

### Secondary

The brand red belongs to the compact beverage mark. Warm priority tags distinguish “Review first” content; error and confirmation messages have separate warm and green treatments. These are contextual roles in the implementation.

### Neutral

Paper is the page background; raised white holds forms, the sidebar, and preview cards. Ink carries primary text, muted blue-gray carries supporting text, and the line color separates rows and panels. Controls use a stronger border than passive dividers.

## Typography

The body uses the system sans stack defined in the token block. Georgia supplies italic emphasis in public and onboarding headings and the company heading on exported briefing paper. There is no downloaded font or dedicated monospace face in this system.

| Role | Implemented Use |
| --- | --- |
| Display | Fluid landing heading, with explicit mobile overrides. |
| Headline | Public explanatory section heading. |
| Title | Workspace page heading. |
| Body | Public, onboarding, and workspace base text. |
| Label | Form labels and legends. |
| Editorial | Public emphasis and briefing-paper heading. |

Public display type becomes (58px) at the (800px) breakpoint and (43px) at (540px). Public section headings use (48px), then (42px) and (36px). Workspace headings reduce from (30px) to (27px) at the narrowest breakpoint. Metadata and tags use (10px) through (13px); descriptive workspace text uses (13px) or (14px). Paragraphs have a shared maximum of (72ch), with a narrower landing introduction at (43ch). Tables and numeric utility text use tabular numerals.

## Layout

The public container is centered with a maximum width of (1220px) and a viewport subtraction of (96px). That subtraction becomes (64px) below (1100px), then (40px) below (540px). The landing introduction uses two columns at (1.1fr 1fr) with an (8%) gap; explanatory sections use two equal columns with a (12%) gap. They become one column at (800px).

Onboarding pairs a progress column with a form at (.85fr 1.3fr) and a (10%) gap. At (800px), progress becomes a horizontal row of numbered circles and the form follows it. Two-column choice groups and summary rows become single columns at (540px).

The preview workspace uses a (240px) sticky sidebar and a flexible content column. Main content is capped at (1300px) with (30px 42px) padding. At (800px), the sidebar becomes a top section and navigation scrolls horizontally; main padding becomes (24px). At (540px), inline main padding becomes (20px), heading actions stack, and portfolio and source rows wrap. The overview's (1.5fr 1fr) grid becomes one column at (1100px). The inherited local shell separately compacts its navigation at (767px).

## Elevation & Depth

Most surfaces use flat fills, borders, and horizontal rules. The landing briefing preview is the exception, with the single implemented feature shadow recorded in the sidecar. The onboarding form and pricing panel use white fill and a line border without a shadow.

Button background transitions use (.18s ease-out). The global reduced-motion query removes transitions. There are no entrance animations in the documented surfaces.

## Shapes

Tags have the smallest rounded corners; fields and navigation use slightly larger corners; buttons, choices, and notices use the control radius. Context panels use the context radius, product forms use the form radius, and onboarding, pricing, and landing preview panels use the feature radius. Progress indicators and the preview status dot are circles. The red brand mark is a (32px) square with a (9px) corner radius and a white line symbol.

## Components

### Buttons

Primary buttons pair navy with white text, a minimum height of (48px), (14px) semibold type, and a (12px) internal gap. Small buttons use a minimum height of (42px); the narrow header variant becomes (40px) at (540px). The light variant is used against the navy closing section. Outline buttons have a transparent background and a (1px) border. Disabled primary and outline buttons use (.6) opacity and a not-allowed cursor. Text actions use a blue label and an underline that appears on hover.

All interactive elements retain the global keyboard focus treatment: a (2px) outline with a (2px) offset.

### Inputs And Choices

Fields have a white fill, a (1px) control border, a minimum height of (46px), and (14px) text. Labels sit above fields with an (8px) gap. Textareas resize vertically. Choice rows use native checkbox or radio controls at (17px), with a selected border and pale blue fill. Onboarding validation appears as an alert above the form actions; successful workspace operations use the confirmation treatment.

### Tags And Filters

Small tags use (11px) semibold type and compact padding. A warm tag communicates review priority. Update filter buttons use (12px) text and expose selection through `aria-pressed`, with pale blue fill and navy text.

### Panels And Lists

The landing briefing preview has a navy top strip, rounded outer shell, soft shadow, and white content. Synthetic content is visibly labeled. Onboarding uses a bordered white form panel. Workspace review and source lists rely on dividers and row spacing; supporting business context uses a pale filled panel. The briefing-paper view is a square-cornered white document with a line border.

### Navigation And Progress

Public navigation uses (14px) medium text and underlined hover feedback. Preview workspace navigation uses (13px) text, a pale blue current-page fill, navy current-page text, and `aria-current`. The current onboarding step uses a filled navy circle with white contents; completed steps show a check symbol. The skip link becomes visible on focus.

### Brand

The mark is an inline vector with the red fill token and white (2px) strokes. “Bev” uses weight (700), while “Watch” uses weight (400). The wordmark is (22px), reducing to (20px) with a (28px) mark at (540px). Compact mode displays the mark alone.

## Do's and Don'ts

- **Do** reuse the navy action, pale selection, and neutral surface roles.
- **Do** preserve visible labels, keyboard focus, semantic selection states, and synthetic-preview labeling.
- **Do** follow the implemented responsive changes for progress, navigation, lists, and forms.
- **Don't** apply the inherited local application's dark tokens to the explicitly light public and preview surfaces.
- **Don't** turn the landing preview's shadow into the default treatment for every workspace panel.
- **Don't** present sample regulatory content as current findings.

Source evidence: [Product](PRODUCT.md), [Global Styles](web/src/app/globals.css), [Brand Components](web/src/components/brand.tsx), [Public Landing](web/src/app/page.tsx), [Onboarding](web/src/app/onboarding/page.tsx), [Preview Workspace](web/src/app/workspace/page.tsx), and [Local Shell](web/src/components/shell.tsx).
