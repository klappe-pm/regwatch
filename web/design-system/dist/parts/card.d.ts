import * as react from 'react';
import { PartProps, PartRenderer } from './core.js';
import '@mui/material/styles';
import '../types.js';

/** `material: Card` (outlined) or `Card:elevation`. Renders its children. */
declare const card: PartRenderer;
declare const CardPart: ({ name, children, labelKey, sx, unlabeled, modifiers, ...rest }: PartProps) => react.JSX.Element;

export { CardPart, card };
