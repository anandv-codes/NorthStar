import { useLayoutEffect, useRef } from "react";
import type { RefObject } from "react";

const MAX_FLIP_ITEMS = 50;
const FLIP_DURATION_MS = 200;
const FLIP_EASING = "cubic-bezier(0.22, 1, 0.36, 1)";

/**
 * Animates items whose vertical position changed since the previous render.
 * New and removed items are left to their own enter/exit treatment.
 */
export function useListFlip<T extends HTMLElement = HTMLDivElement>(): RefObject<T> {
  const containerRef = useRef<T>(null);
  const previousPositions = useRef(new Map<string, DOMRect>());
  const animations = useRef(new Map<string, Animation>());

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const nodes = Array.from(container.querySelectorAll<HTMLElement>("[data-flip-id]"));
    const nodesById = new Map<string, HTMLElement>();
    nodes.forEach((node) => {
      const id = node.dataset.flipId;
      if (id) nodesById.set(id, node);
    });

    const cancelAnimations = () => {
      animations.current.forEach((animation) => animation.cancel());
      animations.current.clear();
    };

    if (nodesById.size > MAX_FLIP_ITEMS) {
      cancelAnimations();
      previousPositions.current.clear();
      return;
    }

    cancelAnimations();

    const nextPositions = new Map<string, DOMRect>();
    nodesById.forEach((node, id) => {
      nextPositions.set(id, node.getBoundingClientRect());
    });

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!reduceMotion && previousPositions.current.size > 0) {
      nextPositions.forEach((next, id) => {
        const previous = previousPositions.current.get(id);
        const node = nodesById.get(id);
        if (!previous || !node) return;

        const deltaY = previous.top - next.top;
        if (Math.abs(deltaY) < 1) return;

        const animation = node.animate(
          [{ transform: `translateY(${deltaY}px)` }, { transform: "translateY(0)" }],
          { duration: FLIP_DURATION_MS, easing: FLIP_EASING },
        );
        animations.current.set(id, animation);
        void animation.finished
          .catch(() => undefined)
          .then(() => {
            if (animations.current.get(id) === animation) {
              animations.current.delete(id);
            }
          });
      });
    }

    previousPositions.current = nextPositions;
  });

  useLayoutEffect(
    () => () => {
      animations.current.forEach((animation) => animation.cancel());
      animations.current.clear();
    },
    [],
  );

  return containerRef;
}
