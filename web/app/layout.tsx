import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "PropertyRisk — US Real Estate Risk Dashboard",
  description: "Comprehensive natural disaster risk analysis for US residential properties",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans bg-[#f0f2f5] text-slate-900 min-h-screen`}>
        {/* ── 顶部导航 ── */}
        <nav
          className="sticky top-0 z-50 border-b border-black/[0.06]"
          style={{ background: "rgba(255,255,255,0.9)", backdropFilter: "blur(12px)" }}
        >
          <div className="max-w-screen-2xl mx-auto px-5 flex items-center h-13" style={{ gap: 40 }}>
            <Link href="/" className="flex items-center shrink-0" style={{ gap: 10 }}>
              <div
                className="w-7 h-7 rounded-lg flex items-center justify-center text-sm text-white"
                style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }}
              >
                🏡
              </div>
              <span className="font-bold text-slate-800 text-[15px] tracking-tight">
                Property<span className="gradient-text">Risk</span>
              </span>
            </Link>

            <div className="flex" style={{ gap: 24 }}>
              <Link href="/" className="nav-link px-3 py-1.5 text-sm rounded-lg hover:bg-slate-100 transition-colors">
                仪表盘
              </Link>
              <Link href="/listings" className="nav-link px-3 py-1.5 text-sm rounded-lg hover:bg-slate-100 transition-colors">
                房产列表
              </Link>
            </div>

            <div className="ml-auto flex items-center text-[11px] text-slate-400" style={{ gap: 6 }}>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              数据来源：FEMA · USGS · Zillow
            </div>
          </div>
        </nav>

        <main>{children}</main>
      </body>
    </html>
  );
}
