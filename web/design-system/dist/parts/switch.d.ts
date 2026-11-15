import * as react from 'react';
import { PartProps, PartRenderer } from './core.js';
import '@mui/material/styles';
import '../types.js';

/** `material: Switch`. With a label it renders inside a FormControlLabel; `unlabeled` renders the bare control. */
declare const switchControl: PartRenderer;
declare const SwitchPart: ({ name, children, labelKey, sx, unlabeled, modifiers, ...rest }: PartProps) => react.JSX.Element;

export { SwitchPart, switchControl };
