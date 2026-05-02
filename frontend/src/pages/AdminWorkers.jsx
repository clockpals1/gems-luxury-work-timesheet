import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Filter, Package, Check, X } from "lucide-react";

export default function AdminWorkers() {
  const [workers, setWorkers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    date_from: "",
    date_to: "",
    worker_id: ""
  });

  useEffect(() => {
    loadWorkers();
  }, [filters]);

  const loadWorkers = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.date_from) params.append("date_from", filters.date_from);
      if (filters.date_to) params.append("date_to", filters.date_to);
      if (filters.worker_id) params.append("worker_id", filters.worker_id);
      
      const r = await api.get(`/admin/workers/productivity?${params.toString()}`);
      setWorkers(r.data);
    } catch (e) {
      toast.error("Failed to load worker productivity");
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <AdminLayout><div className="text-[#A1B4A8]">Loading...</div></AdminLayout>;

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <div className="label-overline text-[#D4AF37]">Worker Tracking</div>
          <h1 className="font-display text-4xl mt-2">Productivity Metrics</h1>
        </div>

        {/* Filters */}
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardHeader><CardTitle className="font-display text-xl flex items-center gap-2"><Filter className="w-5 h-5"/>Filters</CardTitle></CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <label className="label-overline text-xs">Date From</label>
                <Input 
                  type="date"
                  value={filters.date_from} 
                  onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <label className="label-overline text-xs">Date To</label>
                <Input 
                  type="date"
                  value={filters.date_to} 
                  onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <label className="label-overline text-xs">Worker</label>
                <Input 
                  value={filters.worker_id} 
                  onChange={(e) => setFilters({ ...filters, worker_id: e.target.value })}
                  placeholder="Filter by worker ID..."
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Worker Productivity Table */}
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardHeader><CardTitle className="font-display text-xl">Worker Productivity ({workers.length})</CardTitle></CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#21362A]">
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">Worker Name</th>
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">Worker ID</th>
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">Products Generated</th>
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">Approved for Export</th>
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">Rejected</th>
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">Images Reviewed</th>
                    <th className="text-left p-3 text-xs text-[#A1B4A8]">Approval Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {workers.map((w) => (
                    <tr key={w.worker_id} className="border-b border-[#21362A]/50 hover:bg-[#132018]/50">
                      <td className="p-3 text-sm">{w.worker_name}</td>
                      <td className="p-3 text-sm text-[#A1B4A8]">{w.worker_id}</td>
                      <td className="p-3 text-sm">
                        <div className="flex items-center gap-2">
                          <Package className="w-4 h-4 text-[#D4AF37]"/>
                          {w.products_generated || 0}
                        </div>
                      </td>
                      <td className="p-3 text-sm">
                        <div className="flex items-center gap-2">
                          <Check className="w-4 h-4 text-[#097969]"/>
                          {w.products_approved || 0}
                        </div>
                      </td>
                      <td className="p-3 text-sm">
                        <div className="flex items-center gap-2">
                          <X className="w-4 h-4 text-[#E63946]"/>
                          {w.products_rejected || 0}
                        </div>
                      </td>
                      <td className="p-3 text-sm text-[#A1B4A8]">{w.images_reviewed || 0}</td>
                      <td className="p-3">
                        <Badge className={w.approval_rate >= 80 ? "bg-[#097969]/20 text-[#2A9D8F]" : "bg-[#E63946]/20 text-[#E63946]"}>
                          {w.approval_rate || 0}%
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </AdminLayout>
  );
}
