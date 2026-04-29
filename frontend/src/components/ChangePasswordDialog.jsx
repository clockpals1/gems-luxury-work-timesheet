import React, { useState } from "react";
import { api } from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Button } from "./ui/button";
import { toast } from "sonner";

export default function ChangePasswordDialog({ open, onOpenChange }) {
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (next.length < 8) { toast.error("New password must be at least 8 characters"); return; }
    if (next !== confirm) { toast.error("Passwords do not match"); return; }
    setBusy(true);
    try {
      await api.post("/auth/change-password", { current_password: cur, new_password: next });
      toast.success("Password updated");
      setCur(""); setNext(""); setConfirm(""); onOpenChange(false);
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#0C140F] border-[#21362A] text-white" data-testid="change-password-dialog">
        <DialogHeader><DialogTitle className="font-display text-2xl">Change password</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2"><Label className="label-overline">Current password</Label><Input type="password" value={cur} onChange={(e) => setCur(e.target.value)} required className="bg-[#132018] border-[#21362A]" data-testid="cp-current"/></div>
          <div className="space-y-2"><Label className="label-overline">New password</Label><Input type="password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={8} className="bg-[#132018] border-[#21362A]" data-testid="cp-new"/></div>
          <div className="space-y-2"><Label className="label-overline">Confirm new password</Label><Input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required minLength={8} className="bg-[#132018] border-[#21362A]" data-testid="cp-confirm"/></div>
          <Button type="submit" disabled={busy} className="w-full bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]" data-testid="cp-submit">{busy ? "Saving…" : "Update password"}</Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
