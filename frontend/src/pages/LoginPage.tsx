import { FormEvent, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { LockKeyhole, Sparkles } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { getErrorMessage } from '@/utils/errors';

function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fromPath = (location.state as { from?: string } | null)?.from ?? '/dashboard';
  const registeredEmail = (location.state as { registeredEmail?: string } | null)?.registeredEmail ?? '';

  if (isAuthenticated) {
    return <Navigate to={fromPath} replace />;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      await login(email, password);
      navigate(fromPath, { replace: true });
    } catch (error) {
      setErrorMessage(getErrorMessage(error, 'Unable to login'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="relative flex min-h-screen items-center justify-center px-4 py-12">
      <div className="grid-overlay" />
      <div className="bg-orb left-0 top-20" />
      <div className="bg-orb right-10 bottom-10" />
      <motion.section
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="glass-card glow-border w-full max-w-md p-8"
      >
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-gradient-to-br from-cyan-400 to-emerald-400 p-3 shadow-lg shadow-cyan-400/30">
            <LockKeyhole className="h-5 w-5 text-slate-900" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-cyan-200">TrustSeal IoT</p>
            <h1 className="text-2xl font-semibold text-slate-100">Sign in to mission control</h1>
            <p className="mt-1 text-sm text-slate-400">JWT-secured access to your logistics intelligence hub.</p>
          </div>
        </div>

        {registeredEmail && (
          <p className="mt-4 rounded-xl border border-status-green/35 bg-status-green/10 px-3 py-2 text-sm text-status-green">
            Registration completed for {registeredEmail}. You can sign in now.
          </p>
        )}

        {errorMessage && (
          <p className="mt-4 rounded-xl border border-status-red/35 bg-status-red/10 px-3 py-2 text-sm text-status-red">
            {errorMessage}
          </p>
        )}

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-1">
            <label htmlFor="email" className="text-sm text-slate-300">
              Email
            </label>
            <div className="relative">
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                className="input-field pr-10"
                placeholder="operator@trustseal.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
              <Sparkles className="absolute right-3 top-3 h-4 w-4 text-cyan-300" />
            </div>
          </div>

          <div className="space-y-1">
            <label htmlFor="password" className="text-sm text-slate-300">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              className="input-field"
              placeholder="********"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>

          <button type="submit" className="btn-primary w-full" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in...' : 'Login'}
          </button>
        </form>

        <p className="mt-6 text-sm text-slate-400">
          New account?{' '}
          <Link to="/register" className="font-semibold text-cyan-200 transition hover:text-cyan-100">
            Register here
          </Link>
        </p>
      </motion.section>
    </main>
  );
}

export default LoginPage;
