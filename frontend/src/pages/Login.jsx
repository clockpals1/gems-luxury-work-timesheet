import React, { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Brand } from "../components/Brand";
import { toast } from "sonner";
import { motion } from "framer-motion";

export default function Login() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("admin@gemsandluxury.com");
  const [password, setPassword] = useState("Admin@123");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  if (user) return <Navigate to={user.role === "worker" ? "/worker" : "/admin"} replace />;

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const u = await login(email.trim().toLowerCase(), password);
      toast.success(`Welcome, ${u.name}`);
      nav(u.role === "worker" ? "/worker" : "/admin", { replace: true });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen grid md:grid-cols-2 bg-[#050A07] text-white">
      <div
        className="relative hidden md:block"
        style={{
          backgroundImage:
            "linear-gradient(180deg, rgba(5,10,7,0.2), rgba(5,10,7,0.85)), url(https://images.pexels.com/photos/1475033/pexels-photo-1475033.jpeg)",
          backgroundSize: "cover", backgroundPosition: "center",
        }}
      >
        <div className="absolute inset-0 p-12 flex flex-col justify-between">
          <Brand />
          <div>
            <div className="label-overline text-[#D4AF37]">Studio of African Luxury</div>
            <h1 className="font-display text-5xl lg:text-6xl mt-3 leading-[1.05] max-w-md">
              Where heritage meets <span className="italic text-[#D4AF37]">couture</span>.
            </h1>
            <p className="mt-6 text-[#A1B4A8] max-w-md">
              The internal studio for Gems &amp; Luxury — where our catalog is born, curated, and brought to market.
            </p>
          </div>
        </div>
      </div>
      <div className="flex items-center justify-center p-8">
        <motion.form
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
          onSubmit={onSubmit} className="w-full max-w-md space-y-6" data-testid="login-form"
        >
          <div>
            <div className="label-overline text-[#D4AF37]">Studio access</div>
            <h2 className="font-display text-4xl mt-2">Sign in</h2>
            <p className="text-[#A1B4A8] text-sm mt-2">Use the credentials provided by your administrator.</p>
          </div>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email" className="label-overline">Email</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="login-email" className="bg-[#0C140F] border-[#21362A] h-11" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="label-overline">Password</Label>
              <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required data-testid="login-password" className="bg-[#0C140F] border-[#21362A] h-11" />
            </div>
          </div>
          <Button type="submit" disabled={loading} data-testid="login-submit"
            className="w-full h-11 bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07] rounded-sm font-semibold tracking-wide">
            {loading ? "Signing in…" : "Enter Studio"}
          </Button>
          <p className="text-xs text-[#A1B4A8]">Default admin: <span className="text-white">admin@gemsandluxury.com / Admin@123</span> · Worker: <span className="text-white">worker@gemsandluxury.com / Worker@123</span></p>
        </motion.form>
      </div>
    </div>
  );
}
