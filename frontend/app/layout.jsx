import "../src/App.css";

const siteOrigin = process.env.GITSCOPE_SITE_URL;
const title = "GitScope | Evidence-Driven GitHub Engineering Health";
const description = "Explore transparent, evidence-based engineering health analytics for public GitHub users and repositories.";

export const metadata = {
  metadataBase: siteOrigin ? new URL(siteOrigin) : undefined,
  title: {
    default: title,
    template: "%s | GitScope",
  },
  description,
  applicationName: "GitScope",
  openGraph: {
    type: "website",
    siteName: "GitScope",
    title,
    description,
    ...(siteOrigin ? { url: siteOrigin } : {}),
  },
  twitter: {
    card: "summary",
    title,
    description,
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <div className="app">
          {children}
        </div>
      </body>
    </html>
  );
}
