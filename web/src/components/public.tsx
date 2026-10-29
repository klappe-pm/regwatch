// The public website's frame and its shared parts: the page, container, header, footer, buttons,
// links and tags. The public surfaces stay light: they use the fixed --ds-color-* tokens.
import { T } from "@klappe/design-system";
import Box, { type BoxProps } from "@mui/material/Box";
import InputBase, { type InputBaseProps } from "@mui/material/InputBase";
import NativeSelect from "@mui/material/NativeSelect";
import Stack from "@mui/material/Stack";
import type { SxProps, Theme } from "@mui/material/styles";
import Head from "next/head";
import NextLink from "next/link";
import type { ReactNode } from "react";

import { PLAN_FEATURES } from "@/lib/bev-watch";
import type { IconName } from "@/lib/icons.generated";
import { t } from "@/lib/text";

import { Brand } from "./brand";
import { Icon, Piece } from "./ui";

export const c = (name: string) => `var(--ds-color-${name})`;

const merge = (base: SxProps<Theme>, sx?: SxProps<Theme>): SxProps<Theme> =>
  [base, ...(Array.isArray(sx) ? sx : sx ? [sx] : [])] as SxProps<Theme>;

/** The title, description and robots line of a page. */
export function Meta({ title, index = true }: { title?: string; index?: boolean }) {
  const full = title ? t("global.public.meta.title-template", { title }) : t("global.public.meta.title");
  return (
    <Head>
      <title>{full}</title>
      <meta name="description" content={t("global.public.meta.description")} />
      <meta name="robots" content={index ? "index, follow" : "noindex, nofollow"} />
    </Head>
  );
}

/** The light public frame, with the base text rules every public page shares. */
export function PublicFrame({ children, sx, tightHeadings = true, ...rest }: BoxProps & { tightHeadings?: boolean }) {
  return (
    <Box
      {...rest}
      sx={merge(
        {
          colorScheme: "light",
          color: c("bw-ink"),
          bgcolor: c("bw-paper"),
          minHeight: "100vh",
          fontSize: "15px",
          lineHeight: 1.65,
          accentColor: c("bw-navy"),
          caretColor: c("bw-navy"),
          // Zero-specificity resets (:where), so each element's own styles win over them.
          "& :where(*)": { boxSizing: "border-box", scrollbarColor: `${c("scrollbar-thumb")} ${c("bw-paper")}` },
          "& ::selection": { background: c("text-selection"), color: c("bw-navy") },
          "& :where(h1, h2, h3, h4, p, ol, ul, dl, dd, figure, fieldset, legend)": { m: 0 },
          "& :where(ol, ul, fieldset, legend)": { listStyle: "none", p: 0, border: 0 },
          "& :where(h1, h2, h3, h4)": { fontSize: "inherit", fontWeight: "inherit" },
          "& :where(p)": { maxWidth: "72ch" },
          "& :where(a)": { color: "inherit", textDecoration: "none" },
          "& :where(em)": { fontFamily: "Georgia, serif", fontWeight: 400, color: c("emphasis") },
          "& :where(button, input, select, textarea)": { font: "inherit", color: "inherit", letterSpacing: "inherit" },
          // The website and onboarding set every first and second level heading tight; the workspace does not.
          ...(tightHeadings ? { "& :where(h1, h2)": { lineHeight: 1.1, letterSpacing: "-.035em", textWrap: "balance" } } : {}),
        },
        sx,
      )}
    >
      {children}
    </Box>
  );
}

export const headingSx = { lineHeight: 1.1, letterSpacing: "-.035em", textWrap: "balance" } as const;

/** The centred public column: 1220 pixels wide at most, with gutters that narrow with the screen. */
export function Container({ children, sx, ...rest }: BoxProps) {
  return (
    <Box
      {...rest}
      sx={merge(
        {
          width: "min(1220px, calc(100% - 96px))",
          mx: "auto",
          "@media (max-width: 1100px)": { width: "calc(100% - 64px)" },
          "@media (max-width: 540px)": { width: "calc(100% - 40px)" },
        },
        sx,
      )}
    >
      {children}
    </Box>
  );
}

type Tone = "public-button" | "public-button-small" | "public-button-light" | "public-button-outline";

/** A public call to action. With `href` it is a link; otherwise a button. */
export function ActionButton({
  tone = "public-button",
  href,
  children,
  onClick,
  type = "button",
  sx,
  ...rest
}: {
  tone?: Tone;
  href?: string;
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  sx?: SxProps<Theme>;
  [prop: string]: unknown;
}) {
  return (
    <Piece
      name={tone}
      {...(href ? { component: NextLink, href } : { type, onClick })}
      {...rest}
      disableElevation
      sx={merge(
        {
          gap: "12px",
          textAlign: "center",
          transition: "background-color .18s ease-out",
          textDecoration: "none",
          "&.Mui-disabled": { opacity: 0.6, cursor: "not-allowed" },
        },
        sx,
      )}
    >
      {children}
    </Piece>
  );
}

/** A blue text action whose underline appears on hover. With `href` it is a link; otherwise a button. */
export function TextAction({
  href,
  children,
  onClick,
  external = false,
  sx,
  ...rest
}: {
  href?: string;
  children: ReactNode;
  onClick?: () => void;
  external?: boolean;
  sx?: SxProps<Theme>;
  [prop: string]: unknown;
}) {
  const target = href
    ? external
      ? { href, target: "_blank", rel: "noreferrer" }
      : { component: NextLink, href }
    : { component: "button" as const, type: "button", onClick };
  return (
    <Piece
      name="public-text-link"
      {...target}
      {...rest}
      underline="none"
      sx={merge(
        {
          display: "inline-flex",
          alignItems: "center",
          gap: "8px",
          cursor: "pointer",
          background: "none",
          border: 0,
          p: 0,
          textDecoration: "underline",
          textDecorationColor: "transparent",
          textUnderlineOffset: "4px",
          "&:hover": { textDecorationColor: "currentColor" },
        },
        sx,
      )}
    >
      {children}
    </Piece>
  );
}

/** A compact tag; `priority` marks "Review first" content. */
export function PublicTag({ priority = false, children }: { priority?: boolean; children: ReactNode }) {
  return (
    <Piece
      name={priority ? "public-tag-priority" : "public-tag"}
      component="span"
      sx={{ display: "inline-block", fontSize: "11px", fontWeight: 650, lineHeight: 1.5 }}
    >
      {children}
    </Piece>
  );
}

const linkHover = { "&:hover": { textDecoration: "underline", textUnderlineOffset: "5px" } };

export function PublicHeader() {
  return (
    <Piece name="public-header" component="header">
      <Container
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          minHeight: "92px",
          gap: "28px",
          "@media (max-width: 540px)": { minHeight: "76px", gap: "14px" },
        }}
      >
        <Brand />
        <Stack
          component="nav"
          aria-label={t("global.public.header.nav-label")}
          direction="row"
          sx={{
            alignItems: "center",
            gap: "32px",
            fontSize: "14px",
            fontWeight: 500,
            "& > a": linkHover,
            "@media (max-width: 1100px)": { gap: "20px" },
            "@media (max-width: 540px)": { gap: "12px", fontSize: "12px", "& > a:first-of-type": { display: "none" } },
          }}
        >
          <NextLink href="/#how-it-works">
            <T k="global.public.header.how-it-works" />
          </NextLink>
          <NextLink href="/pricing/">
            <T k="global.public.header.membership" />
          </NextLink>
          <Box component={NextLink} href="/workspace/" sx={{ "@media (max-width: 800px)": { display: "none" } }}>
            <T k="global.public.header.workspace" />
          </Box>
          <ActionButton
            tone="public-button-small"
            href="/onboarding/"
            sx={{ "@media (max-width: 540px)": { fontSize: "12px", p: "10px 12px", minHeight: "40px" } }}
          >
            <T k="global.public.header.get-started" />
          </ActionButton>
        </Stack>
      </Container>
    </Piece>
  );
}

export function PublicFooter() {
  return (
    <Piece name="public-footer" component="footer">
      <Container
        sx={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "20px",
          py: "44px",
          "@media (max-width: 540px)": { display: "flex", flexDirection: "column" },
        }}
      >
        <Brand />
        <Box component="p" sx={{ fontSize: "13px", textAlign: "right", "@media (max-width: 540px)": { textAlign: "left" } }}>
          {t("global.preview-data.brand.tagline")}
        </Box>
        <Stack
          component="nav"
          aria-label={t("global.public.footer.nav-label")}
          direction="row"
          sx={{ gap: "22px", fontSize: "12px", color: c("bw-ink"), "& > a": linkHover, "@media (max-width: 540px)": { flexWrap: "wrap", gap: "12px 20px" } }}
        >
          <NextLink href="/pricing/">
            <T k="global.public.footer.membership" />
          </NextLink>
          <NextLink href="/privacy/">
            <T k="global.public.footer.privacy" />
          </NextLink>
          <NextLink href="/workspace/">
            <T k="global.public.footer.explore" />
          </NextLink>
        </Stack>
        <Box component="small" sx={{ textAlign: "right", fontSize: "11px", "@media (max-width: 540px)": { textAlign: "left" } }}>
          <T k="global.public.footer.disclaimer" />
        </Box>
      </Container>
    </Piece>
  );
}

/** An arrow after an action's label. */
export function Arrow({ size = 20, name = "arrow_forward" }: { size?: number; name?: "arrow_forward" | "chevron_right" }) {
  return <Icon name={name} size={size} />;
}

/** The plan's features, each with a check. */
export function FeatureList({ size = 20, sx }: { size?: number; sx?: object }) {
  return (
    <Box component="ul" sx={{ mt: "30px", ...sx }}>
      {PLAN_FEATURES.map((feature) => (
        <Box component="li" key={feature} sx={{ display: "flex", alignItems: "center", gap: "10px", my: "14px" }}>
          <Icon name="check_circle" size={size} sx={{ color: c("check-icon") }} />
          {feature}
        </Box>
      ))}
    </Box>
  );
}

const fieldSx = {
  width: "100%",
  minWidth: 0,
  fontSize: "14px",
  fontWeight: 400,
  "& input, & textarea, & select": { p: 0, fontSize: "14px", "&::placeholder": { color: c("placeholder"), opacity: 1 } },
  "& textarea": { resize: "vertical" },
};

/** A labelled public form field; the control comes from Material UI's InputBase or NativeSelect. */
export function PublicField({ label, children, full = false }: { label: string; children: ReactNode; full?: boolean }) {
  return (
    <Box
      component="label"
      sx={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "13px", fontWeight: 600, mb: "24px", ...(full ? { gridColumn: "1 / -1" } : {}) }}
    >
      {label}
      {children}
    </Box>
  );
}

export function PublicInput({ sx, ...props }: InputBaseProps) {
  return <Piece name="public-field" component={InputBase} {...props} sx={merge(fieldSx, sx)} />;
}

export function PublicSelect({ value, onChange, options }: { value: string; onChange: (value: string) => void; options: [string, string][] }) {
  return (
    <NativeSelect value={value} onChange={(event) => onChange(event.target.value)} input={<PublicInput />}>
      {options.map(([id, text]) => (
        <option key={id} value={id}>
          {text}
        </option>
      ))}
    </NativeSelect>
  );
}

/** A large checkbox or radio row; the selected one gets the pale blue fill. */
export function Choice({
  type = "checkbox",
  name,
  checked,
  onChange,
  children,
}: {
  type?: "checkbox" | "radio";
  name?: string;
  checked: boolean;
  onChange: () => void;
  children: ReactNode;
}) {
  return (
    <Piece
      name="choice"
      component="label"
      className={checked ? "Mui-selected" : undefined}
      sx={{ display: "flex", alignItems: "center", gap: "10px", minHeight: "58px", fontSize: "13px", cursor: "pointer" }}
    >
      <Box component="input" type={type} name={name} checked={checked} onChange={onChange} sx={{ width: "17px", height: "17px", flexShrink: 0, m: 0 }} />
      {children}
    </Piece>
  );
}

/** A pale note with an icon, for what the preview does not do. */
export function PublicNote({ icon, children }: { icon?: IconName; children: ReactNode }) {
  return (
    <Piece name="public-note" sx={{ display: "flex", alignItems: "start", gap: "12px", fontSize: "13px", my: "24px" }}>
      {icon ? <Icon name={icon} /> : null}
      {children}
    </Piece>
  );
}

export function PublicError({ children }: { children: ReactNode }) {
  return (
    <Piece name="public-error" component="p" role="alert" sx={{ fontSize: "13px", mb: "20px" }}>
      {children}
    </Piece>
  );
}

export function PublicNotice({ children, live = true }: { children: ReactNode; live?: boolean }) {
  return (
    <Piece name="public-notice" component="p" role={live ? "status" : undefined} sx={{ fontSize: "13px", mb: "20px" }}>
      {children}
    </Piece>
  );
}

/** Visually hidden text, still read by screen readers. */
export const srOnly = { position: "absolute", width: "1px", height: "1px", overflow: "hidden", clipPath: "inset(50%)", whiteSpace: "nowrap" } as const;
