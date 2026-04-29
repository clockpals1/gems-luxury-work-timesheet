import React, { useEffect, useState } from "react";
import { api, imgUrl } from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Sparkles, Layers } from "lucide-react";
import { toast } from "sonner";

export default function ImageVariationsDialog({ id, open, onOpenChange }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    if (!id) return;
    const r = await api.get(`/admin/images/${id}/variations`);
    setData(r.data);
  };
  useEffect(() => { if (open) load(); /* eslint-disable-next-line */ }, [open, id]);

  const enhance = async () => {
    setBusy(true);
    try { toast.message("Enhancing… ~20s"); await api.post(`/admin/images/${id}/enhance`); toast.success("Enhanced"); await load(); }
    catch { toast.error("Failed"); }
    finally { setBusy(false); }
  };
  const alts = async () => {
    setBusy(true);
    try { toast.message("Generating alternates… ~30s"); await api.post(`/admin/images/${id}/alternates`); toast.success("Alternates ready"); await load(); }
    catch { toast.error("Failed"); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#0C140F] border-[#21362A] text-white max-w-5xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-3xl">{data?.source?.filename || "Image"}</DialogTitle>
          <div className="flex gap-2 pt-2">
            <Button size="sm" disabled={busy} onClick={enhance} className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]" data-testid="dlg-enhance"><Sparkles className="w-3 h-3 mr-1"/>Enhance</Button>
            <Button size="sm" disabled={busy} onClick={alts} variant="outline" className="border-[#21362A]" data-testid="dlg-alts"><Layers className="w-3 h-3 mr-1"/>Generate alternates</Button>
          </div>
        </DialogHeader>
        {data && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Badge className="bg-[#D4AF37]/15 text-[#D4AF37] border border-[#D4AF37]/30">Source</Badge>
              <div className="aspect-square bg-[#132018] border border-[#21362A] rounded-sm overflow-hidden">
                <img src={imgUrl(data.source.id)} alt="source" className="w-full h-full object-cover"/>
              </div>
              <div className="text-xs text-[#A1B4A8]">{data.source.tags?.join(", ")}</div>
            </div>
            {(data.variations || []).map((v) => (
              <div key={v.id} className="space-y-2">
                <Badge className="bg-[#097969]/20 text-[#2A9D8F] border border-[#097969]/40">{v.kind}{v.view ? ` · ${v.view}` : ""}</Badge>
                <div className="aspect-square bg-[#132018] border border-[#21362A] rounded-sm overflow-hidden">
                  <img src={imgUrl(v.id)} alt={v.kind} className="w-full h-full object-cover"/>
                </div>
                <div className="text-xs text-[#A1B4A8]">{new Date(v.created_at).toLocaleString()}</div>
              </div>
            ))}
            {(!data.variations || data.variations.length === 0) && (
              <div className="col-span-full text-sm text-[#A1B4A8]">No variations yet — click Enhance or Generate alternates.</div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
