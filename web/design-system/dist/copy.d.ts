import * as react from 'react';
import { ReactNode } from 'react';
import { CopyMap, OnMissing, Translate } from './types.js';

declare function createCopy(copy: CopyMap, opts?: { onMissing?: OnMissing }): Translate

/** `copy` is either the copy map or a translate function already built with createCopy. */
declare function CopyProvider({ copy, children, onMissing }: {
    copy: CopyMap | Translate;
    children: ReactNode;
    onMissing?: OnMissing;
}): react.JSX.Element;
/** The translate function of the nearest provider. Throws when there is none. */
declare function useCopy(): Translate;
declare function Lines({ text }: {
    text: string;
}): react.JSX.Element;
/**
 * <T k="pages.home.hero.title" /> renders one string of copy. Without a provider it renders `fallback` when one is
 * given, and throws otherwise.
 */
declare function T({ k, vars, annotate, fallback }: {
    k: string;
    vars?: Record<string, string | number>;
    annotate?: boolean;
    fallback?: ReactNode;
}): react.JSX.Element;

export { CopyProvider, Lines, OnMissing, T, Translate, createCopy, useCopy };
