import type { Metadata } from "next";
import { AppSidebar, MobileNav } from "@/components/app-sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "OmniClip",
  description: "Long-form to Shorts repurposing and autonomous channel growth",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans">
        <div className="flex min-h-svh">
          <AppSidebar />
          <div className="min-w-0 flex-1">
            <MobileNav />
            <main className="mx-auto w-full max-w-7xl px-4 py-6 md:px-8 md:py-8">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
