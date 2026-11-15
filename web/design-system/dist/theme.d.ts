/// <reference path="../types/typography.d.ts" />
import { ThemeOptions, Theme } from '@mui/material/styles';
import { DesignSpec } from './types.js';
export { componentSx } from './styles.js';

declare function spacingUnit(spec: Pick<DesignSpec, 'spacing'> & {
    spacingUnit?: string | null;
}): number;
interface DesignThemeScope {
    /** Render the theme variables on this selector (a scoped preview, `#scope`) instead of :root. */
    rootSelector?: string;
    /** Prefix of the Material UI variables when scoped. Default 'ds-mui'. */
    cssVarPrefix?: string;
    /** Where the dark palette switches: an attribute name (default 'data-theme') or a selector with %s. */
    colorSchemeSelector?: string;
}
declare function createDesignTheme(spec: DesignSpec, overrides?: ThemeOptions, scope?: DesignThemeScope): Theme;

export { type DesignThemeScope, createDesignTheme, spacingUnit };
