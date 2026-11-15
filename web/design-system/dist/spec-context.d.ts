import * as react from 'react';
import { DesignSpec } from './types.js';

declare const SpecContext: react.Context<DesignSpec | null>;
/**
 * The spec of the nearest DesignSystemProvider. `who` names the caller in the error (for example `<Part name="x">`).
 */
declare function useDesignSpec(who?: string): DesignSpec;

export { SpecContext, useDesignSpec };
