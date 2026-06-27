import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CogniFlow — RAG + Multi-Agent Research Assistant",
  description:
    "Interview-ready demo of a Retrieval-Augmented Generation pipeline orchestrated by a multi-agent system (Router → Retriever → Reranker → Analyzer ⇄ Critic). Built with Next.js, TypeScript, and z-ai-web-dev-sdk.",
  keywords: [
    "RAG",
    "Multi-Agent",
    "LangGraph",
    "Next.js",
    "TypeScript",
    "Interview Project",
    "AI",
  ],
  authors: [{ name: "CogniFlow" }],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
