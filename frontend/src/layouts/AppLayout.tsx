import { Outlet, useLocation } from 'react-router-dom';
import { Shield, Sparkles } from 'lucide-react';
import AdminChatWidget from '@/components/AdminChatWidget';
import Sidebar from '@/components/Sidebar';
import { useAuth } from '@/hooks/useAuth';

function AppLayout() {
  const { user } = useAuth();
  const location = useLocation();
  const pathLabel = location.pathname.replace('/', '') || 'dashboard';

  return (
    <div className="relative min-h-screen overflow-hidden bg-transparent md:grid md:grid-cols-[260px_1fr]">
      <div className="grid-overlay" />
      <div className="bg-orb -left-10 top-20" />
      <div className="bg-orb right-10 top-1/2" />
      <Sidebar />
      <div className="md:pl-2">
        <header className="sticky top-0 z-30 border-b border-white/10 bg-white/5 px-4 py-4 backdrop-blur-xl md:px-8">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-gradient-to-br from-cyan-400/80 to-emerald-400/80 p-2 shadow-lg shadow-cyan-400/30">
                <Shield className="h-5 w-5 text-slate-900" />
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.14em] text-cyan-200">Mission Control</p>
                <p className="text-sm font-semibold text-slate-100">{pathLabel}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
              <Sparkles className="h-4 w-4 text-cyan-300" />
              {user ? `${user.name} · ${user.role}` : 'Session'}
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 md:px-8">
          <Outlet />
        </main>
        <AdminChatWidget />
      </div>
    </div>
  );
}

export default AppLayout;
