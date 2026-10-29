// The design spec generated from DESIGN.md (design/spec.json, written by `ds sync`) and the theme
// options the pages add to it.
import type { DesignSpec } from "@klappe/design-system";
import type { ThemeOptions } from "@mui/material/styles";

import spec from "../design/spec.json";

export const designSpec = spec as unknown as DesignSpec;

/**
 * The spec the Material UI theme is built from. Its roles point at the --ds-role-* variables of
 * design/ds.css, which switch to the dark roles with the system setting, so the palette follows
 * dark mode without script and without a flash of the light scheme. The public pages set
 * data-theme="light" on <html>, which keeps those variables light.
 */
export const themeSpec: DesignSpec = {
  ...designSpec,
  roles: Object.fromEntries(
    Object.entries(designSpec.roles).map(([role, value]) => [role, `var(--ds-role-${role}, ${value})`]),
  ),
  rolesDark: null,
};

/** Breakpoints the layout was written for (640, 768, 1024 and 1280 pixels). */
export const themeOptions: ThemeOptions = {
  cssVariables: { colorSchemeSelector: "media", nativeColor: true },
  breakpoints: { values: { xs: 0, sm: 640, md: 768, lg: 1024, xl: 1280 } },
  components: {
    MuiButtonBase: { defaultProps: { disableRipple: true } },
  },
};
