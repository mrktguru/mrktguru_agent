import "./globals.css";
import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: "SiteDoc — AI редактор сайтов",
  description: "Опишите задачу — AI внесёт изменения на ваш сайт",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-surface-2">{children}</body>
    </html>
  );
}
