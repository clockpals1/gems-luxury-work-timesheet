import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Card, CardContent } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { FileDown } from "lucide-react";

export default function AdminAttendance() {
  const [rows, setRows] = useState([]);
  const [days, setDays] = useState("7");
  const [downloading, setDownloading] = useState(false);

  const load = async () => { const r = await api.get("/admin/attendance"); setRows(r.data); };
  useEffect(() => { load(); }, []);

  const forceOut = async (id) => {
    try { await api.post(`/admin/attendance/${id}/force-punch-out`); toast.success("Force punched out"); load(); }
    catch { toast.error("Failed"); }
  };

  const downloadPdf = async () => {
    setDownloading(true);
    try {
      const r = await api.get(`/admin/reports/timesheet?days=${days}`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `timesheet_${new Date().toISOString().slice(0,10)}_${days}d.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Timesheet downloaded");
    } catch (err) { toast.error("Download failed"); }
    finally { setDownloading(false); }
  };

  return (
    <AdminLayout>
      <div className="flex items-end justify-between mb-6">
        <div><div className="label-overline text-[#D4AF37]">Work</div><h1 className="font-display text-4xl mt-2">Attendance</h1></div>
        <div className="flex items-center gap-2">
          <Select value={days} onValueChange={setDays}>
            <SelectTrigger className="bg-[#132018] border-[#21362A] w-36 h-9" data-testid="ts-days"><SelectValue/></SelectTrigger>
            <SelectContent className="bg-[#0C140F] border-[#21362A] text-white">
              {["7","14","30","60","90"].map((d) => <SelectItem key={d} value={d}>{`Last ${d} days`}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button onClick={downloadPdf} disabled={downloading} className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]" data-testid="download-timesheet-btn">
            <FileDown className="w-4 h-4 mr-2"/>{downloading ? "Generating…" : "Download PDF"}
          </Button>
        </div>
      </div>
      <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
        <CardContent className="p-0">
          <table className="w-full text-sm" data-testid="attendance-table">
            <thead className="text-[#A1B4A8] text-xs uppercase tracking-widest">
              <tr><th className="text-left p-4">Worker</th><th className="text-left">Punch in</th><th className="text-left">Punch out</th><th className="text-right">Total</th><th className="text-right">Break</th><th className="text-left pl-4">Status</th><th className="p-4 text-right">Actions</th></tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id} className="border-t border-[#21362A]">
                  <td className="p-4">{a.user_name}</td>
                  <td className="text-[#A1B4A8]">{new Date(a.punch_in).toLocaleString()}</td>
                  <td className="text-[#A1B4A8]">{a.punch_out ? new Date(a.punch_out).toLocaleString() : "—"}</td>
                  <td className="text-right">{a.total_minutes || 0}m</td>
                  <td className="text-right">{a.break_minutes || 0}m</td>
                  <td className="pl-4">
                    {a.punch_out ? (a.auto_punched_out ? <Badge className="bg-[#E63946]/15 text-[#E63946] border border-[#E63946]/30">auto</Badge> : <Badge className="bg-[#132018] border border-[#21362A] text-[#A1B4A8]">closed</Badge>) : <Badge className="bg-[#097969]/20 text-[#2A9D8F] border border-[#097969]/40">open</Badge>}
                  </td>
                  <td className="p-4 text-right">
                    {!a.punch_out && <Button size="sm" variant="outline" className="border-[#E63946] text-[#E63946]" onClick={() => forceOut(a.id)} data-testid={`force-out-${a.id}`}>Force out</Button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </AdminLayout>
  );
}
