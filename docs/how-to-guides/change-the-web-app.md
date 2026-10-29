# Change the Web App

This guide changes the pages behind `regwatch ui` and the public Bev Watch website, builds them, and commits the build so the change ships. The pages are a Next.js app in `web/` built on Material UI and the shared design and content framework (`@klappe/design-system`), and exported as static files into `regwatch/web/`, which is package data. Users install the built files with the package and never need Node; you need Node 22 or newer to change them.

## Set Up

Install the exact dependency versions that `web/package-lock.json` pins. Install scripts are skipped; the build does not need them.

```bash
npm --prefix ~/regwatch/web ci --include=dev --ignore-scripts
```

## Where Things Live

- Each page is a file under `web/pages/` (the Pages Router), and the shared parts are under `web/src/components/`, `web/src/views/` and `web/src/lib/`. The data comes from the JSON interface in `regwatch/webapi.py`, and the shapes the pages expect are in `web/src/lib/types.ts`; change the two together.
- Every word a page shows comes from the copy documents in `docs/content-management-system/`: one document per page under `pages/` and the shared words under `global/`. A document lists groups, each a second level heading that names the group in backticks, and under each group its keys, each a list line that names the key in backticks and gives the text after a colon. Code looks a word up by its key with `t("pages.changes.header.title")`, a page's `p("header.title")` helper, or `<T k="..." />`, all built with `createCopy(..., { onMissing: "throw" })`, so a missing key fails the build.
- Colours, type, spacing, corner radii and component styles come from the frontmatter of `DESIGN.md`. The local application uses the Material roles (`roles` and `rolesDark`), so it follows the system's light or dark setting; the public pages use the fixed `colors` and stay light.
- `ds sync`, run from `web/`, writes `web/design/`: `spec.json` (the design spec the theme and the parts are built from), `ds.css` (the `--ds-*` variables), `tailwind.css` and `copy.json`. Commit them with the change; `ds check` fails when they are stale.

For live editing, start the server against the examples in one terminal, and in another run the build after each change, then reload the browser.

```bash
regwatch --config ~/regwatch/examples/regwatch.toml ui
```

```bash
npm --prefix ~/regwatch/web run build
```

To edit only the public website, `npm --prefix ~/regwatch/web run dev` serves the pages with hot reload; set `NEXT_PUBLIC_BEV_WATCH_MODE=hosted-preview` to see the landing page at `/`.

Follow the design rules the existing pages follow:

- Build every part from Material UI. A part that DESIGN.md describes renders through `Piece` (the design system's `Part`, tagged with `data-part` so the hub finds it in the built pages); add a component to DESIGN.md with `material:` and `selector: '[data-part="name"]'` for a new one.
- Colours come only from `var(--ds-*)` variables and the theme. Do not write a colour in a component; `ds lint --strict` fails on one. Light blue marks structure and selection; the warm accent marks priority only (act now, suspicious, failing).
- Do not write text in a component; add it to the copy document and look it up. `ds lint --strict` fails on literal text in JSX.
- No text is smaller than 12 pixels, and body text is 15. Spacing is a multiple of the 3.75 pixel unit in DESIGN.md. Tables use tabular numerals.
- Headings are Title Case; labels say what a control does in plain words. A test checks the headings through their copy keys.
- Icons come from Material Symbols Outlined through `web/scripts/make-icons.mjs`, which copies the paths of the icons in its list into the build. Add a name to that list to use another icon.
- Nothing loads from another origin: no remote font, script, image or style. The server's content security policy blocks any such load, and a test fails on a remote address in the build.
- No inline style and no inline script. The server sends `style-src 'self'`; Material UI's styles are written into constructed style sheets in the browser (`web/src/emotion.ts`) and into style sheet files at build time (`web/scripts/postbuild.mjs`), which fails the build on an inline style or script.
- Every control is reachable from the keyboard and shows a visible focus ring.

Run the checks before you commit: the generated files are current, no colour or text is hard coded, and the types check.

```bash
npm --prefix ~/regwatch/web run check
```

## Test Page Logic

Logic that decides what a page shows, such as how the Sources page lays out the catalogue, lives in plain modules under `web/src/lib/` that import nothing from React or the `@/` alias, so Node can load them directly. Their tests are in `web/tests/`, one `*.test.mjs` file per module, and run with Node's built-in test runner, which strips the TypeScript types itself (Node 22.18 or newer). `web/tests/copy.test.mjs` checks that every copy key the pages use exists.

```bash
npm --prefix ~/regwatch/web test
```

The Python suite runs the same tests through `tests/test_web_logic.py` when such a Node and the web dependencies are present, and skips them otherwise.

After a build, two more suites check the exports: `test:build` reads the built files (every page, link and style sheet resolves, no copy key shows, the parts carry their `data-part`), and `test:browser` opens every page in Chromium under the server's policy, in light and dark mode.

```bash
npm --prefix ~/regwatch/web run build:site
npm --prefix ~/regwatch/web run test:build
npm --prefix ~/regwatch/web run test:browser
```

## Build and Commit

Run the build script. It installs from the lockfile and replaces `regwatch/web/` with a fresh export.

```bash
~/regwatch/scripts/build-web.sh
```

The build is reproducible: the same source gives the same files. Commit the source change and the changed files under `regwatch/web/` together. The `web` workflow on each pull request and the release workflow build the pages again from the lockfile and fail when the result differs from what is committed, so a stale build cannot be released. When only the workflow's build differs, take its `web-build` artifact and commit that.

Then run the tests, which check that the build has every page and refers to no other origin; see [run the tests](run-the-tests.md).

## Change a Dependency

Pin every version exactly in `web/package.json`, choose a release that is at least two weeks old, and commit the updated `web/package-lock.json`. A test fails on a range such as `^15.5.0` and on a lock entry without an integrity hash (a package bundled inside another is covered by its parent's hash). The shared design package is vendored as a tarball in `web/vendor/` and named with `file:vendor/<tarball>`; to update it, copy the new release's tarball there, change the name in `web/package.json`, reinstall, and run `npm run sync`.

Check the lockfile against the published advisories before you commit, and keep it clean:

```bash
npm --prefix ~/regwatch/web audit --package-lock-only
```

When a fix exists only in a release newer than two weeks, take that release and say why in the commit. When a package you depend on pins a vulnerable copy of another package, pin a fixed copy under `overrides` in `web/package.json`, exactly as for any other version; `next` pins its own `postcss` this way. A test checks that no copy of `next` or `postcss` in the lockfile is older than the release that fixed the advisories found so far, so add a package to `FIXED_IN` in `tests/test_web_build.py` when you fix another.
