import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "SiteDoc — AI редактор сайтов",
  description: "Опишите задачу — AI внесёт изменения на ваш сайт",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-surface-2">{children}</body>
    </html>
  );
}
