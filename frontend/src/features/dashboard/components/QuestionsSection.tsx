import { MemoryQuestion } from "../../../shared/api/httpClient";

interface QuestionsSectionProps {
  questions: MemoryQuestion[];
  onToggleStatus: (question: MemoryQuestion) => Promise<void>;
  activeQuestionId: string | null;
}

export function QuestionsSection({
  questions,
  onToggleStatus,
  activeQuestionId,
}: QuestionsSectionProps) {
  return (
    <section>
      <h2>Questions</h2>
      {questions.length === 0 ? (
        <p>No questions found.</p>
      ) : (
        <ul>
          {questions.map((question) => {
            const isOpen = question.status === "open";
            return (
              <li key={question.question_id}>
                <span>{question.question} ({question.status}) </span>
                <button
                  onClick={() => onToggleStatus(question)}
                  disabled={activeQuestionId === question.question_id}
                >
                  {isOpen ? "Close" : "Reopen"}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
