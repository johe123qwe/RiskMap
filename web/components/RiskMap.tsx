"use client";
import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { scoreToColor } from "@/lib/utils";

interface Marker {
  zpid: string;
  latitude: number;
  longitude: number;
  risk_score: number | null;
  risk_label: string | null;
  price: number | null;
  address: string | null;
  city: string | null;
  state: string | null;
  beds: number | null;
  baths: number | null;
  area_sqft: number | null;
}

interface Props {
  markers: Marker[];
}

// ── 纯函数：清空旧标记并重新添加 ──────────────────────────────
function renderMarkers(L: any, map: any, markers: Marker[]) {
  map.eachLayer((layer: any) => {
    if (layer instanceof L.CircleMarker) map.removeLayer(layer);
  });

  markers.forEach((m) => {
    if (!m.latitude || !m.longitude) return;
    const color = scoreToColor(m.risk_score);
    const radius = m.risk_score ? 4 + (m.risk_score / 100) * 6 : 5;

    const circle = L.circleMarker([m.latitude, m.longitude], {
      radius,
      fillColor: color,
      color: "#fff",
      weight: 1,
      opacity: 0.9,
      fillOpacity: 0.75,
    });

    const price = m.price
      ? m.price >= 1_000_000
        ? `$${(m.price / 1_000_000).toFixed(1)}M`
        : `$${(m.price / 1_000).toFixed(0)}K`
      : "—";

    circle.bindPopup(`
      <div style="min-width:200px;font-family:system-ui">
        <div style="font-weight:600;margin-bottom:4px;font-size:13px">${m.address || "未知地址"}</div>
        <div style="font-size:12px;color:#555">${m.city || ""}, ${m.state || ""}</div>
        <hr style="margin:6px 0;border-color:#e5e7eb"/>
        <div style="display:flex;justify-content:space-between;font-size:12px">
          <span>价格</span><strong>${price}</strong>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:12px">
          <span>风险分</span>
          <strong style="color:${color}">${m.risk_score ?? "—"} / 100</strong>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:12px">
          <span>风险等级</span><strong>${m.risk_label ?? "—"}</strong>
        </div>
        ${m.beds ? `<div style="font-size:12px;margin-top:4px;color:#777">${m.beds}床 · ${m.baths}浴 · ${m.area_sqft?.toLocaleString() ?? "—"} sqft</div>` : ""}
        <div style="margin-top:8px">
          <a href="/listings/${m.zpid}" style="color:#3b82f6;font-size:12px;text-decoration:underline">查看详情 →</a>
        </div>
      </div>
    `);

    circle.addTo(map);
  });
}

export default function RiskMap({ markers }: Props) {
  const mapRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  // 始终持有最新 markers 的 ref，供异步回调使用
  const markersRef = useRef<Marker[]>(markers);
  const router = useRouter();

  // ── Effect 1：初始化地图（只跑一次）────────────────────────
  useEffect(() => {
    if (typeof window === "undefined") return;

    let cancelled = false;

    import("leaflet").then((L) => {
      if (cancelled || mapRef.current) return;

      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      });

      const map = L.map(containerRef.current!, {
        center: [38.5, -96],
        zoom: 4,
        zoomControl: true,
      });

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors",
        maxZoom: 19,
      }).addTo(map);

      mapRef.current = map;

      // 地图初始化完成后立即渲染当时最新的 markers
      renderMarkers(L, map, markersRef.current);
    });

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []); // 空依赖，只在 mount/unmount 执行

  // ── Effect 2：markers 变化时同步并刷新────────────────────
  useEffect(() => {
    markersRef.current = markers; // 先同步最新值
    const map = mapRef.current;
    if (!map) return; // 地图未就绪时 Effect 1 的 Promise 会处理

    import("leaflet").then((L) => {
      renderMarkers(L, map, markers);
    });
  }, [markers]);

  // ── Effect 3：拦截 Popup 中的 A 标签点击，改为 Next.js 软路由
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      // 查找点击的元素或其父元素是否是 A 标签
      const aTag = target.closest("a");
      if (aTag && aTag.getAttribute("href")?.startsWith("/listings/")) {
        e.preventDefault();
        router.push(aTag.getAttribute("href")!);
      }
    };

    container.addEventListener("click", handleClick);
    return () => container.removeEventListener("click", handleClick);
  }, [router]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full rounded-xl overflow-hidden"
      id="risk-map"
    />
  );
}
