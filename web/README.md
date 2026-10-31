# Bev Watch Website

Bev Watch is the beverage-focused public website and browser-local preview built around the Regwatch engine. The engine retains its package name, CLI, authenticated loopback server, and existing API contracts.

## How It Is Built

The pages are a Next.js app (Pages Router, webpack, static export) built from Material UI and the shared design and content framework `@klappe/design-system`, vendored in `vendor/`.

- Design: the frontmatter of the repository's `DESIGN.md` holds the colours with their Material roles, type, spacing, corner radii and components. `ds sync` writes `design/` from it (`spec.json`, `ds.css`, `tailwind.css`); the theme and every part are built from those files.
- Copy: every visible string is in a copy document under `docs/content-management-system/` (`pages/` per page, `global/` for shared words). `ds sync` compiles them to `design/copy.json`, and the pages look words up through `createCopy(..., { onMissing: "throw" })`, `T` and `Lines`.
- `ds.config.json` sets where `ds` reads and writes; run `ds` from this folder (`npm run sync`, and `npm run check` for the checks).
- Content security: the local server sends `style-src 'self'` and allows inline scripts only by hash. `createCspEmotionCache` from `@klappe/design-system/emotion` writes Material UI's styles into constructed style sheets in the browser, and `ds csp out` moves the styles rendered at build time into style sheet files and fails on any inline style or script.

## Public Build

The public build sets a non-secret display mode at compile time and writes only the website routes into `web/dist/`. It does not replace the Python package's built local UI.

```bash
npm --prefix "$HOME/projects/regwatch/web" ci --include=dev
npm --prefix "$HOME/projects/regwatch/web" run build:site
```

Deploy with `web/` as the project root. `vercel.json` selects a static deployment and the `dist` output directory. Public routes are `/`, `/onboarding/`, `/workspace/`, `/pricing/`, and `/privacy/`. The website publishes no `/api/*` handlers or local engine routes.

## Local Engine Build

The existing build keeps the local overview at `/` and copies the static export into the Python package. Run this before committing a local UI change.

```bash
npm --prefix "$HOME/projects/regwatch/web" run build
```

## Preview Data Contract

The public workspace uses the versioned `Workspace` schema in `src/lib/bev-watch.ts`, persisted in browser local storage. Onboarding, portfolio editing, source preferences, review state, backup import/export, and sample briefing export work locally in the browser. Imports validate the schema before replacing a workspace, and undo preserves an imported product's identity. Ordinary workspace and onboarding saves compare their loaded snapshot with stored data and prompt a reload if another tab saved changes. Import and confirmed clearing remain deliberate replacement operations. Browser storage is a preview mechanism, not a transactional database or device synchronization service.

Regulatory examples are synthetic and explicitly labeled. Source links navigate to official websites; they do not verify or substantiate the invented updates. The preview performs no scheduled monitoring and sends no emails. It does not create accounts, synchronize data between devices, collect payments, or grant paid entitlements.

## Managed Content and Design

Category, market, and cadence labels are editable copy while their stored workspace values remain stable. After a copy or design edit, `npm run sync` regenerates `design/`; `npm run check` fails when the committed files are stale. `hub.config.json` and `product-feedback.config.json` at the repository root point the hub and the review workspace at `DESIGN.md` and `docs/content-management-system/`, and a hub publish rebuilds `regwatch/web/` with them.

## Commercial Launch Requirements

Subscription pricing, payment provider, account service, hosted storage, and monitoring jobs remain undecided. Connect and verify those services before offering a paid subscription. A client-side premium flag or checkout return URL must never grant subscription access.

## Verification

```bash
npm --prefix "$HOME/projects/regwatch/web" run check
npm --prefix "$HOME/projects/regwatch/web" test
npm --prefix "$HOME/projects/regwatch/web" run build
npm --prefix "$HOME/projects/regwatch/web" run build:site
npm --prefix "$HOME/projects/regwatch/web" run test:build
npm --prefix "$HOME/projects/regwatch/web" run test:browser
```

`check` confirms the generated design and copy files are current, finds no hard-coded colour or text, and checks the types. The logic tests cover workspace validation, persistence failures, synthetic briefing labels, import/undo integrity, and that every copy key the pages use exists. The export tests check every page, link and style sheet of both builds, and the browser tests open every page in Chromium under the local server's content security policy, in light and dark mode, and walk through onboarding, the review queue and the navigation rail.
