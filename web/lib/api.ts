// 统一 API 请求层
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchStats() {
  const res = await fetch(`${API_BASE}/api/stats`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function fetchMapMarkers(state?: string) {
  const url = state
    ? `${API_BASE}/api/map?state=${state}`
    : `${API_BASE}/api/map`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch map markers");
  return res.json();
}

export async function fetchListings(params: Record<string, string | number>) {
  const qs = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)])
  ).toString();
  const res = await fetch(`${API_BASE}/api/listings?${qs}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch listings");
  return res.json();
}

export async function fetchListingDetail(zpid: string) {
  const res = await fetch(`${API_BASE}/api/listings/${zpid}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Property not found");
  return res.json();
}
