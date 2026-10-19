import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

let registered = false;
function ensureRegistered() {
  if (!registered) {
    gsap.registerPlugin(ScrollTrigger);
    registered = true;
  }
}

interface ScrollRevealOptions {
  /** CSS selector (within the container) for items to stagger-reveal. Defaults to direct children with [data-reveal]. */
  selector?: string;
  y?: number;
  stagger?: number;
  duration?: number;
  start?: string;
}

/**
 * Attaches a subtle fade/slide-up reveal to matched elements once they enter the viewport.
 * Respects prefers-reduced-motion by skipping the animation and rendering the final state.
 */
export function useScrollReveal<T extends HTMLElement = HTMLDivElement>(
  options: ScrollRevealOptions = {},
): RefObject<T> {
  const containerRef = useRef<T>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    ensureRegistered();
    const {
      selector = "[data-reveal]",
      y = 16,
      stagger = 0.08,
      duration = 0.6,
      start = "top 85%",
    } = options;

    const targets = container.querySelectorAll(selector);
    if (targets.length === 0) {
      return;
    }

    const mm = gsap.matchMedia();
    mm.add("(prefers-reduced-motion: no-preference)", () => {
      const tween = gsap.from(targets, {
        opacity: 0,
        y,
        duration,
        ease: "power2.out",
        stagger,
        scrollTrigger: {
          trigger: container,
          start,
          toggleActions: "play none none reverse",
        },
      });
      return () => tween.scrollTrigger?.kill();
    });

    mm.add("(prefers-reduced-motion: reduce)", () => {
      gsap.set(targets, { opacity: 1, y: 0 });
    });

    return () => mm.revert();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return containerRef;
}
