import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "MRKTGURU Agent",
  description: "AI app builder platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
