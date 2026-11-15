import * as react from 'react';
import { ReactNode, ElementType } from 'react';
import { BoxProps } from '@mui/material/Box';

declare function Page({ children, maxWidth, ...rest }: {
    children: ReactNode;
    maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | false;
} & BoxProps): react.JSX.Element;
declare function Section({ children, tone, spacing, ...rest }: {
    children: ReactNode;
    tone?: 'surface' | 'primary' | 'secondary';
    spacing?: string;
} & BoxProps): react.JSX.Element;
type NavLink = {
    href: string;
    label: string;
    current?: boolean;
};
declare function SiteHeader({ brand, brandHref, links, action, linkComponent, navLabel, skipLabel }: {
    brand: ReactNode;
    brandHref?: string;
    links: NavLink[];
    action?: ReactNode;
    linkComponent?: ElementType;
    navLabel?: string;
    skipLabel?: string;
}): react.JSX.Element;
declare function SiteFooter({ children, links, linkComponent }: {
    children?: ReactNode;
    links?: NavLink[];
    linkComponent?: ElementType;
}): react.JSX.Element;

export { type NavLink, Page, Section, SiteFooter, SiteHeader };
