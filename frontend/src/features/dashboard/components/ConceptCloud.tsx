import type { MemoryConcept } from "../../../shared/api/httpClient";
import { EmptyState } from "./TaskBoard";

export function ConceptCloud({ concepts }: { concepts: MemoryConcept[] }) {
  if (concepts.length === 0) {
    return <EmptyState label="Concepts you write about will appear here." />;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {concepts.map((concept) => (
        <span
          key={concept.concept_id}
          className="rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1.5 text-xs font-medium text-neutral-700"
        >
          {concept.concept}
        </span>
      ))}
    </div>
  );
}
