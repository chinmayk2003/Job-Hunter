import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "JobHunter AI | AI-Powered Job Search and Match Platform",
  description: "Accelerate your career with JobHunter AI. Automatically search, filter, match, and tailor applications using state-of-the-art AI agents.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className} id="jobhunter-root">
        {children}
      </body>
    </html>
  );
}
