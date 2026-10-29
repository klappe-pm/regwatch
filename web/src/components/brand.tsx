import Box from "@mui/material/Box";
import SvgIcon from "@mui/material/SvgIcon";
import NextLink from "next/link";

import { BRAND } from "@/lib/bev-watch";
import { t } from "@/lib/text";

import { Piece } from "./ui";

/** The red beverage mark: a rounded square with a white line symbol. */
export function BrandMark({ size = 32 }: { size?: number }) {
  return (
    <SvgIcon viewBox="0 0 32 32" aria-hidden focusable="false" sx={{ width: size, height: size, fontSize: size, flexShrink: 0 }}>
      <Box component="rect" width="32" height="32" rx="9" sx={{ fill: "var(--ds-color-brand-red)" }} />
      <Box
        component="path"
        d="M8 11h5.5a5 5 0 0 1 0 10H8V11Zm5.5 0H24l-4 10h-6.5M8 16h12"
        sx={{ fill: "none", stroke: "var(--ds-color-white)", strokeWidth: 2, strokeLinejoin: "round" }}
      />
    </SvgIcon>
  );
}

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Piece
      name="brand"
      component={NextLink}
      href="/"
      aria-label={t("global.preview-data.brand.home", { name: BRAND })}
      underline="none"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: "10px",
        whiteSpace: "nowrap",
        textDecoration: "none",
        "@media (max-width: 540px)": { fontSize: "20px", gap: "8px", "& svg": { width: 28, height: 28 } },
      }}
    >
      <BrandMark />
      {compact ? null : (
        <span>
          {t("global.preview-data.brand.name-first")}{" "}
          <Box component="span" sx={{ fontWeight: 400 }}>
            {t("global.preview-data.brand.name-second")}
          </Box>
        </span>
      )}
    </Piece>
  );
}
