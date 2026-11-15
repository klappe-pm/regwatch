import * as react from 'react';
export { partProps, partSx } from '../styles.js';
export { useParts } from '../parts/use-parts.js';
import { PartProps } from '../parts/core.js';
export { PartRegistry, PartRenderContext, PartRenderer, createPart } from '../parts/core.js';
import '../types.js';
import '@mui/material/styles';

declare const Part: ({ name, children, labelKey, sx, unlabeled, modifiers, ...rest }: PartProps) => react.JSX.Element;

export { Part, PartProps };
