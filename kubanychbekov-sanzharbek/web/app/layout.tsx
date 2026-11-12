import "@fontsource-variable/inter";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Providers } from "@/components/Providers";
import { getLang } from "@/lib/i18n/server";
import "./globals.css";

export const metadata: Metadata = {
  title: "FixFlow - Field Service Management Platform",
  description:
    "Dispatch work, manage assets, coordinate technicians and track SLAs across independent organizations.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const lang = await getLang();
  return (
    <html lang={lang}>
      <body>
        <Providers lang={lang}>{children}</Providers>
      </body>
    </html>
  );
}
