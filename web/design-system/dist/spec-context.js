"use client";
import { createContext, useContext } from "react";
const SpecContext = createContext(null);
function useDesignSpec(who = "useDesignSpec") {
  const spec = useContext(SpecContext);
  if (!spec) {
    throw new Error(
      `${who} needs a DesignSystemProvider above it, and none was found. Part, useParts, SiteHeader, SiteFooter and useDesignSpec read the design spec from it: wrap the tree in <DesignSystemProvider spec={spec} copy={copy}>. Outside React (server code, tests, plain modules) use partProps(spec, names) or partSx(spec, name) from regwatch-design/styles with the spec itself. If a provider is there, two copies of regwatch-design may be installed; check that the app resolves one.`
    );
  }
  return spec;
}
export {
  SpecContext,
  useDesignSpec
};
//# sourceMappingURL=spec-context.js.map