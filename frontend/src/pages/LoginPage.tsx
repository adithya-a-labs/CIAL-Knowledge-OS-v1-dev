import { useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'wouter';
import { Eye, EyeOff, LoaderCircle } from 'lucide-react';
import AuthScreen from '@/components/auth/AuthScreen';
import { useAuth } from '@/auth/AuthContext';
import { ApiError } from '@/api/types';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginPage() {
  const { login } = useAuth();
  const [form, setForm] = useState({ email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const validationError = useMemo(() => {
    if (!form.email.trim()) return 'Email address is required.';
    if (!EMAIL_PATTERN.test(form.email.trim())) return 'Enter a valid email address.';
    if (!form.password) return 'Password is required.';
    return null;
  }, [form.email, form.password]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (validationError) {
      setErrorMessage(validationError);
      return;
    }
    setSubmitting(true);
    setErrorMessage(null);
    try {
      await login({
        email: form.email.trim(),
        password: form.password,
      });
    } catch (error) {
      setErrorMessage(
        error instanceof ApiError ? error.message : 'Login failed. Try again.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthScreen
      title="Log In"
      subtitle="Enter the workspace with your CIAL Knowledge OS account."
      footer={
        <p>
          New here?{' '}
          <Link href="/signup" className="font-semibold text-[#25611f] transition hover:text-[#1d4f18]">
            Create an account
          </Link>
        </p>
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <label htmlFor="login-email" className="text-sm font-medium text-slate-800">
            Email Address
          </label>
          <input
            id="login-email"
            type="email"
            autoComplete="email"
            value={form.email}
            onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
            className="h-12 w-full rounded-xl border border-[#d7e1d2] bg-white px-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-[#2f6d25] focus:ring-4 focus:ring-[#2f6d25]/10"
            placeholder="name@cial.in"
            data-testid="login-email"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="login-password" className="text-sm font-medium text-slate-800">
            Password
          </label>
          <div className="relative">
            <input
              id="login-password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              value={form.password}
              onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
              className="h-12 w-full rounded-xl border border-[#d7e1d2] bg-white px-4 pr-12 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-[#2f6d25] focus:ring-4 focus:ring-[#2f6d25]/10"
              placeholder="Enter your password"
              data-testid="login-password"
            />
            <button
              type="button"
              onClick={() => setShowPassword((current) => !current)}
              className="absolute right-3 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-slate-500 transition hover:bg-[#f4f7f2] hover:text-slate-800"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>

        {errorMessage ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" data-testid="login-error">
            {errorMessage}
          </div>
        ) : null}

        <button
          type="submit"
          disabled={submitting}
          className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#25611f] px-4 text-sm font-semibold text-white transition hover:bg-[#1f521a] disabled:cursor-not-allowed disabled:opacity-70"
          data-testid="login-submit"
        >
          {submitting ? <LoaderCircle size={16} className="animate-spin" /> : null}
          {submitting ? 'Logging in...' : 'Log In'}
        </button>
      </form>
    </AuthScreen>
  );
}
