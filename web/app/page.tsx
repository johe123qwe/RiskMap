"use client";
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  BarChart, Bar, Cell, Tooltip, ResponsiveContainer, XAxis, YAxis,
  PieChart, Pie,
} from "recharts";
import { RISK_COLORS } from "@/lib/utils";

const RiskMap = dynamic(() => import("@/components/RiskMap"), { ssr: false });

const DISASTER_META = [
  { key: "flood",         label: "洪水",    color: "#38bdf8" },
  { key: "hurricane",    label: "飓风",    color: "#f87171" },
  { key: "tornado",      label: "龙卷风",  color: "#a78bfa" },
  { key: "fire",         label: "野火",    color: "#fb923c" },
  { key: "severe_storm", label: "强风暴",  color: "#94a3b8" },
  { key: "winter_storm", label: "冬季风暴",color: "#22d3ee" },
];

const RISK_ORDER = ["极高风险", "较高风险", "中等风险", "较低风险", "低风险"];

const MAP_LEGEND = [
  { label: "低",   color: "#3b82f6" },
  { label: "较低", color: "#22c55e" },
  { label: "中",   color: "#eab308" },
  { label: "较高", color: "#f97316" },
  { label: "极高", color: "#dc2626" },
];

// ── 颜色常量（所有 inline style 用这里） ─────────────────────
const C = {
  text:    "#0f172a",   // 主文字
  sub:     "#334155",   // 次要文字
  muted:   "#64748b",   // 辅助文字
  border:  "#e2e8f0",
  bg:      "#f8fafc",
};

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8,
      padding: "6px 10px", boxShadow: "0 2px 8px rgba(0,0,0,0.08)", fontSize: 12 }}>
      {label && <p style={{ color: C.muted, marginBottom: 2 }}>{label}</p>}
      <p style={{ color: C.text, fontWeight: 600 }}>{payload[0].value?.toLocaleString()}</p>
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [markers, setMarkers] = useState<any[]>([]);
  const [error, setError] = useState(false);

  const loadData = (silent = false) => {
    setError(false);
    if (!silent) setStats(null);
    Promise.all([
      fetch("/api/stats").then(r => { if (!r.ok) throw new Error(); return r.json(); }),
      fetch("/api/map").then(r => { if (!r.ok) throw new Error(); return r.json(); }),
    ]).then(([s, m]) => {
      setStats(s);
      setMarkers(m);
    }).catch(() => {
      if (!silent) setError(true);
    });
  };

  // 初始加载
  useEffect(() => { loadData(false); }, []);

  // BF Cache 恢复（浏览器后退）：静默刷新，不显示 loading
  useEffect(() => {
    const onPageShow = (e: PageTransitionEvent) => {
      if (e.persisted) loadData(true);  // silent=true 不清空已有数据
    };
    window.addEventListener("pageshow", onPageShow);
    return () => window.removeEventListener("pageshow", onPageShow);
  }, []);

  if (error) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "80vh" }}>
      <div style={{ textAlign: "center" }}>
        <p style={{ color: "#ef4444", marginBottom: 12 }}>数据加载失败，请检查后端服务是否运行。</p>
        <button onClick={loadData}
          style={{ padding: "8px 20px", borderRadius: 8, background: "#6366f1",
            color: "#fff", border: "none", cursor: "pointer", fontSize: 13 }}>
          重试
        </button>
      </div>
    </div>
  );

  if (!stats) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "80vh" }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ width: 56, height: 56, margin: "0 auto 12px", borderRadius: 16,
          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24,
          background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }}>🏡</div>
        <p style={{ color: C.muted, fontSize: 13 }}>正在加载数据...</p>
      </div>
    </div>
  );

  const disasterData = DISASTER_META.map(d => ({
    name: d.label,
    value: (stats.disaster_totals?.[d.key] as number) || 0,
    color: d.color,
  }));

  const pieData = RISK_ORDER
    .map(label => {
      const dist = stats.risk_distribution as { label: string; count: number }[] | undefined;
      const f = dist?.find(r => r.label === label);
      return f ? { name: label, value: f.count } : null;
    })
    .filter(Boolean) as { name: string; value: number }[];

  const STAT_CARDS = [
    { icon: "🏠", label: "房产总数",   value: stats.total?.toLocaleString(),                       accent: "#6366f1" },
    { icon: "🗺️", label: "覆盖州数",   value: `${stats.state_distribution?.length} 州`,            accent: "#0ea5e9" },
    { icon: "💰", label: "平均价格",   value: `$${((stats.avg_price||0)/1000).toFixed(0)}K`,       accent: "#10b981" },
    { icon: "⚠️", label: "平均风险分", value: `${stats.avg_risk_score ?? "—"} / 100`,              accent: "#f97316" },
  ];

  return (
    <div style={{ display: "flex", height: "calc(100vh - 52px)" }}>

      {/* ══ 左侧面板 ══════════════════════════════════════════ */}
      <aside style={{
        width: 300, flexShrink: 0,
        borderRight: `1px solid ${C.border}`,
        background: "#fff",
        overflowY: "auto",
        color: C.text,
        scrollbarWidth: "thin" as const,
      }}>
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>

          {/* 页头 */}
          <div>
            <h1 style={{ fontSize: 15, fontWeight: 700, color: C.text, margin: 0, lineHeight: 1.3 }}>
              美国房产<span className="gradient-text" style={{ marginLeft: 4 }}>风险仪表盘</span>
            </h1>
            <p style={{ fontSize: 11, color: C.muted, margin: "4px 0 0" }}>
              FEMA · USGS · Zillow 数据整合
            </p>
          </div>

          {/* 四格统计 */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {STAT_CARDS.map(c => (
              <div key={c.label} style={{
                borderRadius: 12, padding: 12,
                background: `${c.accent}10`,
                border: `1px solid ${c.accent}30`,
              }}>
                <div style={{ fontSize: 18, marginBottom: 6 }}>{c.icon}</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: C.text, lineHeight: 1.2 }}>{c.value}</div>
                <div style={{ fontSize: 10, color: C.sub, marginTop: 3,
                  textTransform: "uppercase" as const, letterSpacing: "0.05em", fontWeight: 600 }}>
                  {c.label}
                </div>
              </div>
            ))}
          </div>

          {/* 分割线 */}
          <div style={{ borderTop: `1px solid ${C.border}` }} />

          {/* 柱状图 */}
          <div>
            <p style={{ fontSize: 12, fontWeight: 700, color: C.sub, margin: "0 0 8px" }}>🌪 历史灾难次数</p>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={disasterData} barCategoryGap="35%"
                margin={{ top: 2, right: 4, left: -28, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 9 }} axisLine={false} tickLine={false}
                  tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(0,0,0,0.03)" }} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={32}>
                  {disasterData.map((e, i) => <Cell key={i} fill={e.color} fillOpacity={0.9} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* 饼图 */}
          <div>
            <p style={{ fontSize: 12, fontWeight: 700, color: C.sub, margin: "0 0 8px" }}>⚠️ 风险等级分布</p>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ flexShrink: 0 }}>
                <ResponsiveContainer width={90} height={90}>
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%"
                      innerRadius={26} outerRadius={42} paddingAngle={2} dataKey="value" stroke="none">
                      {pieData.map((e, i) => <Cell key={i} fill={RISK_COLORS[e.name] || "#94a3b8"} />)}
                    </Pie>
                    <Tooltip content={<ChartTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 5 }}>
                {pieData.map(d => (
                  <div key={d.name} style={{ display: "flex", alignItems: "center",
                    justifyContent: "space-between", fontSize: 11 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
                        background: RISK_COLORS[d.name] || "#94a3b8", display: "inline-block" }} />
                      <span style={{ color: C.sub }}>{d.name}</span>
                    </div>
                    <span style={{ color: C.text, fontWeight: 600 }}>{d.value.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 分割线 */}
          <div style={{ borderTop: `1px solid ${C.border}` }} />

          {/* 各州分布 */}
          <div>
            <p style={{ fontSize: 12, fontWeight: 700, color: C.sub, margin: "0 0 8px" }}>🗺️ 各州房产数量</p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
              {(stats.state_distribution as { state: string; count: number }[]).map(s => (
                <a key={s.state} href={`/listings?state=${s.state}`} style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "6px 10px", borderRadius: 8, fontSize: 11, textDecoration: "none",
                  border: `1px solid ${C.border}`, background: C.bg, color: C.text,
                  transition: "all 0.15s",
                }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLElement).style.background = "#eef2ff";
                    (e.currentTarget as HTMLElement).style.borderColor = "#a5b4fc";
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLElement).style.background = C.bg;
                    (e.currentTarget as HTMLElement).style.borderColor = C.border;
                  }}
                >
                  <span style={{ fontWeight: 700, color: C.text }}>{s.state}</span>
                  <span style={{ color: C.muted }}>{s.count.toLocaleString()}</span>
                </a>
              ))}
            </div>
          </div>

        </div>
      </aside>

      {/* ══ 右侧大地图 ═════════════════════════════════════════ */}
      <div style={{ flex: 1, position: "relative" }}>
        {/* 图例浮层 */}
        <div style={{
          position: "absolute", bottom: 24, right: 12, zIndex: 500,
          background: "rgba(255,255,255,0.95)", backdropFilter: "blur(8px)",
          border: `1px solid ${C.border}`, borderRadius: 12,
          padding: "10px 14px", boxShadow: "0 2px 12px rgba(0,0,0,0.1)",
        }}>
          <p style={{ fontSize: 10, color: C.muted, marginBottom: 8, marginTop: 0,
            textTransform: "uppercase" as const, letterSpacing: "0.06em", fontWeight: 600 }}>
            风险等级
          </p>
          {MAP_LEGEND.map(l => (
            <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 8,
              fontSize: 11, color: C.sub, marginBottom: 4 }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%",
                background: l.color, flexShrink: 0, display: "inline-block" }} />
              {l.label}
            </div>
          ))}
          <p style={{ fontSize: 10, color: C.muted, marginBottom: 0, marginTop: 8 }}>
            {markers.length.toLocaleString()} 个标记
          </p>
        </div>

        {/* 地图 */}
        <div style={{ width: "100%", height: "100%" }}>
          <RiskMap markers={markers} />
        </div>
      </div>

    </div>
  );
}
