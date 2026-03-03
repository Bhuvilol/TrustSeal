import { Link } from 'react-router-dom';

function NotFoundPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <section className="panel w-full max-w-lg p-8 text-center">
        <p className="text-xs uppercase tracking-[0.2em] text-brand-300">404</p>
        <h1 className="mt-3 text-3xl font-semibold text-slate-100">Page not found</h1>
        <p className="mt-2 text-sm text-slate-400">The requested route does not exist in TrustSeal IoT.</p>
        <Link to="/dashboard" className="btn-primary mt-6 inline-flex">
          Go to Dashboard
        </Link>
      </section>
    </main>
  );
}

export default NotFoundPage;

