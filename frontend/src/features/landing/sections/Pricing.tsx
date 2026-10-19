import { Check } from "@phosphor-icons/react";
import { useNavigate } from "react-router-dom";
import { useScrollReveal } from "../../../shared/animation/useScrollReveal";
import { Button } from "../../../shared/ui/Button";
import { Container } from "../../../shared/ui/Container";
import { SectionHeading } from "../../../shared/ui/SectionHeading";

const PLANS = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    description: "Get started and see if NorthStar fits how you think.",
    features: ["Unlimited note capture", "Daily summaries", "Basic chat with your notes", "Up to 50 recall cards"],
    cta: "Start for free",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "$12",
    period: "per month",
    description: "For people who want their second brain working around the clock.",
    features: [
      "Everything in Free",
      "Daily & weekly summaries",
      "Unlimited chat with grounded answers",
      "Unlimited recall decks",
      "Priority support",
    ],
    cta: "Try Pro free",
    highlighted: true,
  },
  {
    name: "Team",
    price: "Custom",
    period: "contact us",
    description: "Shared memory and summaries across your whole team.",
    features: ["Everything in Pro", "Shared workspaces", "Admin controls", "SSO & priority onboarding"],
    cta: "Contact sales",
    highlighted: false,
  },
];

export function Pricing() {
  const containerRef = useScrollReveal<HTMLDivElement>();
  const navigate = useNavigate();

  return (
    <section id="pricing" className="bg-neutral-50 py-20 sm:py-28" ref={containerRef}>
      <Container>
        <SectionHeading
          eyebrow="Pricing"
          title="Simple pricing that scales with you"
          description="Start free. Upgrade when NorthStar becomes part of how you work."
          className="mb-14"
        />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              data-reveal
              className={`flex flex-col rounded-2xl border p-7 ${
                plan.highlighted
                  ? "border-neutral-950 bg-neutral-950 text-white shadow-soft lg:-translate-y-3"
                  : "border-neutral-200 bg-white"
              }`}
            >
              <p className={`text-sm font-semibold ${plan.highlighted ? "text-white" : "text-neutral-950"}`}>
                {plan.name}
              </p>
              <div className="mt-4 flex items-baseline gap-1.5">
                <span className="font-display text-4xl font-semibold">{plan.price}</span>
                <span className={plan.highlighted ? "text-sm text-neutral-400" : "text-sm text-neutral-500"}>
                  {plan.period}
                </span>
              </div>
              <p className={`mt-3 text-sm leading-relaxed ${plan.highlighted ? "text-neutral-300" : "text-neutral-600"}`}>
                {plan.description}
              </p>

              <ul className="mt-6 flex-1 space-y-3">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2.5 text-sm">
                    <Check
                      size={16}
                      weight="bold"
                      className={`mt-0.5 shrink-0 ${plan.highlighted ? "text-white" : "text-neutral-950"}`}
                    />
                    <span className={plan.highlighted ? "text-neutral-200" : "text-neutral-700"}>{feature}</span>
                  </li>
                ))}
              </ul>

              <Button
                variant={plan.highlighted ? "secondary" : "outline"}
                className={`mt-8 w-full ${plan.highlighted ? "" : ""}`}
                onClick={() => navigate("/register")}
              >
                {plan.cta}
              </Button>
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
}
