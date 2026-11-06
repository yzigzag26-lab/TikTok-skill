import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "TikTok Intelligence Skill", description: "Grounded evidence extraction for public TikTok videos." };
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
