import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { toast } from "sonner";

export default function AdminPricing() {
  const [rules, setRules] = useState({ min_price: 40, max_price: 150, currency: "USD", category_multipliers: {} });
  const [cats, setCats] = useState([]);

  useEffect(() => {
    api.get("/admin/pricing-rules").then(r => setRules(r.data));
    api.get("/admin/categories").then(r => setCats(r.data));
  }, []);

  const save = async () => {
    try {
      await api.put("/admin/pricing-rules", {
        min_price: Number(rules.min_price), max_price: Number(rules.max_price),
        currency: rules.currency, category_multipliers: rules.category_multipliers || {},
      });
      toast.success("Pricing saved");
    } catch { toast.error("Failed"); }
  };

  const setMult = (name, v) => setRules({ ...rules, category_multipliers: { ...(rules.category_multipliers || {}), [name]: Number(v) } });

  return (
    <AdminLayout>
      <div className="mb-6">
        <div className="label-overline text-[#D4AF37]">Commerce</div>
        <h1 className="font-display text-4xl mt-2">Pricing</h1>
        <p className="text-sm text-[#A1B4A8] mt-2">Workers never see reasoning — they see only the final suggested price.</p>
      </div>
      <div className="grid gap-6 md:grid-cols-3">
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardHeader><CardTitle className="font-display text-xl">Price band</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2"><Label className="label-overline">Min price</Label><Input type="number" value={rules.min_price} onChange={(e) => setRules({ ...rules, min_price: e.target.value })} className="bg-[#132018] border-[#21362A]" data-testid="pricing-min"/></div>
            <div className="space-y-2"><Label className="label-overline">Max price</Label><Input type="number" value={rules.max_price} onChange={(e) => setRules({ ...rules, max_price: e.target.value })} className="bg-[#132018] border-[#21362A]" data-testid="pricing-max"/></div>
            <div className="space-y-2"><Label className="label-overline">Currency</Label><Input value={rules.currency} onChange={(e) => setRules({ ...rules, currency: e.target.value })} className="bg-[#132018] border-[#21362A]" data-testid="pricing-currency"/></div>
          </CardContent>
        </Card>
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm md:col-span-2">
          <CardHeader><CardTitle className="font-display text-xl">Category multipliers</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {cats.map((c) => (
              <div key={c.id} className="space-y-2">
                <Label className="label-overline">{c.name}</Label>
                <Input type="number" step="0.05" value={(rules.category_multipliers || {})[c.name] ?? c.price_multiplier ?? 1}
                  onChange={(e) => setMult(c.name, e.target.value)} className="bg-[#132018] border-[#21362A]" data-testid={`mult-${c.slug}`}/>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
      <div className="mt-6"><Button onClick={save} className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]" data-testid="pricing-save">Save pricing</Button></div>
    </AdminLayout>
  );
}
