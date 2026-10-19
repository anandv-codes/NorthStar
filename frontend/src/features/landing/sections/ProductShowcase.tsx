import { CheckCircle, Sparkle } from "@phosphor-icons/react";
import { useScrollReveal } from "../../../shared/animation/useScrollReveal";
import { Container } from "../../../shared/ui/Container";
import { SectionHeading } from "../../../shared/ui/SectionHeading";

const SUMMARY_HIGHLIGHTS = [
  "3 notes captured today",
  "2 open questions resolved",
  "1 risk flagged for review",
];

export function ProductShowcase() {
  const containerRef = useScrollReveal<HTMLDivElement>({ selector: "[data-reveal]" });

  return (
    <section className="py-20 sm:py-28" ref={containerRef}>
      <Container>
        <SectionHeading
          eyebrow="Product"
          title="One place for every note, question and task"
          description="NorthStar quietly organizes everything you capture into a living dashboard — so you never lose track of what matters."
          className="mb-14"
        />

        <div
          data-reveal
          className="relative mx-auto max-w-5xl overflow-hidden rounded-3xl border border-neutral-200 bg-neutral-50 p-3 shadow-soft sm:p-5"
        >
          <div className="rounded-2xl border border-neutral-200 bg-white">
            <div className="flex items-center gap-2 border-b border-neutral-200 px-5 py-3.5">
              <span className="h-2.5 w-2.5 rounded-full bg-neutral-300" />
              <span className="h-2.5 w-2.5 rounded-full bg-neutral-300" />
              <span className="h-2.5 w-2.5 rounded-full bg-neutral-300" />
              <p className="ml-3 text-xs font-medium text-neutral-400">northstar.app/app/dashboard</p>
            </div>

            <div className="grid grid-cols-1 gap-5 p-5 sm:p-8 lg:grid-cols-3">
              <div className="lg:col-span-2 space-y-5">
                <div className="rounded-xl border border-neutral-200 p-5">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-neutral-950">Daily summary</p>
                    <span className="inline-flex items-center gap-1 rounded-full bg-accent-50 px-2.5 py-1 text-[11px] font-semibold text-accent-700">
                      <Sparkle size={12} weight="fill" /> Generated
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-relaxed text-neutral-600">
                    You mostly focused on the Q3 launch plan today — three
                    follow-up tasks were created and one open question about
                    pricing is still unresolved.
                  </p>
                </div>

                <div className="rounded-xl border border-neutral-200 p-5">
                  <p className="text-sm font-semibold text-neutral-950">Open tasks</p>
                  <ul className="mt-3 space-y-2.5">
                    {["Draft pricing one-pager", "Follow up with design on logo", "Review onboarding copy"].map(
                      (task) => (
                        <li key={task} className="flex items-center gap-2.5 text-sm text-neutral-600">
                          <CheckCircle size={16} className="shrink-0 text-neutral-300" />
                          {task}
                        </li>
                      ),
                    )}
                  </ul>
                </div>
              </div>

              <div className="space-y-5">
                <div className="rounded-xl bg-neutral-950 p-5 text-white">
                  <p className="text-sm font-semibold">This week at a glance</p>
                  <ul className="mt-3 space-y-2 text-sm text-neutral-300">
                    {SUMMARY_HIGHLIGHTS.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
                <div className="rounded-xl border border-neutral-200 p-5">
                  <p className="text-sm font-semibold text-neutral-950">Recall due</p>
                  <p className="mt-2 text-3xl font-semibold text-neutral-950">12</p>
                  <p className="mt-1 text-xs text-neutral-500">cards ready for review</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Container>
    </section>
  );
}
