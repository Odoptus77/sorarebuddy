import type { Metadata } from "next";

import { Nav } from "@/components/nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "sorarebuddy",
  description: "Sorare-Dashboard für nicktd7: Aufstellungen, Kader, GW-Bilanz und Modellqualität",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="de" className="h-full antialiased">
      <body className="min-h-full">
        <div className="sticky top-0 z-20 border-b border-line bg-page/90 backdrop-blur">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
            <span className="font-semibold tracking-tight">sorarebuddy</span>
            <Nav />
          </div>
        </div>
        <main className="mx-auto max-w-6xl px-4 py-6 sm:py-8">{children}</main>
      </body>
    </html>
  );
}
