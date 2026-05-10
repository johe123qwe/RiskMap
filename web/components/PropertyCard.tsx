"use client";
import Link from "next/link";
import { scoreToColor, formatPrice } from "@/lib/utils";

interface Props {
  item: {
    zpid: string;
    address: string | null;
    city: string | null;
    state: string | null;
    price: number | null;
    beds: number | null;
    baths: number | null;
    area_sqft: number | null;
    img_url: string | null;
    elevation_ft: number | null;
    risk_score: number | null;
    risk_label: string | null;
    fema_flood: number | null;
    fema_hurricane: number | null;
    fema_total: number | null;
    eq_max_mag: number | null;
  };
}

export default function PropertyCard({ item }: Props) {
  const color = scoreToColor(item.risk_score);

  return (
    <Link href={`/listings/${item.zpid}`} className="block group">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden hover:border-gray-600 hover:shadow-xl hover:shadow-black/40 transition-all duration-200 hover:-translate-y-0.5">
        {/* 图片 */}
        <div className="relative h-44 bg-gray-800 overflow-hidden">
          {item.img_url ? (
            <img
              src={item.img_url}
              alt={item.address || ""}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-600">
              <span className="text-4xl">🏠</span>
            </div>
          )}
          {/* 风险分徽章 */}
          <div
            className="absolute top-2 right-2 text-white text-xs font-bold px-2 py-1 rounded-lg shadow"
            style={{ backgroundColor: color }}
          >
            {item.risk_score ?? "—"} / 100
          </div>
          {/* 价格 */}
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-3 py-2">
            <span className="text-white font-bold text-lg">{formatPrice(item.price)}</span>
          </div>
        </div>

        {/* 正文 */}
        <div className="p-4">
          <p className="text-sm font-medium text-gray-100 truncate">{item.address}</p>
          <p className="text-xs text-gray-500 mt-0.5">{item.city}, {item.state}</p>

          {/* 房型 */}
          <div className="flex gap-3 mt-2 text-xs text-gray-400">
            {item.beds && <span>🛏 {item.beds}bd</span>}
            {item.baths && <span>🚿 {item.baths}ba</span>}
            {item.area_sqft && <span>📐 {item.area_sqft.toLocaleString()} sqft</span>}
          </div>

          {/* 灾难速览 */}
          <div className="mt-3 flex flex-wrap gap-1">
            {(item.fema_flood ?? 0) > 0 && (
              <span className="text-xs bg-blue-950 text-blue-300 px-2 py-0.5 rounded-full">
                洪水 {item.fema_flood}次
              </span>
            )}
            {(item.fema_hurricane ?? 0) > 0 && (
              <span className="text-xs bg-red-950 text-red-300 px-2 py-0.5 rounded-full">
                飓风 {item.fema_hurricane}次
              </span>
            )}
            {item.eq_max_mag && (
              <span className="text-xs bg-orange-950 text-orange-300 px-2 py-0.5 rounded-full">
                M{item.eq_max_mag}地震
              </span>
            )}
            {item.elevation_ft && (
              <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded-full">
                {Math.round(item.elevation_ft)}ft
              </span>
            )}
          </div>

          {/* 风险等级条 */}
          <div className="mt-3 flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${item.risk_score ?? 0}%`, backgroundColor: color }}
              />
            </div>
            <span className="text-xs font-medium" style={{ color }}>
              {item.risk_label || "—"}
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}
