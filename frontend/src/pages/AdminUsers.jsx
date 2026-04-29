import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { AdminLayout } from "../components/Layout";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Plus, KeyRound } from "lucide-react";

export default function AdminUsers() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ email: "", name: "", password: "", role: "worker" });
  const [resetTarget, setResetTarget] = useState(null);
  const [resetPw, setResetPw] = useState("");

  const load = async () => { const r = await api.get("/admin/users"); setUsers(r.data); };
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/admin/users", form);
      toast.success("User created");
      setOpen(false); setForm({ email: "", name: "", password: "", role: "worker" });
      load();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  };

  const toggle = async (u) => {
    try { await api.patch(`/admin/users/${u.id}`, { active: !u.active }); load(); }
    catch { toast.error("Failed"); }
  };

  const setRole = async (u, role) => {
    try { await api.patch(`/admin/users/${u.id}`, { role }); toast.success(`Role updated to ${role}`); load(); }
    catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  };

  const submitReset = async (e) => {
    e.preventDefault();
    if (resetPw.length < 8) { toast.error("Password must be at least 8 characters"); return; }
    try {
      await api.post(`/admin/users/${resetTarget.id}/reset-password`, { new_password: resetPw });
      toast.success(`Password reset for ${resetTarget.email}`);
      setResetTarget(null); setResetPw("");
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  };

  return (
    <AdminLayout>
      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="label-overline text-[#D4AF37]">People</div>
          <h1 className="font-display text-4xl mt-2">Users</h1>
          <p className="text-sm text-[#A1B4A8] mt-2">Admins can promote any user — including making other admins.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button data-testid="add-user-btn" className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]"><Plus className="w-4 h-4 mr-2"/>Add user</Button>
          </DialogTrigger>
          <DialogContent className="bg-[#0C140F] border-[#21362A] text-white">
            <DialogHeader><DialogTitle className="font-display text-2xl">New user</DialogTitle></DialogHeader>
            <form onSubmit={create} className="space-y-4" data-testid="create-user-form">
              <div className="space-y-2"><Label>Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required data-testid="user-name" className="bg-[#132018] border-[#21362A]"/></div>
              <div className="space-y-2"><Label>Email</Label><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required data-testid="user-email" className="bg-[#132018] border-[#21362A]"/></div>
              <div className="space-y-2"><Label>Temporary password</Label><Input type="text" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required data-testid="user-password" className="bg-[#132018] border-[#21362A]"/></div>
              <div className="space-y-2"><Label>Role</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                  <SelectTrigger data-testid="user-role" className="bg-[#132018] border-[#21362A]"><SelectValue/></SelectTrigger>
                  <SelectContent className="bg-[#0C140F] border-[#21362A] text-white">
                    <SelectItem value="worker">Worker</SelectItem>
                    <SelectItem value="manager">Manager</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button type="submit" data-testid="create-user-submit" className="w-full bg-[#D4AF37] text-[#050A07] hover:bg-[#F0C84A]">Create user</Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
        <CardContent className="p-0">
          <table className="w-full text-sm" data-testid="users-table">
            <thead className="text-[#A1B4A8] text-xs uppercase tracking-widest">
              <tr><th className="text-left p-4">Name</th><th className="text-left">Email</th><th className="text-left">Role</th><th className="text-left">Created</th><th className="text-right pr-4">Active</th><th className="text-right p-4">Actions</th></tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-[#21362A]">
                  <td className="p-4">{u.name}{u.id === me?.id && <span className="ml-2 text-xs text-[#D4AF37]">(you)</span>}</td>
                  <td className="text-[#A1B4A8]">{u.email}</td>
                  <td>
                    {me?.role === "admin" && u.id !== me?.id ? (
                      <Select value={u.role} onValueChange={(v) => setRole(u, v)}>
                        <SelectTrigger className="bg-[#132018] border-[#21362A] h-8 w-32 text-xs" data-testid={`role-${u.email}`}><SelectValue/></SelectTrigger>
                        <SelectContent className="bg-[#0C140F] border-[#21362A] text-white">
                          <SelectItem value="worker">Worker</SelectItem>
                          <SelectItem value="manager">Manager</SelectItem>
                          <SelectItem value="admin">Admin</SelectItem>
                        </SelectContent>
                      </Select>
                    ) : <span className="text-[#D4AF37]">{u.role}</span>}
                  </td>
                  <td className="text-[#A1B4A8]">{new Date(u.created_at).toLocaleDateString()}</td>
                  <td className="pr-4 text-right"><Switch checked={!!u.active} disabled={u.id === me?.id} onCheckedChange={() => toggle(u)} data-testid={`user-active-${u.email}`}/></td>
                  <td className="p-4 text-right">
                    {me?.role === "admin" && (
                      <Button size="sm" variant="outline" className="border-[#21362A]" onClick={() => { setResetTarget(u); setResetPw(""); }} data-testid={`reset-pw-${u.email}`}>
                        <KeyRound className="w-3 h-3 mr-1"/>Reset password
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Dialog open={!!resetTarget} onOpenChange={(v) => !v && setResetTarget(null)}>
        <DialogContent className="bg-[#0C140F] border-[#21362A] text-white">
          <DialogHeader><DialogTitle className="font-display text-2xl">Reset password — {resetTarget?.email}</DialogTitle></DialogHeader>
          <form onSubmit={submitReset} className="space-y-4">
            <div className="space-y-2"><Label className="label-overline">New password</Label><Input type="text" value={resetPw} onChange={(e) => setResetPw(e.target.value)} required minLength={8} className="bg-[#132018] border-[#21362A]" data-testid="admin-reset-pw"/></div>
            <p className="text-xs text-[#A1B4A8]">The user will need to use this password the next time they sign in. They can change it themselves afterwards.</p>
            <Button type="submit" className="w-full bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]" data-testid="admin-reset-submit">Reset password</Button>
          </form>
        </DialogContent>
      </Dialog>
    </AdminLayout>
  );
}
