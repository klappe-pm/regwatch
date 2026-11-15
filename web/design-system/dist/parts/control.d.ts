import { ComponentType } from 'react';
import { PartRenderer } from './core.js';
import '@mui/material/styles';
import '../types.js';

declare function controlRenderer(material: 'Switch' | 'Checkbox', Control: ComponentType<any>): PartRenderer;

export { controlRenderer };
