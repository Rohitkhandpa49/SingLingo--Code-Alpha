import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SiteFooter, SiteHeader } from "@/components/layout/site-chrome";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "SignLingo — communication without barriers",
    template: "%s | SignLingo"
  },
  description:
    "An accessible project exploring communication between Indian Sign Language and spoken Hindi or English.",
  applicationName: "SignLingo"
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <SiteHeader />
        <main id="main-content">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
