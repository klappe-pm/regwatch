# Change the Web App

This guide changes the pages behind `regwatch ui`, builds them, and commits the build so the change ships. The pages are a Next.js app in `web/`, styled with Tailwind CSS and exported as static files into `regwatch/web/`, which is package data. Users install the built files with the package and never need Node; you need Node 22 or newer to change them.

## Set Up

Install the exact dependency versions that `web/package-lock.json` pins. Install scripts are skipped; the build does not need them.

```bash
npm --prefix ~/regwatch/web ci --ignore-scripts
```

## Work on a Page

Each page is one folder under `web/src/app/`, and the shared parts are under `web/src/components/` and `web/src/lib/`. The data comes from the JSON interface in `regwatch/webapi.py`, and the shapes the pages expect are in `web/src/lib/types.ts`; change the two together.

For live editing, start the server against the examples in one terminal, and in another run the build after each change, then reload the browser.

```bash
regwatch --config ~/regwatch/examples/regwatch.toml ui
```

```bash
npm --prefix ~/regwatch/web run build
```

Follow the design rules the existing pages follow:

- Colours come from the CSS variables in `web/src/app/globals.css`, defined for both light and dark mode. Do not add a colour in a component. Light blue marks structure and selection; the warm accent marks priority only (act now, suspicious, failing).
- No text is smaller than 12 pixels, and body text is 15. Spacing follows an 8 pixel grid. Tables use tabular numerals.
- Headings are Title Case; labels say what a control does in plain words.
- Icons come from Material Symbols Outlined through `web/scripts/make-icons.mjs`, which copies the paths of the icons in its list into the build. Add a name to that list to use another icon.
- Nothing loads from another origin: no remote font, script, image or style. The server's content security policy blocks any such load, and a test fails on a remote address in the build.
- Every control is reachable from the keyboard and shows a visible focus ring.

## Build and Commit

Run the build script. It installs from the lockfile and replaces `regwatch/web/` with a fresh export.

```bash
~/regwatch/scripts/build-web.sh
```

The build is reproducible: the same source gives the same files. Commit the source change and the changed files under `regwatch/web/` together. The release workflow builds the pages again from the lockfile and fails when the result differs from what is committed, so a stale build cannot be released.

Then run the tests, which check that the build has every page and refers to no other origin; see [run the tests](run-the-tests.md).

## Change a Dependency

Pin every version exactly in `web/package.json`, choose a release that is at least two weeks old, and commit the updated `web/package-lock.json`. A test fails on a range such as `^15.5.0` and on a lock entry without an integrity hash.
