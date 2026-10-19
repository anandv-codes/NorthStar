import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Timer } from "@phosphor-icons/react";
import clsx from "clsx";
import { getTodayRecallSeconds } from "../../../shared/lib/recallTime";

function toneForMinutes(minutes: number): string {
  if (minutes <= 0) return "bg-neutral-50 text-neutral-500";
  if (minutes < 10) return "bg-accent-50 text-accent-700";
  if (minutes < 20) return "bg-accent-100 text-accent-700";
  if (minutes < 30) return "bg-accent-300 text-accent-900";
  return "bg-accent-600 text-white";
}

export function RecallToday() {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const sync = () => setSeconds(getTodayRecallSeconds());
    sync();
    window.addEventListener("focus", sync);
    const interval = setInterval(sync, 5000);
    return () => {
      window.removeEventListener("focus", sync);
      clearInterval(interval);
    };
  }, []);

  const minutes = Math.round(seconds / 60);

  return (
    <Link
      to="/app/recall"
      className={clsx(
        "flex h-full flex-col justify-between rounded-2xl border border-neutral-200 p-6 shadow-card transition-colors",
        toneForMinutes(minutes),
      )}
    >
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold">Recall today</p>
        <Timer size={18} weight="bold" className="opacity-60" />
      </div>
      <div>
        <p className="font-display text-3xl font-semibold">
          {minutes}
          <span className="ml-1 text-base font-medium">min</span>
        </p>
        <p className="mt-1 text-xs opacity-80">
          {minutes > 0 ? "Keep the streak going" : "No review session yet today"}
        </p>
      </div>
    </Link>
  );
}
