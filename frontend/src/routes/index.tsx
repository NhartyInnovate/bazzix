import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { ArrowRight, Target, Zap, Lock } from "lucide-react";
import { motion } from "motion/react";

import { Button } from "@/components/ui/button";
import { BazzixWordmark, BazzixMark } from "@/components/bazzix/Logo";
import { ThemeToggle } from "@/components/bazzix/ThemeToggle";
import { useAuth } from "@/lib/auth";

export const Route = createFileRoute("/")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Bazzix — Think Beyond." },
      {
        name: "description",
        content:
          "Bazzix is an intelligent workspace for thinking, researching, writing and solving problems with AI.",
      },
      { property: "og:title", content: "Bazzix — Think Beyond." },
      {
        property: "og:description",
        content: "An intelligent workspace for thinking, learning and creating.",
      },
    ],
  }),
  component: Landing,
});

function Landing() {
  const { status } = useAuth();
  const navigate = useNavigate();
  const titleText = "Think Beyond.";

  useEffect(() => {
    if (status === "authenticated") navigate({ to: "/workspace", replace: true });
  }, [status, navigate]);

  return (
    <div className="relative min-h-dvh bg-background text-foreground overflow-hidden">
      {/* Soft, Deep Ambient Glow */}
      <div
        className="pointer-events-none absolute left-1/2 top-0 z-0 h-[700px] w-[1200px] -translate-x-1/2 opacity-25 blur-[120px]"
        style={{
          background:
            "radial-gradient(ellipse at top, rgba(99, 102, 241, 0.15) 0%, rgba(59, 130, 246, 0.05) 45%, transparent 70%)",
        }}
      />

      <header className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <BazzixWordmark />
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <Button variant="ghost" asChild className="text-sm">
            <Link to="/login">Sign in</Link>
          </Button>
          <Button asChild className="text-sm">
            <Link to="/register">Get started</Link>
          </Button>
        </div>
      </header>

      <main className="relative z-10 mx-auto flex max-w-5xl flex-col items-center px-6 pb-24 pt-20 text-center md:pt-32">
        <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-border/40 bg-surface/40 px-3.5 py-1.5 text-[11px] font-medium tracking-wide uppercase text-muted-foreground backdrop-blur-sm">
          <BazzixMark className="h-3.5 w-3.5 opacity-70" /> Where great thinking continues
        </div>
        <h1 className="text-balance font-serif text-5xl font-medium leading-[1.05] tracking-tight text-foreground md:text-7xl lg:text-[5.5rem]">
          {titleText.split("").map((char, index) => (
            <motion.span
              key={index}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.45,
                delay: index * 0.05,
                ease: [0.215, 0.61, 0.355, 1.0],
              }}
              style={{ display: "inline-block", whiteSpace: char === " " ? "pre" : "normal" }}
            >
              {char}
            </motion.span>
          ))}
        </h1>
        <p className="mt-8 max-w-2xl text-pretty text-lg text-muted-foreground md:text-xl leading-relaxed">
          A premium AI workspace where ideas become finished work. Not another chatbot — a dedicated
          home for your best thinking.
        </p>

        <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row">
          <Button
            asChild
            size="lg"
            className="group h-12 min-w-48 rounded-xl text-[15px] shadow-[0_0_40px_rgba(59,130,246,0.1)] transition-all hover:shadow-[0_0_60px_rgba(59,130,246,0.15)]"
          >
            <Link to="/register">
              Open Your Workspace
              <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
            </Link>
          </Button>
          <Button
            asChild
            size="lg"
            variant="ghost"
            className="h-12 rounded-xl text-[15px] text-foreground/70 transition-all duration-200 hover:bg-surface/50 hover:text-foreground cursor-pointer"
          >
            <Link to="/login">I already have an account</Link>
          </Button>
        </div>

        {/* Social Proof Placeholder */}
        <div className="mt-12 flex flex-col items-center gap-4 opacity-70">
          <div className="flex -space-x-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full border-2 border-background bg-surface"
              >
                <img
                  src={`https://i.pravatar.cc/100?img=${i * 11 + 2}`}
                  alt={`User ${i}`}
                  className="h-full w-full object-cover"
                />
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground max-w-sm text-balance">
            Built for focused thinking. Loved by students, developers, founders, researchers and
            creators.
          </p>
        </div>

        {/* Workspace Preview Mockup */}
        <div className="mt-24 w-full max-w-5xl rounded-2xl border border-border/40 bg-background/50 p-2 shadow-2xl shadow-primary/5 backdrop-blur-xl sm:p-4">
          <div className="flex h-[550px] w-full overflow-hidden rounded-xl border border-border/50 bg-background shadow-sm text-left">
            {/* Sidebar Mockup */}
            <div className="hidden w-64 flex-col border-r border-border/50 bg-sidebar/50 sm:flex">
              <div className="flex h-14 items-center px-4">
                <BazzixWordmark className="opacity-70" />
              </div>
              <div className="flex-1 px-3 py-4 space-y-6">
                <div>
                  <div className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                    Today
                  </div>
                  <div className="flex h-9 w-full items-center rounded-lg bg-sidebar-accent/80 border-l-[3px] border-primary px-3 text-sm font-medium text-sidebar-accent-foreground">
                    Product Strategy
                  </div>
                  <div className="mt-0.5 flex h-9 w-full items-center rounded-lg px-3 text-sm text-muted-foreground hover:bg-sidebar-accent/50">
                    Market Research
                  </div>
                </div>
                <div>
                  <div className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                    Yesterday
                  </div>
                  <div className="flex h-9 w-full items-center rounded-lg px-3 text-sm text-muted-foreground hover:bg-sidebar-accent/50">
                    YCD Combinator App
                  </div>
                  <div className="mt-0.5 flex h-9 w-full items-center rounded-lg px-3 text-sm text-muted-foreground hover:bg-sidebar-accent/50">
                    Q3 Financials
                  </div>
                </div>
              </div>
            </div>
            {/* Chat Mockup */}
            <div className="flex flex-1 flex-col bg-background">
              <div className="flex h-14 items-center justify-between border-b border-border/30 px-6">
                <div className="font-medium text-sm text-foreground/90">Product Strategy</div>
                <div className="flex gap-2">
                  <div className="h-7 w-7 rounded-md bg-surface border border-border/50" />
                  <div className="h-7 w-7 rounded-md bg-surface border border-border/50" />
                </div>
              </div>
              <div className="flex-1 p-6 space-y-8 overflow-hidden">
                <div className="flex justify-end">
                  <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-surface px-5 py-3.5 text-[0.95rem] text-foreground shadow-sm">
                    Help me structure the product requirements for Phase 3.
                  </div>
                </div>
                <div className="flex gap-4 px-2">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border bg-elevated text-foreground/80">
                    <BazzixMark className="h-4 w-4" />
                  </div>
                  <div className="flex-1 space-y-3.5 pt-1.5 opacity-80">
                    <div className="h-4 w-3/4 rounded-sm bg-surface" />
                    <div className="h-4 w-full rounded-sm bg-surface" />
                    <div className="h-4 w-5/6 rounded-sm bg-surface" />
                    <div className="mt-6 h-32 w-[90%] rounded-xl border border-border/50 bg-[#161618] overflow-hidden">
                      <div className="h-8 w-full border-b border-white/5 bg-[#1c1c1e]" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <section className="mt-32 grid w-full grid-cols-1 gap-6 text-left sm:grid-cols-3">
          {[
            {
              title: "Think Clearly",
              icon: Target,
              body: "No clutter, no noise. A minimalist space that disappears so your ideas can take the lead.",
            },
            {
              title: "Never Lose Your Thinking",
              icon: Lock,
              body: "Bazzix remembers your thinking, naturally organizing your workspaces so you can focus on creating.",
            },
            {
              title: "Read Beautifully",
              icon: Zap,
              body: "Every response is rendered with stunning, document-first typography designed for deep reading.",
            },
          ].map((f) => {
            const CardIcon = f.icon;
            return (
              <div
                key={f.title}
                className="group rounded-2xl border border-border/60 bg-surface/30 p-6 transition-all duration-300 hover:-translate-y-1 hover:border-primary/20 hover:bg-surface/60 hover:shadow-xl hover:shadow-primary/5"
              >
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-elevated text-foreground/80 shadow-sm transition-colors group-hover:border-primary/30 group-hover:text-primary">
                  <CardIcon className="h-4 w-4" />
                </div>
                <h3 className="text-base font-semibold text-foreground tracking-tight">
                  {f.title}
                </h3>
                <p className="mt-2 text-sm text-muted-foreground/90 leading-relaxed text-pretty">
                  {f.body}
                </p>
              </div>
            );
          })}
        </section>

        <section className="mt-40 mb-10 flex flex-col items-center text-center">
          <h2 className="font-serif text-3xl font-medium tracking-tight md:text-4xl">
            Ready to think differently?
          </h2>
          <Button asChild size="lg" className="group mt-8 min-w-44 h-12 rounded-xl text-[15px]">
            <Link to="/register">
              Start your first workspace
              <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
            </Link>
          </Button>
        </section>
      </main>

      <footer className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-6 py-6 text-xs text-muted-foreground">
        <span>© {new Date().getFullYear()} Bazzix</span>
        <span>Think Beyond.</span>
      </footer>
    </div>
  );
}
