export const siteConfig = {
  name: "SentinelAI",
  description: "Multi-Agent AI Cybersecurity Copilot",
  tagline: "Detect. Prioritise. Advise.",
  version: "0.1.0",
  links: {
    docs: "/docs",
    support: "mailto:security@sentinelai.app",
  },
} as const;

export type SiteConfig = typeof siteConfig;
