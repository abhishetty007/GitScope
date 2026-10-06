const siteOrigin = process.env.GITSCOPE_SITE_URL?.replace(/\/$/, "");

export default function sitemap() {
  // Deliberately list only the landing page. Dynamic GitHub result URLs are not
  // added en masse; configure the public site origin before production deploy.
  return siteOrigin ? [{ url: siteOrigin, changeFrequency: "monthly", priority: 1 }] : [];
}
