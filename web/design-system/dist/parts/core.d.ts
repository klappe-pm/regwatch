import * as react from 'react';
import { ReactNode, ElementType } from 'react';
import { SxProps, Theme } from '@mui/material/styles';
import { DesignSpec } from '../types.js';

type PartProps = {
    name: string;
    children?: ReactNode;
    /** Copy key for the label; defaults to the part's `label` in DESIGN.md. */
    labelKey?: string;
    sx?: SxProps<Theme>;
    component?: ElementType;
    /** Switch and Checkbox parts: render the control alone, with no FormControlLabel (label it with aria-labelledby). */
    unlabeled?: boolean;
    /**
     * Modifier parts (DESIGN.md components with `modifier: true`, such as `button-small`) to combine with this one. Their
     * styles follow the part's own and their names join `data-part`.
     */
    modifiers?: string[];
    /**
     * Button, IconButton and ButtonBase parts render `type="button"` unless you pass `type="submit"` (or `"reset"`), so a
     * part inside a form never submits it by accident. Ignored when the part renders a link (`href`) or another element.
     * Input parts (TextField, InputBase) take any input type, such as `"email"` or `"search"`.
     */
    type?: 'button' | 'submit' | 'reset' | (string & {});
    [prop: string]: unknown;
};
/** What a renderer receives: the props to spread (data attributes and sx included) and the resolved label. */
interface PartRenderContext {
    /** The DESIGN.md component name. */
    name: string;
    /** Every prop for the Material UI component: the caller's, `data-part`, `data-component`, `sx` and `type`. */
    props: Record<string, any>;
    /** children, else the label from copy (labelKey or DESIGN.md `label`), else null. */
    label: ReactNode;
    children: ReactNode;
    /** The copy key the label came from, when it did. */
    copyKey: string | null;
    /** The label from copy (labelKey or DESIGN.md `label`) even when there are children, for an accessible name. */
    copyText(): string | null;
    /** The variant after the colon in `material: Button:outlined`. */
    variant?: string;
    unlabeled: boolean;
    spec: DesignSpec;
}
/** Renders the Material UI component a DESIGN.md `material:` names (`Button`, `TableCell` and so on). */
interface PartRenderer {
    material: string;
    render(ctx: PartRenderContext): ReactNode;
}
/** Makes renderers available to every Part below, on top of any registered further up. */
declare function PartRegistry({ parts, children }: {
    parts: readonly PartRenderer[];
    children: ReactNode;
}): react.JSX.Element;
/**
 * A Part component that renders the given Material UI components, plus any registered with PartRegistry. A part whose
 * component has no renderer renders a Box (with a warning in development).
 */
declare function createPart(renderers: readonly PartRenderer[]): ({ name, children, labelKey, sx, unlabeled, modifiers, ...rest }: PartProps) => react.JSX.Element;
declare function controlProps({ inputProps, ...props }: Record<string, any>): {
    [x: string]: any;
};
/** The label as an accessible name, when it is plain text and the caller set none. */
declare const textLabel: (label: ReactNode) => string | undefined;

export { type PartProps, PartRegistry, type PartRenderContext, type PartRenderer, controlProps, createPart, textLabel };
