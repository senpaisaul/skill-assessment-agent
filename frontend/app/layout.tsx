import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Skill Assessment Agent",
  description:
    "Voice-powered conversational skill assessment with IRT-driven adaptive interview, " +
    "ESCO-grounded gap analysis, and personalised learning plans.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}