import { useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'wouter';
import { Eye, EyeOff, LoaderCircle } from 'lucide-react';
import AuthScreen from '@/components/auth/AuthScreen';
import { useAuth } from '@/auth/AuthContext';
import { ApiError } from '@/api/types';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function SignupPage() {
  const { signup } = useAuth();
  const [form, setForm] = useState({ fullName: '', email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const validationError = useMemo(() => {
    if (form.fullName.trim().length < 2) return 'Full name must be at least 2 characters.';
    if (!EMAIL_PATTERN.test(form.email.trim())) return 'Enter a valid email address.';
    if (form.password.length < 8) return 'Password must be at least 8 characters.';
    return null;
  }, [form.email, form.fullName, form.password]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (validationError) {
      setErrorMessage(validationError);
      return;
    }
    setSubmitting(true);
    setErrorMessage(null);
    try {
      await signup({
        full_name: form.fullName.trim(),
        email: form.email.trim(),
        password: form.password,
      });
    } catch (error) {
      setErrorMessage(
        error instanceof ApiError ? error.message : 'Sign up failed. Try again.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthScreen
      title="Create Account"
      subtitle="Set up your workspace access with email and password."
      footer={
        <p>
          Already have an account?{' '}
          <Link href="/login" className="font-semibold text-primary transition hover:text-primary/80">
            Log in
          </Link>
        </p>
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <label htmlFor="signup-name" className="text-sm font-medium text-foreground">
            Full Name
          </label>
          <input
            id="signup-name"
            type="text"
            autoComplete="name"
            value={form.fullName}
            onChange={(event) => setForm((current) => ({ ...current, fullName: event.target.value }))}
            className="h-12 w-full rounded-xl border border-input bg-background px-4 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-ring focus:ring-4 focus:ring-ring/15"
            placeholder="Ananya Nair"
            data-testid="signup-name"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="signup-email" className="text-sm font-medium text-foreground">
            Email Address
          </label>
          <input
            id="signup-email"
            type="email"
            autoComplete="email"
            value={form.email}
            onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
            className="h-12 w-full rounded-xl border border-input bg-background px-4 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-ring focus:ring-4 focus:ring-ring/15"
            placeholder="name@cial.in"
            data-testid="signup-email"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="signup-password" className="text-sm font-medium text-foreground">
            Password
          </label>
          <div className="relative">
            <input
              id="signup-password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              value={form.password}
              onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
              className="h-12 w-full rounded-xl border border-input bg-background px-4 pr-12 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-ring focus:ring-4 focus:ring-ring/15"
              placeholder="At least 8 characters"
              data-testid="signup-password"
            />
            <button
              type="button"
              onClick={() => setShowPassword((current) => !current)}
              className="absolute right-3 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>

        {errorMessage ? (
          <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive" data-testid="signup-error">
            {errorMessage}
          </div>
        ) : null}

        <button
          type="submit"
          disabled={submitting}
          className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:bg-primary/85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-70"
          data-testid="signup-submit"
        >
          {submitting ? <LoaderCircle size={16} className="animate-spin" /> : null}
          {submitting ? 'Creating account...' : 'Create Account'}
        </button>
      </form>
    </AuthScreen>
  );
}
