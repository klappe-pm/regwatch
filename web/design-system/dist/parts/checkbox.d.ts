import * as react from 'react';
import { PartProps, PartRenderer } from './core.js';
import '@mui/material/styles';
import '../types.js';

/** `material: Checkbox`. With a label it renders inside a FormControlLabel; `unlabeled` renders the bare control. */
declare const checkbox: PartRenderer;
declare const CheckboxPart: ({ name, children, labelKey, sx, unlabeled, modifiers, ...rest }: PartProps) => react.JSX.Element;

export { CheckboxPart, checkbox };
