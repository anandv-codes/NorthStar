import {
  Brain,
  CalendarCheck,
  ChatCircleDots,
  ClockCounterClockwise,
  ListChecks,
  NotePencil,
} from "@phosphor-icons/react";
import { useScrollReveal } from "../../../shared/animation/useScrollReveal";
import { Container } from "../../../shared/ui/Container";
import { SectionHeading } from "../../../shared/ui/SectionHeading";

const FEATURES = [
  {
    icon: NotePencil,
    title: "Note Taker",
    description: "A distraction-free capture box for thoughts, meeting notes and ideas on the go.",
  },
  {
    icon: CalendarCheck,
    title: "Daily & weekly summaries",
    description: "Auto-generated narratives that recap what you worked on and what needs attention.",
  },
  {
    icon: ChatCircleDots,
    title: "Chat with your memory",
    description: "Ask questions in plain language and get answers grounded in your own notes.",
  },
  {
    icon: ListChecks,
    title: "Tasks, questions & decisions",
    description: "Action items and open loops are extracted automatically so nothing slips through.",
  },
  {
    icon: ClockCounterClockwise,
    title: "Recall",
    description: "Anki-style spaced-repetition review to make key concepts stick long-term.",
  },
  {
    icon: Brain,
    title: "Concept graph",
    description: "See how your ideas connect over time as NorthStar builds a map of your thinking.",
  },
];

export function FeatureGrid() {
  const containerRef = useScrollReveal<HTMLDivElement>();

  return (
    <section id="features" className="py-20 sm:py-28" ref={containerRef}>
      <Container>
        <SectionHeading
          eyebrow="Features"
          title="Everything a second brain needs"
          description="Built around how you actually think — fast capture in, useful structure out."
          className="mb-14"
        />

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              data-reveal
              className="group rounded-2xl border border-neutral-200 p-6 transition-colors duration-200 hover:border-neutral-950"
            >
              <div className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-neutral-100 text-neutral-950 transition-colors duration-200 group-hover:bg-neutral-950 group-hover:text-white">
                <feature.icon size={20} weight="bold" />
              </div>
              <p className="mt-5 text-sm font-semibold text-neutral-950">{feature.title}</p>
              <p className="mt-2 text-sm leading-relaxed text-neutral-600">{feature.description}</p>
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
}
