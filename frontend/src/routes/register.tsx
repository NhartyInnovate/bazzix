import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AuthShell } from "./login";

export const Route = createFileRoute("/register")({
  ssr: false,
  head: () => ({ meta: [{ title: "Create your account — Bazzix" }] }),
  component: RegisterPage,
});

const schema = z.object({
  first_name: z.string().trim().min(1, "Please share your first name.").max(60),
  last_name: z.string().trim().min(1, "Please share your last name.").max(60),
  email: z.string().trim().email("Enter a valid email address.").max(255),
  password: z.string().min(8, "Use at least 8 characters.").max(128),
});

function RegisterPage() {
  const { register, status } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (status === "authenticated") navigate({ to: "/workspace", replace: true });
  }, [status, navigate]);

  function update<K extends keyof typeof form>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const parsed = schema.safeParse(form);
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Please check your details.");
      return;
    }
    setSubmitting(true);
    try {
      await register(parsed.data);
      navigate({ to: "/workspace", replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          err.status === 400 || err.status === 409
            ? "An account with that email already exists. Try signing in instead."
            : err.status === 0
              ? "We couldn't reach your workspace. Please check your internet connection."
              : typeof err.message === "string"
                ? err.message
                : "We couldn't create your account. Please try again.",
        );
      } else {
        setError("Something interrupted us. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell>
      <div className="mb-8 text-center">
        <h1 className="font-serif text-3xl tracking-tight text-foreground">
          Create your workspace.
        </h1>
        <p className="mt-1.5 text-sm text-muted-foreground">Start building with AI in seconds.</p>
      </div>

      <div className="rounded-2xl border border-border/60 bg-surface/40 px-8 py-8 shadow-sm backdrop-blur-md">
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="first_name" className="font-medium">
                First name
              </Label>
              <Input
                id="first_name"
                autoComplete="given-name"
                autoFocus
                value={form.first_name}
                onChange={(e) => update("first_name", e.target.value)}
                className="focus-visible:ring-primary/50"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="last_name" className="font-medium">
                Last name
              </Label>
              <Input
                id="last_name"
                autoComplete="family-name"
                value={form.last_name}
                onChange={(e) => update("last_name", e.target.value)}
                className="focus-visible:ring-primary/50"
                required
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email" className="font-medium">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              value={form.email}
              onChange={(e) => update("email", e.target.value)}
              className="focus-visible:ring-primary/50"
              required
            />
          </div>
          <div className="space-y-1.5 relative">
            <Label htmlFor="password" className="font-medium">
              Password
            </Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                value={form.password}
                onChange={(e) => update("password", e.target.value)}
                className="pr-10 focus-visible:ring-primary/50"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-0 top-0 h-full px-3 text-muted-foreground hover:text-foreground focus:outline-none focus-visible:text-foreground focus-visible:ring-2 focus-visible:ring-primary/50 rounded-r-xl transition-colors"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <p className="text-[11px] text-muted-foreground">At least 8 characters.</p>
          </div>

          {error && (
            <p
              role="alert"
              className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive"
            >
              {error}
            </p>
          )}

          <Button
            type="submit"
            className="w-full active:scale-[0.98] transition-transform"
            disabled={submitting}
          >
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Preparing your workspace...
              </>
            ) : (
              "Create account"
            )}
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Already thinking with Bazzix?{" "}
          <Link
            to="/login"
            className="font-medium text-foreground underline underline-offset-4 hover:text-primary transition-colors"
          >
            Sign in
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}
