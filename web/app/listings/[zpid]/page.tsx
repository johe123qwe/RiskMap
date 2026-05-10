import { fetchListingDetail } from "@/lib/api";
import { scoreToColor, formatPrice } from "@/lib/utils";
import Link from "next/link";
import { notFound } from "next/navigation";

interface Props {
  params: Promise<{ zpid: string }>;
}

// 灾难进度条（浅色主题版）
function DisasterBar({ label, count, max, color }: {
  label: string; count: number; max: number; color: string;
}) {
  const pct = max > 0 ? Math.min((count / max) * 100, 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1.5 w-28 shrink-0">
        <span style={{ fontSize: 12, color: "#475569", width: 64, flexShrink: 0 }}>{label}</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: count > 0 ? color : "#94a3b8", minWidth: 16 }}>
          {count}
        </span>
      </div>
      <div style={{ flex: 1, height: 6, background: "#e2e8f0", borderRadius: 4, overflow: "hidden" }}>
        <div style={{ height: "100%", borderRadius: 4, backgroundColor: color, width: `${pct}%`, transition: "width 0.3s" }} />
      </div>
    </div>
  );
}

export default async function ListingDetailPage({ params }: Props) {
  const { zpid } = await params;
  let item: any;
  try {
    item = await fetchListingDetail(zpid);
  } catch {
    notFound();
  }

  const color = scoreToColor(item.risk_score);
  const maxDisaster = Math.max(
    item.fema_flood || 0, item.fema_hurricane || 0, item.fema_tornado || 0,
    item.fema_fire || 0, item.fema_severe_storm || 0, item.fema_winter_storm || 0, 1
  );

  // 浅色主题颜色常量
  const C = {
    bg:       "#f0f2f5",
    card:     "#ffffff",
    border:   "#e2e8f0",
    text:     "#0f172a",
    sub:      "#334155",
    muted:    "#64748b",
    trackBg:  "#e2e8f0",
  };

  return (
    <div style={{ background: C.bg, minHeight: "100vh", paddingBottom: 40, color: C.text }}>
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "24px 16px", display: "flex", flexDirection: "column", gap: 20 }}>

        {/* 返回 */}
        <Link href="/listings" style={{ fontSize: 13, color: C.muted, textDecoration: "none" }}>
          ← 返回列表
        </Link>

        {/* 顶部：图片 + 基本信息 */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {/* 图片 */}
          <div style={{ borderRadius: 16, overflow: "hidden", background: "#e2e8f0", height: 280 }}>
            {item.img_url ? (
              <img src={item.img_url} alt={item.address} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            ) : (
              <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 64 }}>🏠</div>
            )}
          </div>

          {/* 基本信息 */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <h1 style={{ fontSize: 20, fontWeight: 700, color: C.text, margin: 0 }}>{item.address}</h1>
              <p style={{ fontSize: 14, color: C.muted, margin: "4px 0 0" }}>{item.city}, {item.state} {item.zip}</p>
            </div>

            <div style={{ fontSize: 28, fontWeight: 700, color: C.text }}>{formatPrice(item.price)}</div>

            <div style={{ display: "flex", gap: 16, fontSize: 13, color: C.sub }}>
              {item.beds  && <span>🛏 {item.beds} 卧室</span>}
              {item.baths && <span>🚿 {item.baths} 卫生间</span>}
              {item.area_sqft && <span>📐 {item.area_sqft?.toLocaleString()} sqft</span>}
            </div>

            {item.elevation_ft && (
              <p style={{ fontSize: 13, color: C.muted, margin: 0 }}>
                ⛰️ 海拔：<strong style={{ color: C.sub }}>{Math.round(item.elevation_ft)} ft</strong>
                （{Math.round(item.elevation_ft * 0.3048)} m）
              </p>
            )}

            {/* 综合风险评分卡片 */}
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: 16 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ fontSize: 13, color: C.muted }}>综合风险评分</span>
                <span style={{ fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 20,
                  background: color, color: "#fff" }}>
                  {item.risk_label || "—"}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
                <span style={{ fontSize: 48, fontWeight: 900, color, lineHeight: 1 }}>
                  {item.risk_score ?? "—"}
                </span>
                <span style={{ fontSize: 18, color: C.muted, marginBottom: 4 }}>/ 100</span>
              </div>
              <div style={{ height: 8, background: C.trackBg, borderRadius: 4, marginTop: 10, overflow: "hidden" }}>
                <div style={{ height: "100%", borderRadius: 4, background: color,
                  width: `${item.risk_score ?? 0}%`, transition: "width 0.4s" }} />
              </div>
            </div>
          </div>
        </div>

        {/* 灾难 & 地震 */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {/* FEMA 灾难 */}
          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: 20 }}>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: C.text, margin: "0 0 6px" }}>🌪 FEMA 历史灾难</h2>
            {item.fema_county && (
              <p style={{ fontSize: 11, color: C.muted, margin: "0 0 12px" }}>
                县：{item.fema_county}
                {item.fema_first_year && ` · ${item.fema_first_year}–${item.fema_last_year} 年`}
                {item.fema_total != null && ` · 共 ${item.fema_total} 次`}
              </p>
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {[
                { label: "洪水",     count: item.fema_flood        || 0, color: "#3b82f6" },
                { label: "飓风",     count: item.fema_hurricane    || 0, color: "#dc2626" },
                { label: "龙卷风",   count: item.fema_tornado      || 0, color: "#8b5cf6" },
                { label: "野火",     count: item.fema_fire         || 0, color: "#f97316" },
                { label: "严重风暴", count: item.fema_severe_storm || 0, color: "#6b7280" },
                { label: "冬季风暴", count: item.fema_winter_storm || 0, color: "#06b6d4" },
                { label: "其他",     count: item.fema_other        || 0, color: "#a3a3a3" },
              ].map(d => <DisasterBar key={d.label} {...d} max={maxDisaster} />)}
            </div>
          </div>

          {/* 地震 */}
          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: 20 }}>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: C.text, margin: "0 0 16px" }}>🌋 地震风险</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {[
                { label: "风险等级",          value: item.eq_risk || "—",                                        vc: undefined },
                { label: "历史地震（M2.5+）", value: item.eq_count != null ? String(item.eq_count) : "—",        vc: undefined },
                { label: "最大震级",          value: item.eq_max_mag ? `M${item.eq_max_mag}` : "—",
                  vc: item.eq_max_mag ? scoreToColor(item.eq_max_mag >= 7 ? 90 : item.eq_max_mag >= 6 ? 70 : item.eq_max_mag >= 5 ? 50 : 30) : undefined },
                { label: "最近地震",          value: item.eq_last_date || "—",                                   vc: undefined },
              ].map(row => (
                <div key={row.label} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 13, color: C.muted, width: 144, flexShrink: 0 }}>{row.label}</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: row.vc ?? C.text }}>{row.value}</span>
                </div>
              ))}
            </div>

            {item.eq_max_mag && (
              <div style={{ marginTop: 20 }}>
                <div style={{ fontSize: 11, color: C.muted, marginBottom: 4 }}>最大震级（M{item.eq_max_mag}）</div>
                <div style={{ height: 8, background: C.trackBg, borderRadius: 4, overflow: "hidden" }}>
                  <div style={{
                    height: "100%", borderRadius: 4,
                    width: `${Math.min((item.eq_max_mag / 9) * 100, 100)}%`,
                    backgroundColor: scoreToColor(item.eq_max_mag >= 7 ? 90 : item.eq_max_mag >= 6 ? 70 : item.eq_max_mag >= 5 ? 50 : 30),
                    transition: "width 0.4s",
                  }} />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: C.muted, marginTop: 3 }}>
                  <span>M2.5</span><span>M5</span><span>M7</span><span>M9</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 描述 */}
        {item.description && item.description.length > 10 && (
          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: 20 }}>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: C.text, margin: "0 0 10px" }}>✨ What&apos;s Special</h2>
            <p style={{ fontSize: 13, color: C.sub, lineHeight: 1.7, margin: 0 }}>{item.description}</p>
          </div>
        )}

        {/* 外部链接 */}
        {item.url && (
          <div style={{ textAlign: "center" }}>
            <a href={item.url} target="_blank" rel="noopener noreferrer"
              style={{ display: "inline-flex", alignItems: "center", gap: 8,
                background: "#6366f1", color: "#fff", fontSize: 13, fontWeight: 600,
                padding: "10px 24px", borderRadius: 12, textDecoration: "none",
                transition: "background 0.2s" }}>
              在 Zillow 上查看 →
            </a>
          </div>
        )}

      </div>
    </div>
  );
}
