import React, { useEffect, useState } from "react";
import { api, imgUrl } from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Badge } from "./ui/badge";
import { toast } from "sonner";
import { Copy, Save } from "lucide-react";

export default function ProductDetailDialog({ id, open, onOpenChange, onSaved }) {
  const [p, setP] = useState(null);
  const [meta, setMeta] = useState({});
  const [price, setPrice] = useState(0);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !id) return;
    api.get(`/products/${id}`).then((r) => {
      setP(r.data);
      setPrice(r.data.final_price);
      setMeta(r.data.pricing_meta || {});
    });
  }, [open, id]);

  const save = async () => {
    setSaving(true);
    try {
      await api.patch(`/products/${id}`, { final_price: Number(price), pricing_meta: meta });
      toast.success("Saved");
      onSaved?.();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };

  const copyCMS = async () => {
    try {
      const r = await api.get(`/products/${id}/cms-payload`);
      await navigator.clipboard.writeText(JSON.stringify(r.data, null, 2));
      toast.success("CMS payload copied to clipboard");
    } catch (e) { toast.error("Copy failed"); }
  };

  if (!p) return null;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#0C140F] border-[#21362A] text-white max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-3xl">{p.name}</DialogTitle>
          <div className="text-sm text-[#A1B4A8]">{p.category} · by {p.generated_by_name}</div>
        </DialogHeader>
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <div className="aspect-square bg-[#132018] border border-[#21362A] rounded-sm overflow-hidden">
              {p.image_asset_id && <img src={imgUrl(p.image_asset_id)} alt="" className="w-full h-full object-cover"/>}
            </div>
            <div className="mt-4">
              <div className="label-overline">Short title</div>
              <div className="text-sm">{p.short_title}</div>
              <div className="label-overline mt-3">Short description</div>
              <div className="text-sm text-[#A1B4A8]">{p.short_description}</div>
              <div className="label-overline mt-3">Full description</div>
              <div className="text-sm text-[#A1B4A8] whitespace-pre-line">{p.full_description}</div>
              <div className="label-overline mt-3">Tags</div>
              <div className="flex flex-wrap gap-1 mt-1">{p.tags?.map((t) => <Badge key={t} className="bg-[#132018] border border-[#21362A] text-[#A1B4A8]">{t}</Badge>)}</div>
              <div className="label-overline mt-3">Sizes</div>
              <div className="text-sm">{p.sizes?.join(", ")}</div>
            </div>
          </div>
          <div className="space-y-4">
            <div>
              <Label className="label-overline">Final price ({p.currency})</Label>
              <Input type="number" value={price} onChange={(e) => setPrice(e.target.value)} className="bg-[#132018] border-[#21362A] mt-1" data-testid="detail-price"/>
            </div>
            <div className="border border-[#21362A] rounded-sm p-4 space-y-3 bg-[#050A07]">
              <div className="label-overline text-[#D4AF37]">Pricing reasoning (admin only)</div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="text-xs">Perceived quality</Label><Input type="number" min="1" max="5" value={meta.perceivedQuality ?? 3} onChange={(e) => setMeta({ ...meta, perceivedQuality: Number(e.target.value) })} className="bg-[#132018] border-[#21362A]" data-testid="meta-quality"/></div>
                <div><Label className="text-xs">Complexity</Label><Input type="number" min="1" max="5" value={meta.complexity ?? 3} onChange={(e) => setMeta({ ...meta, complexity: Number(e.target.value) })} className="bg-[#132018] border-[#21362A]" data-testid="meta-complexity"/></div>
                <div><Label className="text-xs">Occasion tier</Label><Input value={meta.occasionTier ?? ""} onChange={(e) => setMeta({ ...meta, occasionTier: e.target.value })} className="bg-[#132018] border-[#21362A]" data-testid="meta-tier"/></div>
                <div><Label className="text-xs">Uplift</Label><Input type="number" step="0.05" value={meta.uplift ?? 0} onChange={(e) => setMeta({ ...meta, uplift: Number(e.target.value) })} className="bg-[#132018] border-[#21362A]" data-testid="meta-uplift"/></div>
              </div>
              <div><Label className="text-xs">Reasoning</Label><Textarea rows={2} value={meta.reasoning ?? ""} onChange={(e) => setMeta({ ...meta, reasoning: e.target.value })} className="bg-[#132018] border-[#21362A]" data-testid="meta-reasoning"/></div>
            </div>
            <div className="flex gap-2">
              <Button onClick={save} disabled={saving} className="flex-1 bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]" data-testid="detail-save"><Save className="w-4 h-4 mr-2"/>{saving ? "Saving…" : "Save changes"}</Button>
              <Button onClick={copyCMS} variant="outline" className="border-[#21362A]" data-testid="copy-cms"><Copy className="w-4 h-4 mr-2"/>Copy CMS JSON</Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
