import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Switch } from "../components/ui/switch";
import { toast } from "sonner";
import { Plus } from "lucide-react";

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ email: "", name: "", password: "", role: "worker" });

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

  return (
    <AdminLayout>
      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="label-overline text-[#D4AF37]">People</div>
          <h1 className="font-display text-4xl mt-2">Users</h1>
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
              <tr><th className="text-left p-4">Name</th><th className="text-left">Email</th><th className="text-left">Role</th><th className="text-left">Created</th><th className="text-right p-4">Active</th></tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-[#21362A]">
                  <td className="p-4">{u.name}</td>
                  <td className="text-[#A1B4A8]">{u.email}</td>
                  <td><Badge className="bg-[#132018] border border-[#21362A] text-[#D4AF37]">{u.role}</Badge></td>
                  <td className="text-[#A1B4A8]">{new Date(u.created_at).toLocaleDateString()}</td>
                  <td className="p-4 text-right"><Switch checked={!!u.active} onCheckedChange={() => toggle(u)} data-testid={`user-active-${u.email}`}/></td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </AdminLayout>
  );
}
