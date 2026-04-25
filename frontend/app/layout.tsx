import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Skill Assessment Agent",
  description:
    "Conversational skill assessment + personalised learning plan. " +
    "IRT-driven adaptive interview, ESCO-grounded gap analysis, curated resources.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
