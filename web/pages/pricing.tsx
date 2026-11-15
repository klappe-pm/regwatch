import Box from "@mui/material/Box";

import { ActionButton, Arrow, Container, FeatureList, PublicFooter, PublicFrame, PublicHeader, c, headingSx } from "@/components/public";
import { Piece } from "@/components/ui";
import { t } from "@/lib/text";

const p = (key: string) => t(`pages.pricing.${key}`);
const muted = { color: c("bw-muted") };

export default function PricingPage() {
  return (
    <PublicFrame>
      <PublicHeader />
      <Container component="main" id="main" sx={{ pt: "70px", pb: "100px", "@media (max-width: 540px)": { pt: "45px", pb: "65px" } }}>
        <Box component="h1" sx={{ ...headingSx, fontSize: "64px", fontWeight: 550, "@media (max-width: 540px)": { fontSize: "44px" } }}>
          {p("header.title-1")}
          <br />
          <em>{p("header.title-emphasis")}</em>
        </Box>
        <Box component="p" sx={{ fontSize: "17px", mt: "22px", mb: "44px", ...muted }}>
          {p("header.lede")}
        </Box>
        <Piece
          name="plan-card"
          sx={{
            display: "grid",
            gridTemplateColumns: "1.2fr 1fr",
            overflow: "hidden",
            "& > div": { p: "44px", "@media (max-width: 540px)": { p: "27px" } },
            "@media (max-width: 800px)": { gridTemplateColumns: "1fr" },
          }}
        >
          <div>
            <Box component="h2" sx={{ fontSize: "28px", fontWeight: 600, mb: "18px", "@media (max-width: 540px)": { fontSize: "25px" } }}>
              {p("plan.title")}
            </Box>
            <p>{p("plan.intro")}</p>
            <FeatureList />
          </div>
          <Box sx={{ bgcolor: c("plan-surface") }}>
            <Box component="p" sx={{ fontWeight: 600 }}>
              {p("plan.status")}
            </Box>
            <Box component="strong" sx={{ display: "block", fontSize: "40px", fontWeight: 500, my: "12px" }}>
              {p("plan.price")}
            </Box>
            <Box component="p" sx={{ fontSize: "14px", ...muted }}>
              {p("plan.terms")}
            </Box>
            <ActionButton href="/onboarding/" sx={{ mt: "26px", mb: "16px" }}>
              {p("plan.try")} <Arrow />
            </ActionButton>
            <Box component="small" sx={{ display: "block", fontSize: "12px", ...muted }}>
              {p("plan.inactive")}
            </Box>
          </Box>
        </Piece>
        <Box sx={{ maxWidth: "760px", mx: "auto", mt: "70px" }}>
          <Box component="h2" sx={{ ...headingSx, fontSize: "32px", mb: "26px" }}>
            {p("faq.title")}
          </Box>
          {[1, 2, 3, 4].map((n) => (
            <Box component="details" key={n} sx={{ borderTop: `1px solid ${c("bw-line")}`, py: "20px" }}>
              <Box component="summary" sx={{ cursor: "pointer", fontWeight: 600 }}>
                {p(`faq.${n}-question`)}
              </Box>
              <Box component="p" sx={{ mt: "16px", ...muted }}>
                {p(`faq.${n}-answer`)}
              </Box>
            </Box>
          ))}
        </Box>
      </Container>
      <PublicFooter />
    </PublicFrame>
  );
}
