import { ArrowRight } from "@phosphor-icons/react";
import { useNavigate } from "react-router-dom";
import { useScrollReveal } from "../../../shared/animation/useScrollReveal";
import { Button } from "../../../shared/ui/Button";
import { Container } from "../../../shared/ui/Container";

export function FinalCTA() {
  const containerRef = useScrollReveal<HTMLDivElement>();
  const navigate = useNavigate();

  return (
    <section className="py-20 sm:py-28" ref={containerRef}>
      <Container>
        <div
          data-reveal
          className="relative overflow-hidden rounded-3xl bg-neutral-950 px-8 py-16 text-center sm:px-16"
        >
          <h2 className="font-display text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Your notes deserve a second brain.
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-base leading-relaxed text-neutral-300">
            Create an account, write your first note, and let NorthStar handle the rest.
          </p>
          <div className="mt-8 flex justify-center">
            <Button variant="secondary" size="lg" onClick={() => navigate("/register")}>
              Try it free
              <ArrowRight size={18} weight="bold" />
            </Button>
          </div>
        </div>
      </Container>
    </section>
  );
}
