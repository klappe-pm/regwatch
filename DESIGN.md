---
name: Bev Watch
description: The blue and neutral visual system for Bev Watch, the public website and the local regwatch ui.
colors:
  surface: "#f6f8fa"
  raised: "#ffffff"
  ink: "#17212b"
  muted: "#4b5866"
  line: "#d6dee7"
  control: "#768799"
  selection: "#e3eef9"
  structure: "#1d5a92"
  on-structure: "#ffffff"
  accent: "#a8481a"
  accent-soft: "#fbede4"
  ok: "#2e6b3f"
  surface-dark: "#0f151b"
  raised-dark: "#151d26"
  ink-dark: "#e5ecf3"
  muted-dark: "#a5b3c2"
  line-dark: "#2a3642"
  control-dark: "#6c7f93"
  selection-dark: "#1b3550"
  structure-dark: "#86bdee"
  on-structure-dark: "#0f151b"
  accent-dark: "#f2a06a"
  accent-soft-dark: "#3a2416"
  ok-dark: "#86c79a"
  black: "#000000"
  white: "#ffffff"
  brand-red: "#b33a36"
  bw-navy: "#183e56"
  bw-ink: "#1b303c"
  bw-muted: "#526674"
  bw-line: "#d8e1e6"
  bw-paper: "#f7f9fa"
  bw-focus: "#1d5a92"
  button-hover: "#285c79"
  light-hover: "#e9f1f5"
  outline-border: "#7a8e9c"
  outline-hover: "#eaf0f4"
  control-border: "#8b9da9"
  placeholder: "#5d6f7b"
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
  emphasis: "#2a617b"
  text-link: "#1d5a79"
  text-selection: "#dcebf3"
  scrollbar-thumb: "#9babb5"
  preview-shadow: "#17395119"
  preview-label: "#d6e6ee"
  live-dot: "#bad7e6"
  strip-surface: "#f0f4f6"
  step-number: "#607481"
  close-emphasis: "#c6dce8"
  close-text: "#d8e6ee"
  check-icon: "#2b647c"
  plan-surface: "#ecf2f6"
  note-surface: "#edf3f7"
  note-ink: "#31536a"
  banner-border: "#d5e2ea"
  banner-surface: "#eef4f7"
  banner-ink: "#34566c"
  nav-hover: "#f2f6f8"
  row-hover: "#286d91"
  context-surface: "#edf2f5"
  tab-selected: "#dfebf2"
  update-ink: "#435c6c"
  empty-icon: "#698391"
  monogram-surface: "#e5edf2"
  monogram-ink: "#335a71"
roles:
  primary: "{colors.structure}"
  on-primary: "{colors.on-structure}"
  secondary-container: "{colors.selection}"
  on-secondary-container: "{colors.structure}"
  tertiary: "{colors.ok}"
  error: "{colors.accent}"
  on-error: "{colors.on-structure}"
  error-container: "{colors.accent-soft}"
  on-error-container: "{colors.accent}"
  background: "{colors.surface}"
  surface: "{colors.surface}"
  surface-container-lowest: "{colors.raised}"
  on-surface: "{colors.ink}"
  on-surface-variant: "{colors.muted}"
  outline: "{colors.control}"
  outline-variant: "{colors.line}"
rolesDark:
  primary: "{colors.structure-dark}"
  on-primary: "{colors.on-structure-dark}"
  secondary-container: "{colors.selection-dark}"
  on-secondary-container: "{colors.structure-dark}"
  tertiary: "{colors.ok-dark}"
  error: "{colors.accent-dark}"
  on-error: "{colors.on-structure-dark}"
  error-container: "{colors.accent-soft-dark}"
  on-error-container: "{colors.accent-dark}"
  background: "{colors.surface-dark}"
  surface: "{colors.surface-dark}"
  surface-container-lowest: "{colors.raised-dark}"
  on-surface: "{colors.ink-dark}"
  on-surface-variant: "{colors.muted-dark}"
  outline: "{colors.control-dark}"
  outline-variant: "{colors.line-dark}"
typography:
  body:
    fontFamily: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif'
    fontSize: "15px"
    fontWeight: 400
    lineHeight: "24px"
  small:
    fontSize: "13px"
    lineHeight: "20px"
  caption:
    fontSize: "12px"
    lineHeight: "16px"
  overline:
    fontSize: "12px"
    fontWeight: 600
    lineHeight: "16px"
    letterSpacing: "0.025em"
    textTransform: uppercase
  label:
    fontSize: "13px"
    fontWeight: 600
  action:
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.4
  control:
    fontSize: "13px"
    fontWeight: 500
    lineHeight: "20px"
  page-title:
    fontSize: "24px"
    fontWeight: 600
    lineHeight: "32px"
    letterSpacing: "-0.025em"
  section-title:
    fontSize: "17px"
    fontWeight: 600
    lineHeight: "24px"
  figure:
    fontSize: "24px"
    fontWeight: 600
    lineHeight: "32px"
  display:
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
  public-body:
    fontSize: "15px"
    lineHeight: 1.65
  editorial:
    fontFamily: "Georgia, serif"
    fontWeight: 400
  wordmark:
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-.025em"
  mono:
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace'
rounded:
  default: "4px"
  tag: "4px"
  field: "5px"
  control: "6px"
  context: "8px"
  form: "10px"
  feature: "14px"
  circle: "50%"
spacing:
  unit: "3.75px"
  gutter: "30px"
  rail: "225px"
  rail-compact: "52.5px"
  content: "1080px"
  public-content: "1220px"
  compact: "8px"
  field-gap: "10px"
  control-gap: "12px"
  action-gap: "22px"
  panel: "24px"
  section: "32px"
  onboarding-panel: "38px"
components:
  button-primary:
    material: Button:contained
    selector: '[data-part="button-primary"]'
    backgroundColor: "var(--ds-role-primary)"
    textColor: "var(--ds-role-on-primary)"
    border: "1px solid var(--ds-role-primary)"
    rounded: "{rounded.default}"
    padding: "0 7.5px"
    minHeight: "30px"
    typography: "{typography.control}"
  button-primary-hover:
    backgroundColor: "var(--ds-role-primary)"
    opacity: "0.9"
  button-primary-disabled:
    textColor: "inherit"
    opacity: "0.6"
  button-secondary:
    material: Button:outlined
    selector: '[data-part="button-secondary"]'
    backgroundColor: "var(--ds-role-surface-container-lowest)"
    textColor: "var(--ds-role-on-surface)"
    border: "1px solid var(--ds-role-outline)"
    rounded: "{rounded.default}"
    padding: "0 7.5px"
    minHeight: "30px"
    typography: "{typography.control}"
  button-secondary-hover:
    backgroundColor: "var(--ds-role-secondary-container)"
    border: "1px solid var(--ds-role-outline)"
  button-secondary-disabled:
    textColor: "inherit"
    opacity: "0.6"
  button-quiet:
    material: Button:text
    selector: '[data-part="button-quiet"]'
    textColor: "var(--ds-role-primary)"
    border: "1px solid transparent"
    rounded: "{rounded.default}"
    padding: "0 7.5px"
    minHeight: "30px"
    typography: "{typography.control}"
  button-quiet-hover:
    backgroundColor: "var(--ds-role-secondary-container)"
  button-quiet-disabled:
    textColor: "inherit"
    opacity: "0.6"
  text-link:
    material: Link
    selector: '[data-part="text-link"]'
    textColor: "var(--ds-role-primary)"
    textDecoration: underline
    textUnderlineOffset: "2px"
  text-link-small:
    material: Link
    selector: '[data-part~="text-link-small"]'
    typography: "{typography.caption}"
  text-link-quiet:
    material: Link
    selector: '[data-part~="text-link-quiet"]'
    textColor: "var(--ds-role-on-surface)"
    textDecoration: "none"
  text-link-quiet-hover:
    textColor: "var(--ds-role-primary)"
    textDecoration: underline
  control-input:
    material: none
    selector: '[data-part="control-input"]'
    backgroundColor: "var(--ds-role-surface-container-lowest)"
    textColor: "var(--ds-role-on-surface)"
    border: "1px solid var(--ds-role-outline)"
    rounded: "{rounded.default}"
    minHeight: "30px"
    typography: "{typography.small}"
    padding: "0 7.5px"
  control-input-disabled:
    opacity: "0.6"
  control-input-swatch:
    material: none
    selector: '[data-part~="control-input-swatch"]'
    padding: "1.875px"
  field-label:
    material: Typography
    selector: '[data-part="field-label"]'
    textColor: "var(--ds-role-on-surface-variant)"
    typography: "{typography.control}"
  page-header:
    material: none
    selector: '[data-part="page-header"]'
    borderBottom: "1px solid var(--ds-role-outline-variant)"
  nav-rail:
    material: none
    selector: '[data-part="nav-rail"]'
    backgroundColor: "var(--ds-role-surface-container-lowest)"
    borderRight: "1px solid var(--ds-role-outline-variant)"
  nav-link:
    material: ListItemButton
    selector: '[data-part="nav-link"]'
    textColor: "var(--ds-role-on-surface)"
    rounded: "{rounded.default}"
    minHeight: "37.5px"
    typography: "{typography.small}"
    padding: "8px 7.5px"
  nav-link-hover:
    backgroundColor: "var(--ds-role-secondary-container)"
  nav-link-selected:
    backgroundColor: "var(--ds-role-secondary-container)"
    textColor: "var(--ds-role-primary)"
    fontWeight: "600"
  nav-link-compact:
    material: ListItemButton
    selector: '[data-part~="nav-link-compact"]'
    padding: "8px 0"
  search-panel:
    material: none
    selector: '[data-part="search-panel"]'
    backgroundColor: "var(--ds-role-surface-container-lowest)"
    border: "1px solid var(--ds-role-outline-variant)"
    boxShadow: "0 1px 2px 0 var(--ds-role-outline-variant)"
  data-table:
    material: none
    selector: '[data-part="data-table"]'
    backgroundColor: "var(--ds-role-surface-container-lowest)"
    border: "1px solid var(--ds-role-outline-variant)"
  table-heading:
    material: Typography
    selector: '[data-part="table-heading"]'
    textColor: "var(--ds-role-on-surface-variant)"
    typography: "{typography.overline}"
    borderBottom: "1px solid var(--ds-role-outline-variant)"
    padding: "7.5px"
  figures:
    material: none
    selector: '[data-part="figures"]'
    backgroundColor: "var(--ds-role-surface-container-lowest)"
    border: "1px solid var(--ds-role-outline-variant)"
  panel:
    material: none
    selector: '[data-part="panel"]'
    backgroundColor: "var(--ds-role-surface-container-lowest)"
    border: "1px solid var(--ds-role-outline-variant)"
    padding: "15px"
  panel-compact:
    material: none
    selector: '[data-part~="panel-compact"]'
    padding: "7.5px 15px"
    typography: "{typography.small}"
  panel-roomy:
    material: none
    selector: '[data-part~="panel-roomy"]'
    padding: "22.5px 15px"
  panel-flush:
    material: none
    selector: '[data-part~="panel-flush"]'
    padding: "0"
  empty-state:
    material: none
    selector: '[data-part="empty-state"]'
    backgroundColor: "var(--ds-role-surface-container-lowest)"
    textColor: "var(--ds-role-on-surface-variant)"
    border: "1px dashed var(--ds-role-outline-variant)"
    padding: "15px"
  error-note:
    material: none
    selector: '[data-part="error-note"]'
    backgroundColor: "var(--ds-role-error-container)"
    border: "1px solid var(--ds-role-error)"
    padding: "7.5px 15px"
  command:
    material: none
    selector: '[data-part="command"]'
    backgroundColor: "var(--ds-role-surface-container-lowest)"
    border: "1px solid var(--ds-role-outline-variant)"
    rounded: "{rounded.default}"
    padding: "0 3.75px"
    typography: "{typography.mono}"
    fontSize: "13px"
  generated-tag:
    material: none
    selector: '[data-part="generated-tag"]'
    textColor: "var(--ds-role-on-surface-variant)"
    border: "1px solid var(--ds-role-outline)"
    padding: "0 3.75px"
    typography: "{typography.caption}"
    fontWeight: "500"
  severity-act-now:
    material: none
    selector: '[data-part="severity-act-now"]'
    backgroundColor: "var(--ds-role-error-container)"
    textColor: "var(--ds-role-error)"
    border: "1px solid var(--ds-role-error)"
    padding: "0 3.75px"
    typography: "{typography.overline}"
  severity-high:
    material: none
    selector: '[data-part="severity-high"]'
    textColor: "var(--ds-role-on-surface)"
    border: "1px solid var(--ds-role-outline)"
    padding: "0 3.75px"
    typography: "{typography.overline}"
  severity-watch:
    material: none
    selector: '[data-part="severity-watch"]'
    textColor: "var(--ds-role-on-surface-variant)"
    border: "1px solid var(--ds-role-outline-variant)"
    padding: "0 3.75px"
    typography: "{typography.overline}"
  preview-frame:
    material: none
    selector: '[data-part="preview-frame"]'
    backgroundColor: "{colors.white}"
    border: "1px solid var(--ds-role-outline-variant)"
  switch:
    material: Switch
    selector: '[data-part="switch"]'
  document-preview:
    material: none
    selector: '[data-part="document-preview"]'
    backgroundColor: "{colors.white!}"
    textColor: "{colors.ink!}"
    border: "1px solid var(--ds-role-outline-variant)"
    padding: "15px"
  public-button:
    material: Button:contained
    selector: '[data-part="public-button"]'
    backgroundColor: "{colors.bw-navy}"
    textColor: "{colors.white}"
    rounded: "{rounded.control}"
    padding: "12px 22px"
    minHeight: "48px"
    typography: "{typography.action}"
    textDecoration: "none"
  public-button-hover:
    backgroundColor: "{colors.button-hover}"
  public-button-disabled:
    opacity: "0.6"
  public-button-small:
    material: Button:contained
    selector: '[data-part="public-button-small"]'
    backgroundColor: "{colors.bw-navy}"
    textColor: "{colors.white}"
    rounded: "{rounded.control}"
    padding: "10px 18px"
    minHeight: "42px"
    typography: "{typography.action}"
    textDecoration: "none"
  public-button-small-hover:
    backgroundColor: "{colors.button-hover}"
  public-button-small-disabled:
    opacity: "0.6"
  public-button-light:
    material: Button:contained
    selector: '[data-part="public-button-light"]'
    backgroundColor: "{colors.white}"
    textColor: "{colors.bw-navy}"
    rounded: "{rounded.control}"
    padding: "12px 22px"
    minHeight: "48px"
    typography: "{typography.action}"
    textDecoration: "none"
  public-button-light-hover:
    backgroundColor: "{colors.light-hover}"
  public-button-light-disabled:
    opacity: "0.6"
  public-button-outline:
    material: Button:outlined
    selector: '[data-part="public-button-outline"]'
    textColor: "{colors.bw-navy}"
    border: "1px solid {colors.outline-border}"
    rounded: "{rounded.control}"
    padding: "12px 22px"
    minHeight: "48px"
    typography: "{typography.action}"
    textDecoration: "none"
  public-button-outline-hover:
    backgroundColor: "{colors.outline-hover}"
    border: "1px solid {colors.outline-border}"
  public-button-outline-disabled:
    opacity: "0.6"
  public-text-link:
    material: Link
    selector: '[data-part="public-text-link"]'
    textColor: "{colors.text-link}"
    typography: "{typography.action}"
    background: "none"
    border: "0"
    padding: "0"
    textDecoration: underline
    textDecorationColor: transparent
    textUnderlineOffset: "4px"
  public-text-link-hover:
    textDecorationColor: currentColor
  public-text-link-inline:
    material: Link
    selector: '[data-part~="public-text-link-inline"]'
    textColor: "inherit"
    fontSize: "11px"
    fontWeight: "400"
    textDecoration: underline
  public-field:
    material: none
    selector: '[data-part="public-field"]'
    backgroundColor: "{colors.white}"
    textColor: "{colors.bw-ink}"
    border: "1px solid {colors.control-border}"
    rounded: "{rounded.field}"
    padding: "10px 12px"
    minHeight: "46px"
    fontSize: "14px"
    fontWeight: "400"
  public-tag:
    material: none
    selector: '[data-part="public-tag"]'
    backgroundColor: "{colors.tag-surface}"
    textColor: "{colors.tag-ink}"
    rounded: "{rounded.tag}"
    padding: "3px 8px"
    fontSize: "11px"
    fontWeight: "650"
    lineHeight: "1.5"
  public-tag-priority:
    material: none
    selector: '[data-part="public-tag-priority"]'
    backgroundColor: "{colors.priority-surface}"
    textColor: "{colors.priority-ink}"
    rounded: "{rounded.tag}"
    padding: "3px 8px"
    fontSize: "11px"
    fontWeight: "650"
    lineHeight: "1.5"
  choice:
    material: none
    selector: '[data-part="choice"]'
    border: "1px solid {colors.choice-border}"
    rounded: "{rounded.control}"
    padding: "13px"
    fontSize: "13px"
  choice-selected:
    backgroundColor: "{colors.choice-selected-surface}"
    border: "1px solid {colors.choice-selected-border}"
  onboarding-panel:
    material: none
    selector: '[data-part="onboarding-panel"]'
    backgroundColor: "{colors.white}"
    border: "1px solid {colors.bw-line}"
    rounded: "{rounded.feature}"
    padding: "{spacing.onboarding-panel}"
  public-note:
    material: none
    selector: '[data-part="public-note"]'
    backgroundColor: "{colors.note-surface}"
    textColor: "{colors.note-ink}"
    rounded: "{rounded.control}"
    padding: "18px"
    fontSize: "13px"
  public-error:
    material: none
    selector: '[data-part="public-error"]'
    backgroundColor: "{colors.error-surface}"
    textColor: "{colors.error-ink}"
    rounded: "{rounded.control}"
    padding: "14px 18px"
    fontSize: "13px"
  public-notice:
    material: none
    selector: '[data-part="public-notice"]'
    backgroundColor: "{colors.notice-surface}"
    textColor: "{colors.notice-ink}"
    rounded: "{rounded.control}"
    padding: "12px 16px"
    fontSize: "13px"
  briefing-preview:
    material: Card
    selector: '[data-part="briefing-preview"]'
    backgroundColor: "{colors.white}"
    rounded: "{rounded.feature}"
    boxShadow: "0 20px 60px {colors.preview-shadow}"
    border: "0"
  plan-card:
    material: Card
    selector: '[data-part="plan-card"]'
    backgroundColor: "{colors.white}"
    border: "1px solid {colors.bw-line}"
    rounded: "{rounded.feature}"
  workspace-nav-link:
    material: ListItemButton
    selector: '[data-part="workspace-nav-link"]'
    textColor: "{colors.bw-muted}"
    rounded: "{rounded.field}"
    padding: "11px 12px"
    fontSize: "13px"
  workspace-nav-link-hover:
    backgroundColor: "{colors.nav-hover}"
  workspace-nav-link-selected:
    backgroundColor: "{colors.tag-surface}"
    textColor: "{colors.bw-navy}"
    fontWeight: "650"
  filter-tab:
    material: Button:text
    selector: '[data-part="filter-tab"]'
    textColor: "{colors.bw-muted}"
    rounded: "{rounded.field}"
    padding: "8px 12px"
    fontSize: "12px"
    fontWeight: "400"
    lineHeight: "1.65"
  filter-tab-selected:
    backgroundColor: "{colors.tab-selected}"
    textColor: "{colors.bw-navy}"
    fontWeight: "600"
  context-panel:
    material: none
    selector: '[data-part="context-panel"]'
    backgroundColor: "{colors.context-surface}"
    rounded: "{rounded.context}"
    padding: "26px"
  briefing-paper:
    material: none
    selector: '[data-part="briefing-paper"]'
    backgroundColor: "{colors.white}"
    border: "1px solid {colors.bw-line}"
    padding: "50px"
  source-monogram:
    material: none
    selector: '[data-part="source-monogram"]'
    backgroundColor: "{colors.monogram-surface}"
    textColor: "{colors.monogram-ink}"
    rounded: "{rounded.control}"
    fontSize: "13px"
    fontWeight: "650"
  brand:
    material: Link
    selector: '[data-part="brand"]'
    textColor: "{colors.bw-navy}"
    typography: "{typography.wordmark}"
    textDecoration: "none"
  brand-local:
    material: Link
    selector: '[data-part~="brand-local"]'
    textColor: "var(--ds-role-primary)"
  public-header:
    material: none
    selector: '[data-part="public-header"]'
    borderBottom: "1px solid {colors.bw-line}"
  public-footer:
    material: none
    selector: '[data-part="public-footer"]'
    textColor: "{colors.bw-muted}"
---

# Design System: Bev Watch

This document records the Bev Watch tokens, component patterns, and responsive behavior. The frontmatter above is the source the shared design framework reads: `ds sync` in `web/` turns it into the CSS variables, the Material UI theme and the component styles the pages use.

## Overview

Bev Watch extends the existing application's blue and neutral interface with a compact red beverage mark. The implemented system combines large, tightly tracked public headings with a denser workspace built from lists, restrained panels, visible labels, and source context.

This record captures the public website, five-step onboarding, browser-local preview, and the local application behind `regwatch ui`. The public surfaces explicitly use a light color scheme. The local application follows the light and dark roles in the frontmatter, which switch with the system setting.

**Key Characteristics:**

- Navy actions and selection treatments on pale blue-gray surfaces.
- System sans typography with Georgia emphasis on public headings and briefing paper.
- Thin dividers, compact tags, and modest corner radii.
- Larger public composition and compact task-oriented workspace density.

## Tokens

Colors carry Material roles for the local application: `roles` holds the light scheme and `rolesDark` the dark one, and every local component refers to a role through its `--ds-role-*` variable so it follows the system setting. The public website and preview refer to fixed `colors` only. Spacing has an explicit unit of 3.75px, the 0.25rem step at the application's 15px root size, so a spacing of 2 in a component is 7.5px. Each component names the Material UI component it renders as (`material`) and the selector that finds it in the built pages (`selector`); every rendered part carries a matching `data-part` attribute.

These components are the only source of each part's look: colors, fill, border, radius, typography, padding, shadow and opacity, with their hover, selected and disabled states. Every part renders through `Piece` in [the shared parts](web/src/components/ui.tsx), which applies its component's style, so a component edited here or in the hub changes the rendered pages after `ds sync` and a build. A part that differs from its component by more than layout names a second component as its `modifier` (for example `panel-compact`, `text-link-quiet` or `brand-local`); the modifier's style and states apply over the component's, and its name joins the element's `data-part`, which is why a modifier's selector matches with `~=`. The sx a page passes beside a part keeps only what a component cannot express: display, grid and flex layout, position, sizing, margins and overflow; breakpoint overrides; descendant rules for a part's children; transitions and the cursor. [Application Styles](web/styles/app.css) hold no component style, only the focus ring, tabular numbers, print and reduced-motion rules, all from `--ds-*` variables. The local application ships prebuilt in `regwatch/web/`, so `hub.config.json` declares `sourceGeneration`: a hub publish runs `ds sync` and the build, and its pull request carries the rebuilt pages that CI compares with a fresh build.

## Colors

### Primary

Muted navy carries primary actions, active navigation, progress markers, and the closing public section. The primary button hover color is a lighter blue. The focus token supplies a visible keyboard outline across controls.

### Secondary

The brand red belongs to the compact beverage mark. Warm priority tags distinguish “Review first” content; error and confirmation messages have separate warm and green treatments. These are contextual roles in the implementation.

### Neutral

Paper is the page background; raised white holds forms, the sidebar, and preview cards. Ink carries primary text, muted blue-gray carries supporting text, and the line color separates rows and panels. Controls use a stronger border than passive dividers.

## Typography

The body uses the system sans stack defined in the token block. Georgia supplies italic emphasis in public and onboarding headings and the company heading on exported briefing paper. There is no downloaded font; identifiers and commands use the system monospace stack.

| Role | Implemented Use |
| --- | --- |
| Display | Fluid landing heading, with explicit mobile overrides. |
| Headline | Public explanatory section heading. |
| Title | Workspace page heading. |
| Body | Local application base text. |
| Public Body | Public, onboarding, and workspace base text. |
| Label | Form labels and legends. |
| Overline | Table headings, figure labels and severity labels. |
| Editorial | Public emphasis and briefing-paper heading. |

Public display type becomes (58px) at the (800px) breakpoint and (43px) at (540px). Public section headings use (48px), then (42px) and (36px). Workspace headings reduce from (30px) to (27px) at the narrowest breakpoint. Metadata and tags use (10px) through (13px); descriptive workspace text uses (13px) or (14px). Paragraphs have a shared maximum of (72ch), with a narrower landing introduction at (43ch). Tables and numeric utility text use tabular numerals.

## Layout

The public container is centered with a maximum width of (1220px) and a viewport subtraction of (96px). That subtraction becomes (64px) below (1100px), then (40px) below (540px). The landing introduction uses two columns at (1.1fr 1fr) with an (8%) gap; explanatory sections use two equal columns with a (12%) gap. They become one column at (800px).

Onboarding pairs a progress column with a form at (.85fr 1.3fr) and a (10%) gap. At (800px), progress becomes a horizontal row of numbered circles and the form follows it. Two-column choice groups and summary rows become single columns at (540px).

The preview workspace uses a (240px) sticky sidebar and a flexible content column. Main content is capped at (1300px) with (30px 42px) padding. At (800px), the sidebar becomes a top section and navigation scrolls horizontally; main padding becomes (24px). At (540px), inline main padding becomes (20px), heading actions stack, and portfolio and source rows wrap. The overview's (1.5fr 1fr) grid becomes one column at (1100px). The local shell compacts its navigation rail at (767px) and uses the breakpoints (640px), (768px), (1024px) and (1280px).

## Elevation & Depth

Most surfaces use flat fills, borders, and horizontal rules. The landing briefing preview is the exception, with the single feature shadow recorded in its component. The onboarding form and pricing panel use white fill and a line border without a shadow.

Button background transitions use (.18s ease-out). The global reduced-motion query removes transitions. There are no entrance animations in the documented surfaces.

## Shapes

Tags have the smallest rounded corners; fields and navigation use slightly larger corners; buttons, choices, and notices use the control radius. Context panels use the context radius, product forms use the form radius, and onboarding, pricing, and landing preview panels use the feature radius. Progress indicators and the preview status dot are circles. The red brand mark is a (32px) square with a (9px) corner radius and a white line symbol.

## Components

### Buttons

Primary buttons pair navy with white text, a minimum height of (48px), (14px) semibold type, and a (12px) internal gap. Small buttons use a minimum height of (42px); the narrow header variant becomes (40px) at (540px). The light variant is used against the navy closing section. Outline buttons have a transparent background and a (1px) border. Disabled primary and outline buttons use (.6) opacity and a not-allowed cursor. Text actions use a blue label and an underline that appears on hover. The local application uses compact (30px) buttons in three tones: primary, secondary and quiet.

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
- **Don't** apply the local application's dark roles to the explicitly light public and preview surfaces.
- **Don't** turn the landing preview's shadow into the default treatment for every workspace panel.
- **Don't** present sample regulatory content as current findings.

Source evidence: [Product](PRODUCT.md), [Application Styles](web/styles/app.css), [Brand Components](web/src/components/brand.tsx), [Public Landing](web/src/views/public-home.tsx), [Onboarding](web/pages/onboarding.tsx), [Preview Workspace](web/pages/workspace.tsx), and [Local Shell](web/src/components/shell.tsx).
