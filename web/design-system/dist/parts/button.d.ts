import * as react from 'react';
import { PartProps, PartRenderer } from './core.js';
import '@mui/material/styles';
import '../types.js';

/** `material: Button` (or `Button:contained`, `Button:outlined`, `Button:text`). Renders type="button" unless asked. */
declare const button: PartRenderer;
declare const ButtonPart: ({ name, children, labelKey, sx, unlabeled, modifiers, ...rest }: PartProps) => react.JSX.Element;

export { ButtonPart, button };
