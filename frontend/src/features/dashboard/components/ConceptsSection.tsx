import { MemoryConcept } from "../../../shared/api/httpClient";

interface ConceptsSectionProps {
  concepts: MemoryConcept[];
  onToggleLearned: (concept: MemoryConcept) => Promise<void>;
  activeConceptId: string | null;
}

export function ConceptsSection({
  concepts,
  onToggleLearned,
  activeConceptId,
}: ConceptsSectionProps) {
  return (
    <section>
      <h2>Concepts</h2>
      {concepts.length === 0 ? (
        <p>No concepts found.</p>
      ) : (
        <ul>
          {concepts.map((concept) => {
            const isLearned = concept.status === "learned";
            return (
              <li key={concept.concept_id}>
                <span>{concept.concept} ({concept.status}) </span>
                <button
                  onClick={() => onToggleLearned(concept)}
                  disabled={activeConceptId === concept.concept_id}
                >
                  {isLearned ? "Reopen" : "Mark learned"}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
