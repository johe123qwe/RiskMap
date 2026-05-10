// 风险评分配色
export const RISK_COLORS: Record<string, string> = {
  极高风险: "#dc2626",
  较高风险: "#f97316",
  中等风险: "#eab308",
  较低风险: "#22c55e",
  低风险:   "#3b82f6",
};

export const RISK_BG: Record<string, string> = {
  极高风险: "bg-red-600",
  较高风险: "bg-orange-500",
  中等风险: "bg-yellow-500",
  较低风险: "bg-green-500",
  低风险:   "bg-blue-500",
};

// 分数 → 颜色
export function scoreToColor(score: number | null): string {
  if (score === null || score === undefined) return "#6b7280";
  if (score >= 80) return "#dc2626";
  if (score >= 60) return "#f97316";
  if (score >= 40) return "#eab308";
  if (score >= 20) return "#22c55e";
  return "#3b82f6";
}

// 分数 → Tailwind ring 颜色
export function scoreToRing(score: number | null): string {
  if (score === null || score === undefined) return "ring-gray-400";
  if (score >= 80) return "ring-red-500";
  if (score >= 60) return "ring-orange-500";
  if (score >= 40) return "ring-yellow-400";
  if (score >= 20) return "ring-green-500";
  return "ring-blue-500";
}

export function formatPrice(price: number | null): string {
  if (!price) return "—";
  if (price >= 1_000_000) return `$${(price / 1_000_000).toFixed(1)}M`;
  if (price >= 1_000) return `$${(price / 1_000).toFixed(0)}K`;
  return `$${price}`;
}
