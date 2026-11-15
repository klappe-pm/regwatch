import * as react from 'react';
import { PartProps, PartRenderer } from './core.js';
import '@mui/material/styles';
import '../types.js';

declare const textField: PartRenderer;
declare const TextFieldPart: ({ name, children, labelKey, sx, unlabeled, modifiers, ...rest }: PartProps) => react.JSX.Element;

export { TextFieldPart, textField };
