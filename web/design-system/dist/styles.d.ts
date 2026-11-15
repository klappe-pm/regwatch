import { DesignSpec, SpecComponent } from './types.js';

type Sx = Record<string, unknown>;
/** The typography properties of a DESIGN.md type style that Material UI understands. */
declare function typeStyle(t: Record<string, string | number>): Record<string, string | number>;
/** A component spec's resolved props -> a style object Material UI understands, nested rules included. */
declare function componentSx(c: Pick<SpecComponent, 'style'>): Sx;
/** Where each DESIGN.md state component (`<name>-hover`, `<name>-selected` and so on) applies. */
declare const STATE_SELECTOR: Record<string, string>;
/**
 * The disabled style of a DESIGN.md component. A `<name>-disabled` component in DESIGN.md wins property by property.
 * Interactive Material UI components (Button, ToggleButton, Chip and so on) otherwise get the Material default built
 * from role variables, so Material UI's own disabled greys never override the design. Modifier components
 * (`modifier: true`) get only their explicit `-disabled` state: the base part they combine with owns the default.
 * Null when there is nothing to emit.
 */
declare function disabledSx(spec: Pick<DesignSpec, 'roles' | 'components'>, name: string): Sx | null;
/**
 * The sx for a DESIGN.md component, as Part applies it: its base style plus its states. The disabled state comes last
 * so it wins over hover and selected. Empty when DESIGN.md has no such component.
 */
declare function partSx(spec: Pick<DesignSpec, 'roles' | 'components'>, name: string): Sx;
/** Merge `data-part` tokens: the part names first, then any the caller passed, without duplicates. */
declare function partTokens(names: string | string[], existing?: unknown): string;
/**
 * Props that tie any element to one or more DESIGN.md components: their styles merged in order, then `extra` (layout),
 * and the `data-part` attribute the hub's usage scan matches (`[data-part~="name"]`). Spread onto any Material UI
 * component: `<Chip {...partProps(spec, 'badge', { ml: 1 })} />`. A modifier part goes after its base:
 * `partProps(spec, ['button-default', 'button-small'])`.
 */
declare function partProps(spec: Pick<DesignSpec, 'roles' | 'components'>, names: string | string[], ...extra: (Sx | false | null | undefined)[]): {
    'data-part': string;
    sx: Sx[];
};
interface ScopedTokenOptions {
    /** Id of the scope element (the provider's `scope`). */
    scope: string;
    /** Where the color-scheme attribute is: on the scope element ('scope', the default) or on an element around it ('root'). */
    colorSchemeNode?: 'scope' | 'root';
    /** The color-scheme attribute (default 'data-theme'), or a full selector with %s for the scheme name. */
    attribute?: string;
}
/**
 * The token variables (design/ds.css) for one scoped provider: defined on `#<scope>`, with the dark roles switched by
 * the color-scheme attribute where the provider puts it. What the scoped provider injects; hosts that load styles
 * themselves (an adopted style sheet, a plugin's styles.css) can write it out with this.
 */
declare function scopedTokenCss(spec: DesignSpec, { scope, colorSchemeNode, attribute }: ScopedTokenOptions): string;

export { STATE_SELECTOR, type ScopedTokenOptions, type Sx, componentSx, disabledSx, partProps, partSx, partTokens, scopedTokenCss, typeStyle };
