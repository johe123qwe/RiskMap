"use client";
import { useEffect, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import PropertyCard from "@/components/PropertyCard";

const STATES = ["TX","CA","FL","NY","PA","OH","NC","IN","MN","AZ"];
const RISK_LABELS = ["极高风险","较高风险","中等风险","较低风险","低风险"];
const SORT_OPTIONS = [
  { value: "risk_score", label: "风险分（高→低）" },
  { value: "price", label: "价格（高→低）" },
  { value: "area_sqft", label: "面积（大→小）" },
  { value: "elevation_ft", label: "海拔（高→低）" },
  { value: "fema_total", label: "灾难总次数" },
];

export default function ListingsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // 过滤状态
  const [state, setState] = useState(searchParams.get("state") || "");
  const [riskLabel, setRiskLabel] = useState(searchParams.get("risk_label") || "");
  const [minPrice, setMinPrice] = useState(searchParams.get("min_price") || "");
  const [maxPrice, setMaxPrice] = useState(searchParams.get("max_price") || "");
  const [sortBy, setSortBy] = useState("risk_score");
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    const params: Record<string, string | number> = {
      page, page_size: 24, sort_by: sortBy, sort_dir: "desc",
    };
    if (state) params.state = state;
    if (riskLabel) params.risk_label = riskLabel;
    if (minPrice) params.min_price = Number(minPrice);
    if (maxPrice) params.max_price = Number(maxPrice);

    const qs = new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)])
    );
    try {
      const res = await fetch(`/api/listings?${qs}`);
      if (!res.ok) throw new Error("API returned " + res.status);
      const json = await res.json();
      setData(json);
    } catch (e) {
      setData({ items: [], total: 0 }); // Fallback on error
    } finally {
      setLoading(false);
    }
  }, [state, riskLabel, minPrice, maxPrice, sortBy, page]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <h1 className="text-2xl font-bold text-white mb-6">房产列表</h1>

      {/* 过滤栏 */}
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 mb-6 flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">州</label>
          <select
            value={state}
            onChange={(e) => { setState(e.target.value); setPage(1); }}
            className="bg-gray-800 border border-gray-700 text-sm text-gray-200 rounded-lg px-3 py-2"
          >
            <option value="">全部</option>
            {STATES.map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs text-gray-500 mb-1">风险等级</label>
          <select
            value={riskLabel}
            onChange={(e) => { setRiskLabel(e.target.value); setPage(1); }}
            className="bg-gray-800 border border-gray-700 text-sm text-gray-200 rounded-lg px-3 py-2"
          >
            <option value="">全部</option>
            {RISK_LABELS.map((l) => <option key={l}>{l}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs text-gray-500 mb-1">最低价格 ($)</label>
          <input
            type="number" value={minPrice} placeholder="100000"
            onChange={(e) => { setMinPrice(e.target.value); setPage(1); }}
            className="bg-gray-800 border border-gray-700 text-sm text-gray-200 rounded-lg px-3 py-2 w-32"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">最高价格 ($)</label>
          <input
            type="number" value={maxPrice} placeholder="2000000"
            onChange={(e) => { setMaxPrice(e.target.value); setPage(1); }}
            className="bg-gray-800 border border-gray-700 text-sm text-gray-200 rounded-lg px-3 py-2 w-32"
          />
        </div>

        <div>
          <label className="block text-xs text-gray-500 mb-1">排序</label>
          <select
            value={sortBy}
            onChange={(e) => { setSortBy(e.target.value); setPage(1); }}
            className="bg-gray-800 border border-gray-700 text-sm text-gray-200 rounded-lg px-3 py-2"
          >
            {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        <button
          onClick={() => { setState(""); setRiskLabel(""); setMinPrice(""); setMaxPrice(""); setPage(1); }}
          className="text-sm text-gray-400 hover:text-white underline ml-auto"
        >
          重置
        </button>
      </div>

      {/* 结果统计 */}
      {data && (
        <p className="text-sm text-gray-500 mb-4">
          共 <strong className="text-gray-200">{data.total.toLocaleString()}</strong> 条结果，
          第 {page} / {data.total_pages} 页
        </p>
      )}

      {/* 卡片网格 */}
      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-2xl h-72 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {data?.items?.map((item: any) => (
            <PropertyCard key={item.zpid} item={item} />
          ))}
        </div>
      )}

      {/* 分页 */}
      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-8">
          <button
            disabled={page === 1}
            onClick={() => setPage(p => p - 1)}
            className="px-4 py-2 bg-gray-800 text-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-700 transition-colors text-sm"
          >
            上一页
          </button>
          <span className="text-gray-500 text-sm">
            {page} / {data.total_pages}
          </span>
          <button
            disabled={page === data.total_pages}
            onClick={() => setPage(p => p + 1)}
            className="px-4 py-2 bg-gray-800 text-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-700 transition-colors text-sm"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
