import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api, imgUrl } from "../lib/api";
import { WorkerLayout } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Play, Pause, LogOut as PunchOut, Sparkles, Coffee, Timer, Package, Download, X } from "lucide-react";

const fmtMin = (m = 0) => {
  const h = Math.floor(m / 60), mm = m % 60;
  return `${h}h ${mm}m`;
};

export default function WorkerDashboard() {
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [category, setCategory] = useState("");
  const [generating, setGenerating] = useState(false);
  const [latest, setLatest] = useState(null);
  const [processing, setProcessing] = useState({});

  const load = useCallback(async () => {
    const [s, p, c] = await Promise.all([
      api.get("/attendance/me"),
      api.get("/products?mine=true&limit=20"),
      api.get("/admin/categories").catch(() => ({ data: [] })),
    ]);
    setStatus(s.data);
    setProducts(p.data);
    setCategories(c.data || []);
    if (c.data?.length && !category) setCategory(c.data[0].name);
  }, [category]);

  useEffect(() => { load(); }, [load]);

  // heartbeat every 60s while active
  useEffect(() => {
    const h = setInterval(() => { api.post("/attendance/heartbeat").catch(() => {}); load(); }, 60000);
    return () => clearInterval(h);
  }, [load]);

  const call = async (path, ok) => {
    try { await api.post(path); toast.success(ok); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Action failed"); }
  };

  const generate = async () => {
    if (!status?.attendance) { toast.error("Punch in first."); return; }
    setGenerating(true); setLatest(null);
    try {
      const r = await api.post("/products/generate", { category: category || undefined });
      setLatest(r.data);
      toast.success(`Generated: ${r.data.name}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Generation failed");
    } finally { setGenerating(false); }
  };

  const handleDownload = async (imageId) => {
    try {
      const r = await api.get(`/images/${imageId}/download`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([r.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `product_${latest?.id}_image.png`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (e) {
      toast.error("Download failed");
    }
  };

  const handleRefine = async () => {
    if (!latest?.id) return;
    setProcessing((p) => ({ ...p, refine: true }));
    try {
      await api.post(`/products/${latest.id}/refine-image`);
      toast.success("Image refined successfully");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Refine failed");
    } finally {
      setProcessing((p) => ({ ...p, refine: false }));
    }
  };

  const handleGenerateViews = async () => {
    if (!latest?.id) return;
    setProcessing((p) => ({ ...p, views: true }));
    try {
      await api.post(`/products/${latest.id}/generate-views`);
      toast.success("AI views generated successfully");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "View generation failed");
    } finally {
      setProcessing((p) => ({ ...p, views: false }));
    }
  };

  const handleSkip = async () => {
    if (!latest?.id) return;
    if (!confirm("Skip this image? It will be returned to the available pool.")) return;
    setProcessing((p) => ({ ...p, skip: true }));
    try {
      await api.post(`/products/${latest.id}/skip-image`);
      toast.success("Image skipped");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Skip failed");
    } finally {
      setProcessing((p) => ({ ...p, skip: false }));
    }
  };

  const handleComplete = async () => {
    if (!latest?.id) return;
    setProcessing((p) => ({ ...p, complete: true }));
    try {
      await api.post(`/products/${latest.id}/complete`);
      toast.success("Product completed");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Complete failed");
    } finally {
      setProcessing((p) => ({ ...p, complete: false }));
    }
  };

  const onBreak = !!status?.open_break;
  const punchedIn = !!status?.attendance;
  const idleWarn = status?.idle_in_seconds != null && status.idle_in_seconds < (status.warning_seconds || 300);

  return (
    <WorkerLayout>
      <div className="space-y-8">
        <section className="flex items-end justify-between flex-wrap gap-4">
          <div>
            <div className="label-overline text-[#D4AF37]">Worker studio</div>
            <h1 className="font-display text-4xl lg:text-5xl mt-2">Today's session</h1>
          </div>
          <div className="flex gap-3">
            {!punchedIn && (
              <Button onClick={() => call("/attendance/punch-in", "Punched in")} data-testid="punch-in-btn"
                className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07] font-semibold"><Play className="w-4 h-4 mr-2"/>Punch in</Button>
            )}
            {punchedIn && !onBreak && (
              <Button onClick={() => call("/attendance/break/start", "Break started")} variant="outline" data-testid="break-start-btn" className="border-[#21362A]"><Coffee className="w-4 h-4 mr-2"/>Start break</Button>
            )}
            {punchedIn && onBreak && (
              <Button onClick={() => call("/attendance/break/end", "Break ended")} data-testid="break-end-btn" className="bg-[#097969] hover:bg-[#0a8a78]"><Pause className="w-4 h-4 mr-2"/>End break</Button>
            )}
            {punchedIn && (
              <Button onClick={() => call("/attendance/punch-out", "Punched out")} data-testid="punch-out-btn" className="bg-[#E63946] hover:bg-[#d72e3b] text-white font-semibold"><PunchOut className="w-4 h-4 mr-2"/>Punch out</Button>
            )}
          </div>
        </section>

        {idleWarn && punchedIn && !onBreak && (
          <div className="rounded-sm border border-[#D4AF37]/40 bg-[#D4AF37]/10 p-4 text-sm text-[#F0C84A]" data-testid="idle-warning">
            <Timer className="inline w-4 h-4 mr-2"/> You&apos;re nearing idle timeout. Generate a product or interact to stay active.
          </div>
        )}

        <section className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <StatCard label="Status" value={!punchedIn ? "Punched out" : onBreak ? "On break" : "Active"} data-testid="stat-status" />
          <StatCard label="Hours today" value={fmtMin(status?.total_today_minutes || 0)} data-testid="stat-hours" />
          <StatCard label="Products today" value={status?.products_today || 0} data-testid="stat-products-today" />
          <StatCard label="Idle timeout" value={`${status?.idle_timeout_minutes || 60}m`} data-testid="stat-idle-timeout" />
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2 bg-[#0C140F] border-[#21362A] rounded-sm">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="font-display text-2xl">Generate product</CardTitle>
              <div className="w-56">
                <Select value={category} onValueChange={setCategory}>
                  <SelectTrigger className="bg-[#132018] border-[#21362A]" data-testid="category-select"><SelectValue placeholder="Category"/></SelectTrigger>
                  <SelectContent className="bg-[#0C140F] border-[#21362A] text-white">
                    {categories.map((c) => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col md:flex-row items-stretch gap-6">
                <div className="md:w-56 aspect-square bg-[#132018] border border-[#21362A] rounded-sm flex items-center justify-center overflow-hidden">
                  {latest?.image_asset_id ? (
                    <img src={imgUrl(latest.image_asset_id)} alt="assigned" className="w-full h-full object-cover"/>
                  ) : (
                    <div className="text-center text-[#A1B4A8] text-sm p-6">Click generate to get an AI product draft with an auto-assigned image.</div>
                  )}
                </div>
                <div className="flex-1 space-y-4">
                  <Button onClick={generate} disabled={generating || !punchedIn} data-testid="generate-product-btn"
                    className="w-full h-12 bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07] font-semibold tracking-wide">
                    <Sparkles className="w-4 h-4 mr-2"/>{generating ? "Crafting draft…" : "Generate product"}
                  </Button>
                  {latest && (
                    <>
                      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3 p-4 border border-[#21362A] rounded-sm bg-[#050A07]" data-testid="latest-product">
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="label-overline">Product name</div>
                            <div className="font-display text-2xl mt-1">{latest.name}</div>
                          </div>
                          <div className="text-right">
                            <div className="label-overline">Price</div>
                            <div className="font-display text-3xl text-[#D4AF37]">${latest.final_price}</div>
                          </div>
                        </div>
                        <div className="text-sm text-[#A1B4A8]">{latest.short_description}</div>
                        <div className="text-xs text-[#A1B4A8] whitespace-pre-line">{latest.full_description}</div>
                        <div className="flex gap-2 flex-wrap">
                          {latest.tags?.map((t) => <Badge key={t} className="bg-[#132018] text-[#A1B4A8] border border-[#21362A]">{t}</Badge>)}
                        </div>
                        <div className="flex gap-2 text-xs text-[#A1B4A8]">Sizes: {latest.sizes?.join(", ")}</div>
                      </motion.div>
                      
                      {/* Workflow buttons */}
                      <div className="grid grid-cols-2 gap-2">
                        {latest.image_asset_id && (
                          <Button onClick={() => handleDownload(latest.image_asset_id)} variant="outline" className="border-[#21362A] text-[#A1B4A8]">
                            <Download className="w-4 h-4 mr-2"/>Download Image
                          </Button>
                        )}
                        <Button onClick={() => navigate(`/products/${latest.id}`)} variant="outline" className="border-[#21362A] text-[#A1B4A8]">
                          Review Image
                        </Button>
                        <Button onClick={handleRefine} disabled={processing.refine || latest.image_workflow_status !== "assigned"} className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]">
                          <Sparkles className="w-4 h-4 mr-2"/>{processing.refine ? "Refining..." : "Refine Image"}
                        </Button>
                        <Button onClick={handleGenerateViews} disabled={processing.views || (latest.image_workflow_status !== "refined" && latest.image_workflow_status !== "assigned")} className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]">
                          <Sparkles className="w-4 h-4 mr-2"/>{processing.views ? "Generating..." : "Create 2 AI Views"}
                        </Button>
                        <Button onClick={handleSkip} disabled={processing.skip || latest.image_workflow_status !== "assigned"} variant="outline" className="border-[#21362A] text-[#A1B4A8]">
                          <X className="w-4 h-4 mr-2"/>{processing.skip ? "Skipping..." : "Skip Image"}
                        </Button>
                        <Button onClick={handleComplete} disabled={processing.complete || (latest.image_workflow_status !== "refined" && latest.image_workflow_status !== "variation-created")} className="bg-[#097969] hover:bg-[#0a8a78]">
                          {processing.complete ? "Saving..." : "Save Product Record"}
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
            <CardHeader><CardTitle className="font-display text-2xl">Recent products</CardTitle></CardHeader>
            <CardContent className="space-y-3" data-testid="recent-products">
              {products.length === 0 && <div className="text-sm text-[#A1B4A8]">Nothing yet — generate your first product.</div>}
              {products.slice(0, 8).map((p) => (
                <div 
                  key={p.id} 
                  onClick={() => navigate(`/products/${p.id}`)}
                  className="flex items-center gap-3 p-2 rounded-sm border border-transparent hover:border-[#21362A] cursor-pointer"
                >
                  <Package className="w-4 h-4 text-[#D4AF37]"/>
                  <div className="flex-1 min-w-0">
                    <div className="truncate text-sm">{p.name}</div>
                    <div className="text-xs text-[#A1B4A8] truncate">{p.category}</div>
                  </div>
                  <div className="font-display text-[#D4AF37]">${p.final_price}</div>
                </div>
              ))}
            </CardContent>
          </Card>
        </section>
      </div>
    </WorkerLayout>
  );
}

function StatCard({ label, value, ...rest }) {
  return (
    <Card className="bg-[#0C140F] border-[#21362A] rounded-sm" {...rest}>
      <CardContent className="p-5">
        <div className="label-overline">{label}</div>
        <div className="font-display text-3xl mt-2">{value}</div>
      </CardContent>
    </Card>
  );
}
