import type { Metadata } from "next";
import { IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { TopNav } from "@/components/layout/TopNav";

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "AgentQR",
  description: "Multi-agent AI quantitative trading terminal",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${mono.className} flex h-screen flex-col overflow-hidden`}>
        <TopNav />
        <main className="flex flex-1 overflow-hidden">{children}</main>
      </body>
    </html>
  );
}
