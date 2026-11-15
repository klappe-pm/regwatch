import { SxProps, Theme } from '@mui/material/styles';
import { Sx } from '../styles.js';
import '../types.js';

/**
 * `{ 'data-part', sx }` for one or more DESIGN.md components, to spread on any Material UI component:
 * `<Chip {...useParts(['badge', 'badge-review'], { ml: 1 })} />`. Modifier parts combine the same way:
 * `useParts(['button-default', 'button-small'])`.
 */
declare function useParts(names: string | string[], ...extra: (Sx | false | null | undefined)[]): {
    "data-part": string;
    sx: SxProps<Theme>;
};

export { useParts };
