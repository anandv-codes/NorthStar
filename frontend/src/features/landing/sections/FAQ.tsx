import { useState } from "react";
import { CaretDown } from "@phosphor-icons/react";
import { useScrollReveal } from "../../../shared/animation/useScrollReveal";
import { Container } from "../../../shared/ui/Container";
import { SectionHeading } from "../../../shared/ui/SectionHeading";

const FAQS = [
  {
    question: "Do I need to format my notes in a special way?",
    answer:
      "No. Write the way you think. NorthStar extracts tasks, questions, decisions and concepts from plain, unstructured text.",
  },
  {
    question: "How are daily and weekly summaries generated?",
    answer:
      "NorthStar reviews everything you logged in the period and writes a short narrative recap, along with the stats behind it, so you can regenerate it any time.",
  },
  {
    question: "What is Recall and how does it work?",
    answer:
      "Recall turns the key ideas from your notes into spaced-repetition style flashcards, similar to Anki, so important concepts resurface right before you'd forget them.",
  },
  {
    question: "Can I chat with my own notes?",
    answer:
      "Yes — the Chat workspace answers questions using your captured notes as grounded context, and tells you when it isn't confident enough to answer.",
  },
  {
    question: "Is my data private?",
    answer:
      "Your notes and summaries are scoped to your account only. You can delete notes and recall data at any time.",
  },
];

export function FAQ() {
  const containerRef = useScrollReveal<HTMLDivElement>();
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <section id="faq" className="py-20 sm:py-28" ref={containerRef}>
      <Container className="max-w-3xl">
        <SectionHeading eyebrow="FAQ" title="Questions, answered" className="mb-12" />

        <div data-reveal className="divide-y divide-neutral-200 rounded-2xl border border-neutral-200">
          {FAQS.map((item, index) => {
            const isOpen = openIndex === index;
            return (
              <div key={item.question}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left"
                  aria-expanded={isOpen}
                  onClick={() => setOpenIndex(isOpen ? null : index)}
                >
                  <span className="text-sm font-semibold text-neutral-950 sm:text-base">{item.question}</span>
                  <CaretDown
                    size={18}
                    className={`shrink-0 text-neutral-400 transition-transform duration-200 ${
                      isOpen ? "rotate-180" : ""
                    }`}
                  />
                </button>
                {isOpen ? (
                  <div className="px-6 pb-5 text-sm leading-relaxed text-neutral-600">{item.answer}</div>
                ) : null}
              </div>
            );
          })}
        </div>
      </Container>
    </section>
  );
}
