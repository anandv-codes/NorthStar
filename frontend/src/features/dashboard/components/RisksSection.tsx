import { MemoryRisk } from "../../../shared/api/httpClient";

interface RisksSectionProps {
  risks: MemoryRisk[];
  onToggleResolved: (risk: MemoryRisk) => Promise<void>;
  activeRiskId: string | null;
}

export function RisksSection({ risks, onToggleResolved, activeRiskId }: RisksSectionProps) {
  return (
    <section>
      <h2>Risks</h2>
      {risks.length === 0 ? (
        <p>No risks found.</p>
      ) : (
        <ul>
          {risks.map((risk) => {
            const isResolved = risk.status === "resolved";
            return (
              <li key={risk.risk_id}>
                <span>{risk.risk} ({risk.status}) </span>
                <button
                  onClick={() => onToggleResolved(risk)}
                  disabled={activeRiskId === risk.risk_id}
                >
                  {isResolved ? "Reopen" : "Resolve"}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
