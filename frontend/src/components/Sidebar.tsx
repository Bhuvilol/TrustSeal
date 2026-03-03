import clsx from 'clsx';
import { NavLink } from 'react-router-dom';
import { Box, BrainCircuit, Compass, FileText, Layers, QrCode } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { getStatusLabel } from '@/utils/status';

const links = [
  { to: '/dashboard', label: 'Dashboard', icon: Compass },
  { to: '/devices', label: 'Devices', icon: Layers },
  { to: '/shipments', label: 'Shipments', icon: Box },
  { to: '/device-logs', label: 'Device Logs', icon: FileText },
  { to: '/intelligence', label: 'Intelligence', icon: BrainCircuit },
  { to: '/lookup', label: 'QR Lookup', icon: QrCode },
];

function Sidebar() {
  const { user, logout } = useAuth();

  return (
    <aside className="glass mb-4 flex w-full flex-col p-5 md:sticky md:top-0 md:mb-0 md:h-screen md:w-[260px]">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-2xl bg-gradient-to-br from-cyan-400/80 to-emerald-400/80 shadow-lg shadow-cyan-400/30" />
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-cyan-200">TrustSeal IoT</p>
          <h1 className="mt-1 text-lg font-semibold text-slate-100">Control Center</h1>
        </div>
      </div>

      <nav className="mt-8 flex flex-1 flex-col gap-2">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition',
                isActive
                  ? 'bg-white/10 text-cyan-200 shadow-[0_8px_20px_rgba(45,212,191,0.18)]'
                  : 'text-slate-300 hover:bg-white/5 hover:text-slate-100',
              )
            }
          >
            <link.icon className="h-4 w-4" />
            {link.label}
          </NavLink>
        ))}
      </nav>

      <div className="space-y-4 border-t border-white/10 pt-4">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-slate-100">{user?.name ?? 'User'}</p>
          <p className="text-xs uppercase tracking-wide text-slate-400">
            {user ? getStatusLabel(user.role) : 'No Role'}
          </p>
          <p className="truncate text-xs text-slate-500">{user?.email ?? ''}</p>
        </div>

        <button type="button" className="btn-secondary w-full" onClick={logout}>
          Logout
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;
