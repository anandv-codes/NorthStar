import { ChatCircleDots, NotePencil, Sparkle, ClockCounterClockwise } from "@phosphor-icons/react";
import { useScrollReveal } from "../../../shared/animation/useScrollReveal";
import { Container } from "../../../shared/ui/Container";
import { SectionHeading } from "../../../shared/ui/SectionHeading";

const STEPS = [
  {
    icon: NotePencil,
    title: "Capture a note",
    description: "Jot down a thought, a meeting recap, or a random idea — no structure required.",
  },
  {
    icon: Sparkle,
    title: "NorthStar organizes it",
    description: "Tasks, questions, decisions and concepts are extracted automatically in the background.",
  },
  {
    icon: ChatCircleDots,
    title: "Get daily & weekly summaries",
    description: "Open your dashboard to a narrative recap built from everything you've logged.",
  },
  {
    icon: ClockCounterClockwise,
    title: "Recall what matters",
    description: "Review key ideas with spaced-repetition style flashcards so they actually stick.",
  },
];

export function HowItWorks() {
  const containerRef = useScrollReveal<HTMLDivElement>();

  return (
    <section id="how-it-works" className="bg-neutral-50 py-20 sm:py-28" ref={containerRef}>
      <Container>
        <SectionHeading
          eyebrow="How it works"
          title="From a quick note to a clear mind"
          description="Four simple steps turn scattered thoughts into something you can act on."
          className="mb-14"
        />

        <div className="relative grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, index) => (
            <div
              key={step.title}
              data-reveal
              className="relative rounded-2xl border border-neutral-200 bg-white p-6 shadow-card"
            >
              <span className="absolute right-5 top-5 font-display text-3xl font-semibold text-neutral-100">
                0{index + 1}
              </span>
              <div className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-neutral-950 text-white">
                <step.icon size={20} weight="bold" />
              </div>
              <p className="mt-5 text-sm font-semibold text-neutral-950">{step.title}</p>
              <p className="mt-2 text-sm leading-relaxed text-neutral-600">{step.description}</p>
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
}
