import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Root Frontend",
  description: "Next.js frontend scaffold for Root app."
};

type RootLayoutProps = {
  children: React.ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
