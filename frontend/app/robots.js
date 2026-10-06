const siteOrigin = process.env.GITSCOPE_SITE_URL;

export default function robots() {
  return {
    rules: { userAgent: "*", allow: "/" },
    ...(siteOrigin ? { sitemap: `${siteOrigin.replace(/\/$/, "")}/sitemap.xml` } : {}),
  };
}
