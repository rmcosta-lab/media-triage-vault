import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Local Media Organizer",
  description: "Local, offline media triage and organization.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
