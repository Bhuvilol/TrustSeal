import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import Lenis from 'lenis';
import { motion } from 'framer-motion';
import {
  Activity,
  BadgeCheck,
  Lock,
  Radio,
  Shield,
  Sparkles,
  TrendingUp,
  Wifi,
} from 'lucide-react';

const sections = [
  {
    eyebrow: 'Intelligent Monitoring',
    title: 'Realtime IoT compliance with AI-assisted alerts.',
    body: 'Stream telemetry, detect anomalies, and surface insights before they become incidents.',
    icon: <Wifi className="h-5 w-5 text-cyan-300" />,
  },
  {
    eyebrow: 'Blockchain Custody',
    title: 'Immutable custody from factory to port.',
    body: 'Chain-of-custody, biometric checkpoints, and cryptographic proofs baked into every leg.',
    icon: <Lock className="h-5 w-5 text-cyan-300" />,
  },
  {
    eyebrow: 'AI Insights',
    title: 'Explainable intelligence on every shipment.',
    body: 'Score risk, forecast delays, and summarize excursions with natural language briefs.',
    icon: <Sparkles className="h-5 w-5 text-cyan-300" />,
  },
  {
    eyebrow: 'Live Data Visualization',
    title: 'Mission-control grade dashboards.',
    body: 'Glowing maps, animated KPIs, and sensor charts that breathe with your data.',
    icon: <Activity className="h-5 w-5 text-cyan-300" />,
  },
];

function LandingPage() {
  useEffect(() => {
    const lenis = new Lenis({ smoothWheel: true, lerp: 0.12 });
    let raf = 0;
    const animate = (time: number) => {
      lenis.raf(time);
      raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);
    return () => {
      cancelAnimationFrame(raf);
      lenis.destroy();
    };
  }, []);

  return (
    <div className="relative min-h-screen overflow-hidden bg-transparent text-slate-50">
      <div className="grid-overlay" />
      <div className="bg-orb -left-10 top-10" />
      <div className="bg-orb right-0 top-1/3" />

      <header className="fixed inset-x-0 top-0 z-30">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 rounded-full border border-white/10 bg-white/5 px-5 py-3 backdrop-blur-xl">
          <div className="flex items-center gap-2">
            <div className="h-9 w-9 rounded-2xl bg-gradient-to-br from-cyan-400 to-emerald-400 shadow-lg shadow-cyan-400/30" />
            <span className="text-sm font-semibold tracking-[0.18em] text-slate-100">TRUSTSEAL IOT</span>
          </div>
          <nav className="hidden items-center gap-6 text-sm text-slate-200 md:flex">
            {['Features', 'Technology', 'Security', 'Pricing'].map((item) => (
              <a key={item} href={`#${item.toLowerCase()}`} className="transition hover:text-cyan-200">
                {item}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Link
              to="/login"
              className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-100 transition hover:border-cyan-300/60 hover:text-cyan-200"
            >
              Sign in
            </Link>
            <Link
              to="/register"
              className="rounded-full bg-gradient-to-r from-cyan-400 to-emerald-400 px-4 py-2 text-sm font-semibold text-slate-900 shadow-lg shadow-cyan-400/30 transition hover:scale-[1.02]"
            >
              Get Started
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-6xl flex-col gap-24 px-5 pb-32 pt-32 md:pt-36">
        <section className="relative grid gap-10 lg:grid-cols-[1.1fr_0.9fr]">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: 'easeOut' }}
            className="space-y-6"
          >
            <span className="pill inline-flex items-center gap-2 bg-white/5 text-cyan-100">
              <BadgeCheck className="h-4 w-4 text-cyan-300" /> Premium AI Logistics
            </span>
            <h1 className="text-4xl font-semibold leading-tight text-slate-50 md:text-5xl">
              TRUST IN EVERY SHIPMENT
            </h1>
            <p className="max-w-2xl text-lg text-slate-300">
              AI-powered IoT compliance, blockchain custody, and real-time monitoring for global supply chains.
              Experience mission-control clarity with layered depth, glow, and intentional motion.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                to="/register"
                className="rounded-full bg-gradient-to-r from-cyan-400 to-emerald-400 px-6 py-3 text-sm font-semibold text-slate-900 shadow-lg shadow-cyan-400/40 transition hover:scale-[1.02]"
              >
                Get Started
              </Link>
              <Link
                to="/login"
                className="rounded-full border border-white/20 px-6 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/60 hover:text-cyan-100"
              >
                View Demo
              </Link>
            </div>
            <div className="flex flex-wrap gap-4 text-sm text-slate-400">
              <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1">
                <Shield className="h-4 w-4 text-emerald-300" />
                Zero-trust security
              </div>
              <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1">
                <Radio className="h-4 w-4 text-cyan-300" />
                Live telemetry
              </div>
              <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1">
                <TrendingUp className="h-4 w-4 text-cyan-300" />
                AI insights
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 18 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.8, ease: 'easeOut', delay: 0.1 }}
            className="glass-card relative overflow-hidden border-white/10 p-6"
          >
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-cyan-300/12 via-transparent to-emerald-300/10" />
            <div className="flex items-center justify-between text-sm text-slate-300">
              <span>Live shipment telemetry</span>
              <span className="rounded-full bg-emerald-400/20 px-3 py-1 text-xs font-semibold text-emerald-200">
                LIVE
              </span>
            </div>
            <div className="mt-4 space-y-3">
              {[1, 2, 3, 4].map((item) => (
                <motion.div
                  key={item}
                  initial={{ opacity: 0, x: 12 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.4, delay: item * 0.05 }}
                  className="flex items-center justify-between rounded-xl border border-white/5 bg-white/5 px-4 py-3"
                >
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Container #{item}</p>
                    <p className="text-sm text-slate-100">Temperature 7.{item}degC · Humidity 4{item}%</p>
                  </div>
                  <span className="h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_0_6px_rgba(16,185,129,0.18)]" />
                </motion.div>
              ))}
            </div>
          </motion.div>
        </section>

        <section id="features" className="grid gap-6 md:grid-cols-2">
          {sections.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: index * 0.05 }}
              viewport={{ once: true, amount: 0.2 }}
              className="glass-card glow-border relative p-6"
            >
              <div className="absolute inset-0 bg-gradient-to-br from-white/3 via-transparent to-cyan-400/5 opacity-60" />
              <div className="relative flex items-start gap-3">
                <div className="mt-1 rounded-xl bg-white/5 p-3">{feature.icon}</div>
                <div className="space-y-1">
                  <p className="text-xs uppercase tracking-[0.2em] text-cyan-200">{feature.eyebrow}</p>
                  <h3 className="text-lg font-semibold text-slate-50">{feature.title}</h3>
                  <p className="text-sm text-slate-300">{feature.body}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </section>

        <section id="technology" className="glass-card relative overflow-hidden border-white/10 p-8">
          <div className="absolute inset-0 bg-gradient-to-r from-cyan-400/10 via-transparent to-emerald-400/10" />
          <div className="relative grid gap-8 lg:grid-cols-2">
            <div>
              <p className="pill bg-white/5 text-cyan-100">Blockchain Custody</p>
              <h3 className="mt-3 text-2xl font-semibold text-slate-50">Immutable custody you can audit</h3>
              <p className="mt-2 text-sm text-slate-300">
                Vertical custody timeline with biometric checkpoints, blockchain hashes, and proof-of-integrity on
                every leg. Visual leg progress animates as data arrives.
              </p>
              <div className="mt-4 space-y-3 text-sm text-slate-300">
                <div className="flex items-center gap-2">
                  <Lock className="h-4 w-4 text-cyan-300" /> Immutable hash reveal on status change
                </div>
                <div className="flex items-center gap-2">
                  <BadgeCheck className="h-4 w-4 text-cyan-300" /> Zero-trust role separation
                </div>
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-cyan-300" /> Custody ledger with on-chain references
                </div>
              </div>
            </div>
            <div className="relative rounded-2xl border border-white/10 bg-white/5 p-6">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(34,211,238,0.18),transparent_35%),radial-gradient(circle_at_80%_40%,rgba(124,58,237,0.16),transparent_35%)]" />
              <div className="relative space-y-4 text-sm text-slate-200">
                {[1, 2, 3, 4].map((step) => (
                  <div
                    key={step}
                    className="flex items-start gap-3 rounded-xl border border-white/8 bg-white/5 px-4 py-3"
                  >
                    <div className="mt-1 h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_0_5px_rgba(45,212,191,0.18)]" />
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Leg {step}</p>
                      <p className="font-semibold text-slate-50">Hash #{step}3a9f...e{step}d</p>
                      <p className="text-xs text-slate-400">Biometric verified · 2m ago</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="security" className="glass-card relative overflow-hidden border-white/10 p-8">
          <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/10 via-transparent to-cyan-400/10" />
          <div className="relative flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="pill bg-white/5 text-cyan-100">Security</p>
              <h3 className="mt-3 text-2xl font-semibold text-slate-50">End-to-end integrity, verified</h3>
              <p className="mt-2 max-w-xl text-sm text-slate-300">
                TLS everywhere, signed telemetry packets, anomaly detection, and auditable custody timelines. Red is
                only for critical.
              </p>
            </div>
            <div className="flex items-center gap-3 text-sm text-slate-200">
              <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_0_6px_rgba(52,211,153,0.2)]" />
              <span>System health: Operational</span>
            </div>
          </div>
        </section>

        <footer className="glass-card border-white/10 p-8">
          <div className="grid gap-6 md:grid-cols-[1.5fr_1fr_1fr]">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <div className="h-9 w-9 rounded-2xl bg-gradient-to-br from-cyan-400 to-emerald-400 shadow-lg shadow-cyan-400/30" />
                <span className="text-sm font-semibold tracking-[0.18em] text-slate-100">TRUSTSEAL IOT</span>
              </div>
              <p className="text-sm text-slate-400">
                Premium AI-powered logistics integrity platform. Live telemetry, custody, and intelligence in one place.
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-slate-400">Product</p>
              <ul className="mt-3 space-y-2 text-sm text-slate-300">
                <li>Features</li>
                <li>Technology</li>
                <li>Security</li>
                <li>Pricing</li>
              </ul>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-slate-400">Support</p>
              <ul className="mt-3 space-y-2 text-sm text-slate-300">
                <li>Docs</li>
                <li>API</li>
                <li>Status</li>
                <li>Contact</li>
              </ul>
            </div>
          </div>
          <div className="mt-6 flex flex-wrap items-center justify-between border-t border-white/10 pt-4 text-xs text-slate-500">
            <span>© {new Date().getFullYear()} TrustSeal IoT. All rights reserved.</span>
            <span className="text-slate-400">Built for premium mission-control experiences.</span>
          </div>
        </footer>
      </main>
    </div>
  );
}

export default LandingPage;
