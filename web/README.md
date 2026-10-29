# Bev Watch Website

Bev Watch is the beverage-focused public website and browser-local preview built around the Regwatch engine. The engine retains its package name, CLI, authenticated loopback server, and existing API contracts.

## Public Build

The public build sets a non-secret display mode at compile time and writes only the website routes into `web/site/`. It does not replace the Python package's built local UI.

```bash
npm --prefix "$HOME/projects/regwatch/web" ci
npm --prefix "$HOME/projects/regwatch/web" run build:site
```

Deploy with `web/` as the project root. `vercel.json` selects a static deployment and the `site` output directory. Public routes are `/`, `/onboarding/`, `/workspace/`, `/pricing/`, and `/privacy/`. The website publishes no `/api/*` handlers or local engine routes.

## Local Engine Build

The existing build keeps the local overview at `/` and copies the static export into the Python package. Run this before committing a local UI change.

```bash
npm --prefix "$HOME/projects/regwatch/web" run build
```

## Preview Data Contract

The public workspace uses the versioned `Workspace` schema in `src/lib/bev-watch.ts`, persisted in browser local storage. Onboarding, portfolio editing, source preferences, review state, backup import/export, and sample briefing export work locally in the browser. Imports validate the schema before replacing a workspace, and undo preserves an imported product's identity. Ordinary workspace and onboarding saves compare their loaded snapshot with stored data and prompt a reload if another tab saved changes. Import and confirmed clearing remain deliberate replacement operations. Browser storage is a preview mechanism, not a transactional database or device synchronization service.

Regulatory examples are synthetic and explicitly labeled. Source links navigate to official websites; they do not verify or substantiate the invented updates. The preview performs no scheduled monitoring and sends no emails. It does not create accounts, synchronize data between devices, collect payments, or grant paid entitlements.

## Managed Content and Design

Editable public text lives in [content](content/pages/landing.md), with page documents under `content/pages/` and shared documents under `content/global/`. Each bullet has a stable key and its visible value. The generated [copy module](src/lib/copy.generated.ts) exposes typed `t()` keys, and the [text component](src/components/copy.tsx) puts those keys on rendered elements for in-page review. Category, market, and cadence labels are editable while their stored workspace values remain stable.

The fenced YAML map in [DESIGN.md](../DESIGN.md) owns colors, typography, spacing, radii, and component properties. The generated [token snapshot](design/tokens.json), [token stylesheet](design/tokens.css), and [component stylesheet](design/components.css) drive the public pages, onboarding, and workspace. Existing `--bw-*` color variables alias the `--ds-color-*` tokens. Component metadata uses the canonical names in the design map, such as `button-primary`, `field`, and `tag`.

Regenerate the snapshots after a content or design edit. Both build modes, development startup, and type checking run this command automatically. The committed snapshots and build script need no content service, credentials, private package, or build-time network request.

```bash
npm --prefix /path/to/regwatch/web run managed
```

Check that committed snapshots match their editable sources without changing a file:

```bash
npm --prefix /path/to/regwatch/web run managed:check
```

## Commercial Launch Requirements

Subscription pricing, payment provider, account service, hosted storage, and monitoring jobs remain undecided. Connect and verify those services before offering a paid subscription. A client-side premium flag or checkout return URL must never grant subscription access.

## Verification

```bash
npm --prefix "$HOME/projects/regwatch/web" test
npm --prefix "$HOME/projects/regwatch/web" run typecheck
```

Build checks validate static routes and TypeScript. Frontend tests cover workspace validation, persistence failures, synthetic briefing labels, and import/undo integrity. Desktop, mobile, keyboard, and full onboarding interaction checks require an enabled browser and remain separate from build success.
