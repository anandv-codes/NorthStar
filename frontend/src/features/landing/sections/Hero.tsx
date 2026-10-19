import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import gsap from "gsap";
import { Brain, ChatCircleDots, ClockCounterClockwise, NotePencil } from "@phosphor-icons/react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../../shared/ui/Button";
import { Container } from "../../../shared/ui/Container";

export function Hero() {
  const sceneRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) {
      return;
    }
    const mm = gsap.matchMedia();
    mm.add("(prefers-reduced-motion: no-preference)", () => {
      const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
      tl.from("[data-hero-eyebrow]", { opacity: 0, y: 12, duration: 0.5 })
        .from("[data-hero-title]", { opacity: 0, y: 18, duration: 0.6 }, "-=0.3")
        .from("[data-hero-copy]", { opacity: 0, y: 14, duration: 0.5 }, "-=0.35")
        .from("[data-hero-cta]", { opacity: 0, y: 10, duration: 0.45 }, "-=0.3")
        .from(
          "[data-hero-card]",
          { opacity: 0, y: 28, scale: 0.96, duration: 0.6, stagger: 0.12 },
          "-=0.35",
        );
      return () => tl.kill();
    });
    return () => mm.revert();
  }, []);

  return (
    <section className="relative overflow-hidden pb-20 pt-16 sm:pb-28 sm:pt-24">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[520px] bg-[radial-gradient(60%_60%_at_50%_0%,rgba(79,70,229,0.08),transparent)]"
      />
      <Container ref={sceneRef}>
        <div className="mx-auto max-w-3xl text-center">
          <p
            data-hero-eyebrow
            className="inline-flex items-center gap-2 rounded-full border border-neutral-200 bg-white px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.15em] text-neutral-600 shadow-sm"
          >
            Your second brain, on autopilot
          </p>
          <h1
            data-hero-title
            className="mt-6 font-display text-4xl font-semibold leading-[1.1] tracking-tight text-neutral-950 sm:text-6xl"
          >
            Think out loud.
            <br />
            Let <span className="text-accent-600">NorthStar</span> remember.
          </h1>
          <p
            data-hero-copy
            className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-neutral-600 sm:text-lg"
          >
            Drop in quick notes and NorthStar turns them into daily and weekly
            summaries, surfaces tasks and open questions, and lets you chat
            with everything you've ever written down.
          </p>
          <div data-hero-cta className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button size="lg" onClick={() => navigate("/register")}>
              Try it free
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() =>
                document.querySelector("#how-it-works")?.scrollIntoView({ behavior: "smooth" })
              }
            >
              See how it works
            </Button>
          </div>
        </div>

        <div className="relative mx-auto mt-16 grid max-w-5xl grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <HeroCard
            icon={<NotePencil size={20} weight="bold" />}
            title="Note Taker"
            description="Capture a thought in seconds, no formatting required."
          />
          <HeroCard
            icon={<Brain size={20} weight="bold" />}
            title="Daily & weekly summaries"
            description="NorthStar writes the recap so you don't have to."
          />
          <HeroCard
            icon={<ChatCircleDots size={20} weight="bold" />}
            title="Chat with your notes"
            description="Ask questions, get grounded answers from your own memory."
          />
          <HeroCard
            icon={<ClockCounterClockwise size={20} weight="bold" />}
            title="Recall"
            description="Spaced-repetition review so key ideas actually stick."
          />
        </div>
      </Container>
    </section>
  );
}

function HeroCard({
  icon,
  title,
  description,
}: {
  icon: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div
      data-hero-card
      className="rounded-2xl border border-neutral-200 bg-white p-5 text-left shadow-soft transition-transform duration-300 hover:-translate-y-1"
    >
      <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-neutral-950 text-white">
        {icon}
      </div>
      <p className="mt-4 text-sm font-semibold text-neutral-950">{title}</p>
      <p className="mt-1.5 text-sm leading-relaxed text-neutral-500">{description}</p>
    </div>
  );
}
