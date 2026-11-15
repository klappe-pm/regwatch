import Box from "@mui/material/Box";

import { Container, PublicFooter, PublicFrame, PublicHeader, c, headingSx } from "@/components/public";
import { t } from "@/lib/text";

const p = (key: string) => t(`pages.privacy.content.${key}`);

export default function PrivacyPage() {
  return (
    <PublicFrame>
      <PublicHeader />
      <Container component="main" id="main" sx={{ maxWidth: "800px", pt: "70px", pb: "100px" }}>
        <Box component="h1" sx={{ ...headingSx, fontSize: "44px", mb: "40px", "@media (max-width: 540px)": { fontSize: "34px" } }}>
          {p("title")}
        </Box>
        {[1, 2, 3, 4].map((n) => (
          <Box key={n}>
            <Box component="h2" sx={{ ...headingSx, fontSize: "24px", mt: "34px", mb: "16px" }}>
              {p(`${n}-heading`)}
            </Box>
            <Box component="p" sx={{ color: c("bw-muted") }}>
              {p(`${n}-body`)}
            </Box>
          </Box>
        ))}
      </Container>
      <PublicFooter />
    </PublicFrame>
  );
}
