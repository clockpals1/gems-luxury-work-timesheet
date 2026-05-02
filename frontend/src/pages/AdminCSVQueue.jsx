import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Download, Check, X, Filter } from "lucide-react";

export default function AdminCSVQueue() {
  const navigate = useNavigate();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(new Set());
  const [filters, setFilters] = useState({
    worker_id: "",
    category: "",
    export_status: "all",
    image_status: "all"
  });
  const [exporting, setExporting] = useState(false);
  const [exportLogs, setExportLogs] = useState([]);

  useEffect(() => {
    loadProducts();
    loadExportLogs();
  }, [filters]);

  const loadExportLogs = async () => {
    try {
      const r = await api.get("/admin/export-logs");
      setExportLogs(r.data);
    } catch (e) {
      // Export logs might not exist yet, ignore error
    }
  };

  const loadProducts = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.worker_id) params.append("worker_id", filters.worker_id);
      if (filters.category) params.append("category", filters.category);
      if (filters.export_status !== "all") params.append("export_status", filters.export_status);
      
      const r = await api.get(`/products?${params.toString()}`);
      setProducts(r.data);
    } catch (e) {
      toast.error("Failed to load products");
    } finally {
      setLoading(false);
    }
  };

  const handleExportCSV = async () => {
    setExporting(true);
    try {
      const r = await api.get("/products/export/csv", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([r.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "products_export.csv");
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success("CSV exported successfully");
      loadProducts();
      loadExportLogs();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Export failed");
    } finally {
      setExporting(false);
    }
  };

  const handlePreviewCSV = async () => {
    setExporting(true);
    try {
      const r = await api.get("/products/export/preview");
      const previewWindow = window.open("", "_blank");
      previewWindow.document.write(`<pre>${r.data.preview}</pre>`);
      toast.success(`Preview loaded (${r.data.preview_products} of ${r.data.total_products} products)`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Preview failed");
    } finally {
      setExporting(false);
    }
  };

  const handleApproveSelected = async () => {
    const selectedArray = Array.from(selected);
    if (selectedArray.length === 0) {
      toast.error("No products selected");
      return;
    }
    try {
      await api.post("/products/approve-batch", { product_ids: selectedArray });
      toast.success(`Approved ${selectedArray.length} products`);
      setSelected(new Set());
      loadProducts();
    } catch (e) {
      toast.error("Failed to approve products");
    }
  };

  const handleRejectSelected = async () => {
    const selectedArray = Array.from(selected);
    if (selectedArray.length === 0) {
      toast.error("No products selected");
      return;
    }
    try {
      await api.post("/products/reject-batch", { product_ids: selectedArray });
      toast.success(`Rejected ${selectedArray.length} products`);
      setSelected(new Set());
      loadProducts();
    } catch (e) {
      toast.error("Failed to reject products");
    }
  };

  const toggleSelect = (id) => {
    const newSelected = new Set(selected);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelected(newSelected);
  };

  const toggleSelectAll = () => {
    if (selected.size === products.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(products.map(p => p.id)));
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      pending: "bg-gray-500/20 text-gray-300",
      approved: "bg-green-500/20 text-green-300",
      exported: "bg-blue-500/20 text-blue-300",
      rejected: "bg-red-500/20 text-red-300"
    };
    return colors[status] || "bg-gray-500/20 text-gray-300";
  };

  if (loading) return <AdminLayout><div className="text-[#A1B4A8]">Loading...</div></AdminLayout>;

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <div className="label-overline text-[#D4AF37]">Export Management</div>
          <h1 className="font-display text-4xl mt-2">CSV Queue</h1>
        </div>

        {/* Filters */}
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardHeader><CardTitle className="font-display text-xl flex items-center gap-2"><Filter className="w-5 h-5"/>Filters</CardTitle></CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-4 gap-4">
              <div className="space-y-2">
                <label className="label-overline text-xs">Worker ID</label>
                <Input 
                  value={filters.worker_id} 
                  onChange={(e) => setFilters({ ...filters, worker_id: e.target.value })}
                  placeholder="Filter by worker..."
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <label className="label-overline text-xs">Category</label>
                <Input 
                  value={filters.category} 
                  onChange={(e) => setFilters({ ...filters, category: e.target.value })}
                  placeholder="Filter by category..."
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <label className="label-overline text-xs">Export Status</label>
                <Select value={filters.export_status} onValueChange={(v) => setFilters({ ...filters, export_status: v })}>
                  <SelectTrigger className="bg-[#132018] border-[#21362A]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="approved">Approved</SelectItem>
                    <SelectItem value="exported">Exported</SelectItem>
                    <SelectItem value="rejected">Rejected</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <label className="label-overline text-xs">Image Status</label>
                <Select value={filters.image_status} onValueChange={(v) => setFilters({ ...filters, image_status: v })}>
                  <SelectTrigger className="bg-[#132018] border-[#21362A]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="assigned">Assigned</SelectItem>
                    <SelectItem value="refined">Refined</SelectItem>
                    <SelectItem value="variation-created">Variations Created</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Bulk Actions */}
        <div className="flex gap-3">
          <Button onClick={handleApproveSelected} disabled={selected.size === 0} className="bg-[#097969] hover:bg-[#0a8a78]">
            <Check className="w-4 h-4 mr-2"/>Approve Selected ({selected.size})
          </Button>
          <Button onClick={handleRejectSelected} disabled={selected.size === 0} variant="outline" className="border-[#21362A] text-[#A1B4A8]">
            <X className="w-4 h-4 mr-2"/>Reject Selected ({selected.size})
          </Button>
          <Button onClick={handlePreviewCSV} disabled={exporting} variant="outline" className="border-[#21362A] text-[#A1B4A8]">
            Preview CSV
          </Button>
          <Button onClick={handleExportCSV} disabled={exporting} className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]">
            <Download className="w-4 h-4 mr-2"/>{exporting ? "Exporting..." : "Export CSV"}
          </Button>
        </div>

        {/* Product List */}
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardHeader><CardTitle className="font-display text-xl">Products ({products.length})</CardTitle></CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#21362A]">
                    <th className="text-left p-3">
                      <input type="checkbox" checked={selected.size === products.length} onChange={toggleSelectAll} className="w-4 h-4"/>
                    </th>
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">Name</th>
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">SKU</th>
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">Worker</th>
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">Category</th>
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">Price</th>
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">Export Status</th>
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">Image Status</th>
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">Generated</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((p) => (
                    <tr key={p.id} className="border-b border-[#21362A]/50 hover:bg-[#132018]/50 cursor-pointer" onClick={(e) => { if (e.target.type !== 'checkbox') navigate(`/admin/products/${p.id}`); }}>
                      <td className="p-3" onClick={(e) => e.stopPropagation()}>
                        <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggleSelect(p.id)} className="w-4 h-4"/>
                      </td>
                      <td className="p-3 text-sm">{p.name}</td>
                      <td className="p-3 text-sm text-[#A1B4A8]">{p.sku || "-"}</td>
                      <td className="p-3 text-sm text-[#A1B4A8]">{p.generated_by_name}</td>
                      <td className="p-3 text-sm text-[#A1B4A8]">{p.category}</td>
                      <td className="p-3 text-sm text-[#D4AF37]">${p.final_price}</td>
                      <td className="p-3"><Badge className={getStatusColor(p.export_status || "pending")}>{p.export_status || "pending"}</Badge></td>
                      <td className="p-3"><Badge className="bg-[#132018] text-[#A1B4A8] border border-[#21362A]">{p.image_workflow_status || "assigned"}</Badge></td>
                      <td className="p-3 text-xs text-[#A1B4A8]">{new Date(p.generated_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Export Logs */}
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardHeader><CardTitle className="font-display text-xl">Export History</CardTitle></CardHeader>
          <CardContent>
            {exportLogs.length === 0 ? (
              <div className="text-sm text-[#A1B4A8]">No exports yet.</div>
            ) : (
              <div className="space-y-2">
                {exportLogs.map((log) => (
                  <div key={log.id} className="flex items-center justify-between p-3 border border-[#21362A] rounded-sm">
                    <div>
                      <div className="text-sm">{log.exported_by_name}</div>
                      <div className="text-xs text-[#A1B4A8]">{log.product_count} products • {new Date(log.exported_at).toLocaleString()}</div>
                    </div>
                    <Badge className="bg-[#097969]/20 text-[#2A9D8F]">{log.status}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AdminLayout>
  );
}
