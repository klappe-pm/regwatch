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

## Commercial Launch Requirements

Subscription pricing, payment provider, account service, hosted storage, and monitoring jobs remain undecided. Connect and verify those services before offering a paid subscription. A client-side premium flag or checkout return URL must never grant subscription access.

## Verification

```bash
npm --prefix "$HOME/projects/regwatch/web" test
npm --prefix "$HOME/projects/regwatch/web" run typecheck
```

Build checks validate static routes and TypeScript. Frontend tests cover workspace validation, persistence failures, synthetic briefing labels, and import/undo integrity. Desktop, mobile, keyboard, and full onboarding interaction checks require an enabled browser and remain separate from build success.
