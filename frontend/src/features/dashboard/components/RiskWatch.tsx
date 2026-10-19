import { WarningCircle } from "@phosphor-icons/react";
import type { MemoryRisk } from "../../../shared/api/httpClient";
import { EmptyState } from "./TaskBoard";

const SEVERITY_STYLES: Record<string, string> = {
  high: "bg-red-50 text-red-700",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-neutral-100 text-neutral-600",
};

interface RiskWatchProps {
  risks: MemoryRisk[];
  onResolve: (risk: MemoryRisk) => void;
}

export function RiskWatch({ risks, onResolve }: RiskWatchProps) {
  if (risks.length === 0) {
    return <EmptyState label="No risks flagged. Nice and calm." />;
  }

  return (
    <ul className="space-y-3">
      {risks.map((risk) => (
        <li
          key={risk.risk_id}
          className="flex items-start justify-between gap-3 rounded-xl border border-neutral-100 p-3"
        >
          <div className="flex items-start gap-2.5">
            <WarningCircle size={18} className="mt-0.5 shrink-0 text-neutral-400" />
            <div>
              <p className="text-sm leading-relaxed text-neutral-700">{risk.risk}</p>
              {risk.severity ? (
                <span
                  className={`mt-1.5 inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize ${
                    SEVERITY_STYLES[risk.severity.toLowerCase()] ?? SEVERITY_STYLES.low
                  }`}
                >
                  {risk.severity}
                </span>
              ) : null}
            </div>
          </div>
          <button
            type="button"
            onClick={() => onResolve(risk)}
            className="shrink-0 cursor-pointer text-xs font-semibold text-neutral-400 hover:text-neutral-950"
          >
            Resolve
          </button>
        </li>
      ))}
    </ul>
  );
}
