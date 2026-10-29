import Box from "@mui/material/Box";

import { Arrow, ActionButton, Container, PublicFooter, PublicFrame, PublicHeader, PublicTag, TextAction, c, headingSx } from "@/components/public";
import { Icon, Piece } from "@/components/ui";
import { t } from "@/lib/text";

const p = (key: string) => t(`pages.home.${key}`);
const STRIP = ["1-fda", "2-ttb", "3-federal-register", "4-health-canada", "5-eur-lex"];
const STEPS = [1, 2, 3];
const mutedText = { color: c("bw-muted") };

function PreviewEntry({ first }: { first: boolean }) {
  const k = first ? "first" : "second";
  return (
    <Box sx={{ py: first ? "20px" : "16px", borderTop: `1px solid ${c("bw-line")}` }}>
      <PublicTag priority={first}>{p(`preview.${k}-tag`)}</PublicTag>
      <Box component="h3" sx={{ fontSize: "17px", lineHeight: 1.45, fontWeight: 600, my: "10px" }}>
        {p(`preview.${k}-title`)}
      </Box>
      {first ? (
        <Box component="p" sx={{ fontSize: "13px", ...mutedText }}>
          {p("preview.first-body")}
        </Box>
      ) : null}
      <Box sx={{ display: "flex", alignItems: "center", gap: "10px", mt: "16px", fontSize: "11px", ...mutedText }}>
        <Box component="strong" sx={{ color: c("bw-navy"), fontSize: "12px" }}>
          {p(`preview.${k}-source`)}
        </Box>
        <span>{p(`preview.${k}-topic`)}</span>
        <Icon name="arrow_forward" size={18} sx={{ ml: "auto" }} />
      </Box>
    </Box>
  );
}

export function PublicHome() {
  return (
    <PublicFrame>
      <PublicHeader />
      <main id="main">
        <Container
          component="section"
          sx={{
            display: "grid",
            gridTemplateColumns: "1.1fr 1fr",
            gap: "8%",
            alignItems: "center",
            pt: "86px",
            pb: "94px",
            "@media (max-width: 1100px)": { gap: "5%" },
            "@media (max-width: 800px)": { gridTemplateColumns: "1fr", gap: "45px", py: "55px" },
            "@media (max-width: 540px)": { py: "42px" },
          }}
        >
          <div>
            <Box
              component="h1"
              sx={{
                ...headingSx,
                fontSize: "clamp(40px, 5.3vw, 74px)",
                fontWeight: "550",
                "@media (max-width: 800px)": { fontSize: "58px" },
                "@media (max-width: 540px)": { fontSize: "43px" },
              }}
            >
              {p("hero.title-1")}
              <br />
              {p("hero.title-2")}
              <br />
              <em>{p("hero.title-emphasis")}</em>
            </Box>
            <Box
              component="p"
              sx={{
                fontSize: "17px",
                lineHeight: 1.8,
                maxWidth: "43ch",
                my: "28px",
                ...mutedText,
                "@media (max-width: 800px)": { maxWidth: "55ch" },
                "@media (max-width: 540px)": { fontSize: "15px" },
              }}
            >
              {p("hero.lede")}
            </Box>
            <Box sx={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: "22px", "@media (max-width: 540px)": { gap: "18px" } }}>
              <ActionButton href="/onboarding/">
                {p("hero.build")} <Arrow />
              </ActionButton>
              <TextAction href="/workspace/">
                {p("hero.explore")} <Arrow name="chevron_right" size={18} />
              </TextAction>
            </Box>
            <Box component="p" sx={{ mt: "20px", maxWidth: "40ch", fontSize: "13px", lineHeight: 1.6, ...mutedText }}>
              {p("hero.audience")}
            </Box>
          </div>
          <Piece
            name="briefing-preview"
            aria-label={p("preview.label")}
            sx={{ overflow: "hidden", border: 0, "@media (max-width: 800px)": { maxWidth: "540px", width: "100%", mx: "auto" } }}
          >
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                gap: "9px",
                bgcolor: c("bw-navy"),
                color: c("white"),
                px: "24px",
                py: "15px",
                fontSize: "13px",
                "@media (max-width: 540px)": { px: "20px", fontSize: "12px" },
              }}
            >
              <Box component="span" sx={{ width: 6, height: 6, borderRadius: "50%", bgcolor: c("live-dot") }} />
              {p("preview.heading")}
              <Box component="span" sx={{ ml: "auto", color: c("preview-label"), fontSize: "10px", letterSpacing: ".08em" }}>
                {p("preview.badge")}
              </Box>
            </Box>
            <Box sx={{ p: "25px 30px 16px", color: c("bw-ink"), "@media (max-width: 540px)": { p: "24px 22px 12px" } }}>
              <Box sx={{ fontSize: "12px", mb: "14px", ...mutedText }}>{p("preview.kicker")}</Box>
              <Box component="h2" sx={{ ...headingSx, fontSize: "34px", fontWeight: "550" }}>
                {p("preview.title-1")}
                <br />
                {p("preview.title-2")}
              </Box>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: "6px 18px", fontSize: "11px", m: "16px 0 22px", ...mutedText }}>
                <span>{p("preview.market")}</span>
                <span>{p("preview.category")}</span>
              </Box>
              <PreviewEntry first />
              <PreviewEntry first={false} />
              <Box component="p" sx={{ fontSize: "10px", color: c("bw-muted"), py: "7px" }}>
                {p("preview.note")}
              </Box>
            </Box>
          </Piece>
        </Container>
        <Box sx={{ borderTop: `1px solid ${c("bw-line")}`, borderBottom: `1px solid ${c("bw-line")}`, bgcolor: c("strip-surface") }}>
          <Container
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "28px",
              py: "30px",
              "@media (max-width: 800px)": { flexWrap: "wrap", justifyContent: "start", gap: "22px 32px", "& > p": { width: "100%" } },
            }}
          >
            <Box component="p" sx={{ fontSize: "12px", lineHeight: 1.6, ...mutedText }}>
              {p("strip.intro-1")}
              <br />
              {p("strip.intro-2")}
            </Box>
            {STRIP.map((key) => (
              <Box component="span" key={key} sx={{ fontSize: "17px", fontWeight: 600, letterSpacing: "-.02em", color: c("bw-muted"), "@media (max-width: 540px)": { fontSize: "15px" } }}>
                {p(`strip.${key}`)}
              </Box>
            ))}
          </Container>
        </Box>
        <Container
          component="section"
          id="how-it-works"
          sx={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "12%",
            py: "110px",
            scrollMarginTop: "30px",
            "@media (max-width: 800px)": { gap: "45px", py: "70px", gridTemplateColumns: "1fr" },
          }}
        >
          <div>
            <Box
              component="h2"
              sx={{ ...headingSx, fontSize: "48px", fontWeight: "550", "@media (max-width: 800px)": { fontSize: "42px" }, "@media (max-width: 540px)": { fontSize: "36px" } }}
            >
              {p("how.title-1")}
              <br />
              <em>{p("how.title-emphasis")}</em>
            </Box>
            <Box component="p" sx={{ maxWidth: "40ch", my: "26px", ...mutedText }}>
              {p("how.intro")}
            </Box>
            <TextAction href="/onboarding/">
              {p("how.set-up")} <Arrow size={18} />
            </TextAction>
          </div>
          <Box component="ol">
            {STEPS.map((step, index) => (
              <Box
                component="li"
                key={step}
                sx={{ display: "flex", gap: "25px", py: "26px", borderTop: index ? `1px solid ${c("bw-line")}` : 0, pt: index ? "26px" : 0 }}
              >
                <Box component="span" className="numeric" sx={{ flex: "0 0 28px", fontSize: "15px", color: c("step-number") }}>
                  {step}
                </Box>
                <div>
                  <Box component="h3" sx={{ fontSize: "19px", fontWeight: "600", mb: "10px" }}>
                    {p(`how.step-${step}-title`)}
                  </Box>
                  <Box component="p" sx={{ fontSize: "14px", ...mutedText }}>
                    {p(`how.step-${step}-body`)}
                  </Box>
                </div>
              </Box>
            ))}
          </Box>
        </Container>
        <Container
          component="section"
          sx={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "12%",
            borderTop: `1px solid ${c("bw-line")}`,
            pt: "55px",
            pb: "100px",
            "@media (max-width: 800px)": { gap: "35px", gridTemplateColumns: "1fr", pb: "60px" },
          }}
        >
          <div>
            <Icon name="filter_list" size={30} />
            <Box component="h2" sx={{ ...headingSx, fontSize: "32px", fontWeight: "550", mt: "14px" }}>
              {p("manifesto.title-1")}
              <br />
              {p("manifesto.title-2")}
            </Box>
          </div>
          <div>
            <Box component="p" sx={{ mt: "15px" }}>
              {p("manifesto.body")}
            </Box>
            <Box component="p" sx={{ mt: "15px", fontSize: "13px", lineHeight: 1.6, ...mutedText }}>
              {p("manifesto.note")}
            </Box>
          </div>
        </Container>
        <Box component="section" sx={{ bgcolor: c("bw-navy"), color: c("white"), "& em": { color: c("close-emphasis") } }}>
          <Container
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "40px",
              py: "70px",
              "@media (max-width: 800px)": { py: "50px" },
              "@media (max-width: 540px)": { alignItems: "start", flexDirection: "column", gap: "28px" },
            }}
          >
            <Box
              component="h2"
              sx={{ ...headingSx, fontSize: "54px", fontWeight: "500", "@media (max-width: 800px)": { fontSize: "42px" }, "@media (max-width: 540px)": { fontSize: "40px" } }}
            >
              {p("close.title-1")}
              <br />
              <em>{p("close.title-emphasis")}</em>
            </Box>
            <div>
              <Box component="p" sx={{ color: c("close-text"), mb: "20px" }}>
                {p("close.body")}
              </Box>
              <ActionButton tone="public-button-light" href="/onboarding/">
                {p("close.build")} <Arrow />
              </ActionButton>
            </div>
          </Container>
        </Box>
      </main>
      <PublicFooter />
    </PublicFrame>
  );
}
