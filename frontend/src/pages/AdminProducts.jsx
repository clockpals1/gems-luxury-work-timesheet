import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Card, CardContent } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import ProductDetailDialog from "../components/ProductDetailDialog";

export default function AdminProducts() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("all");
  const [openId, setOpenId] = useState(null);

  const load = async () => {
    const r = await api.get("/products?limit=500");
    setItems(r.data);
  };
  useEffect(() => { load(); }, []);

  const doExport = async (id) => { try { await api.post(`/products/${id}/export`); toast.success("Marked exported"); load(); } catch { toast.error("Failed"); } };

  const exportCsv = () => {
    const rows = [["Name","Category","Worker","Price","Status","GeneratedAt"], ...items.map((p) => [p.name, p.category, p.generated_by_name, p.final_price, p.status, p.generated_at])];
    const csv = rows.map((r) => r.map((c) => `"${String(c ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "products.csv"; a.click();
  };

  const filtered = filter === "all" ? items : items.filter((p) => p.status === filter);

  return (
    <AdminLayout>
      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="label-overline text-[#D4AF37]">Catalog</div>
          <h1 className="font-display text-4xl mt-2">Products</h1>
        </div>
        <div className="flex gap-2">
          {["all","draft","reviewed","exported"].map((s) => (
            <Button key={s} variant={filter === s ? "default" : "outline"} size="sm" onClick={() => setFilter(s)} data-testid={`filter-${s}`}
              className={filter === s ? "bg-[#D4AF37] text-[#050A07] hover:bg-[#F0C84A]" : "border-[#21362A]"}>{s}</Button>
          ))}
          <Button onClick={exportCsv} variant="outline" size="sm" data-testid="export-csv-btn" className="border-[#21362A]">Export CSV</Button>
        </div>
      </div>
      <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
        <CardContent className="p-0">
          <table className="w-full text-sm" data-testid="products-table">
            <thead className="text-[#A1B4A8] text-xs uppercase tracking-widest">
              <tr><th className="text-left p-4">Name</th><th className="text-left">Category</th><th className="text-left">Worker</th><th className="text-left">Pricing</th><th className="text-right">Price</th><th className="text-left pl-4">Status</th><th className="p-4 text-right">Actions</th></tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <tr key={p.id} className="border-t border-[#21362A]">
                  <td className="p-4">
                    <div>{p.name}</div>
                    <div className="text-xs text-[#A1B4A8] truncate max-w-md">{p.short_description}</div>
                  </td>
                  <td className="text-[#A1B4A8]">{p.category}</td>
                  <td className="text-[#A1B4A8]">{p.generated_by_name}</td>
                  <td className="text-[#A1B4A8] text-xs max-w-[220px]">
                    {p.pricing_meta ? `${p.pricing_meta.occasionTier} · Q${p.pricing_meta.perceivedQuality}/C${p.pricing_meta.complexity}` : "—"}
                  </td>
                  <td className="text-right font-display text-[#D4AF37]">${p.final_price}</td>
                  <td className="pl-4"><Badge className="bg-[#132018] border border-[#21362A] text-[#A1B4A8]">{p.status}</Badge></td>
                  <td className="p-4 text-right space-x-2">
                    <Button size="sm" variant="outline" className="border-[#21362A]" onClick={() => setOpenId(p.id)} data-testid={`view-${p.id}`}>View</Button>
                    {p.status !== "exported" && <Button size="sm" variant="outline" onClick={() => doExport(p.id)} className="border-[#21362A]" data-testid={`export-${p.id}`}>Export</Button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
      <ProductDetailDialog id={openId} open={!!openId} onOpenChange={(v) => !v && setOpenId(null)} onSaved={() => { load(); }} />
    </AdminLayout>
  );
}
