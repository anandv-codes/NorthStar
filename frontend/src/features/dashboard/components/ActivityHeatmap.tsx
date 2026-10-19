import { useEffect, useMemo, useState } from "react";
import { fetchNoteActivity, type NoteActivityDay } from "../../../shared/api/httpClient";

const WEEKDAY_LABELS = ["S", "M", "T", "W", "T", "F", "S"];

function colorForCount(count: number): string {
  if (count <= 0) return "bg-neutral-100";
  if (count === 1) return "bg-accent-200";
  if (count === 2) return "bg-accent-300";
  if (count <= 4) return "bg-accent-500";
  if (count <= 6) return "bg-accent-600";
  return "bg-accent-700";
}

interface DayCell {
  day: number | null;
  count: number;
  isToday: boolean;
}

export function ActivityHeatmap() {
  const [activity, setActivity] = useState<NoteActivityDay[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchNoteActivity()
      .then((data) => {
        if (!cancelled) setActivity(data);
      })
      .catch(() => {
        if (!cancelled) setActivity([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const { cells, monthLabel } = useMemo(() => {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth();
    const counts = new Map(activity.map((d) => [d.date, d.count]));
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const startWeekday = new Date(year, month, 1).getDay();

    const dayCells: DayCell[] = [];
    for (let i = 0; i < startWeekday; i++) {
      dayCells.push({ day: null, count: 0, isToday: false });
    }
    for (let day = 1; day <= daysInMonth; day++) {
      const key = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
      dayCells.push({ day, count: counts.get(key) ?? 0, isToday: day === now.getDate() });
    }
    while (dayCells.length % 7 !== 0) {
      dayCells.push({ day: null, count: 0, isToday: false });
    }

    return {
      cells: dayCells,
      monthLabel: now.toLocaleDateString(undefined, { month: "long", year: "numeric" }),
    };
  }, [activity]);

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-card">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-neutral-950">Note activity</p>
        <span className="text-xs font-medium text-neutral-400">{monthLabel}</span>
      </div>

      <div className={`mt-4 grid grid-cols-7 gap-1.5 ${loading ? "opacity-40" : ""}`}>
        {WEEKDAY_LABELS.map((label, index) => (
          <span key={`label-${index}`} className="text-center text-[10px] font-medium text-neutral-400">
            {label}
          </span>
        ))}
        {cells.map((cell, index) =>
          cell.day === null ? (
            <span key={`empty-${index}`} />
          ) : (
            <div
              key={cell.day}
              title={`${cell.count} note${cell.count === 1 ? "" : "s"} on ${monthLabel.split(" ")[0]} ${cell.day}`}
              className={`aspect-square rounded-md ${colorForCount(cell.count)} ${
                cell.isToday ? "ring-2 ring-neutral-950 ring-offset-1" : ""
              }`}
            />
          ),
        )}
      </div>

      <div className="mt-4 flex items-center justify-end gap-1.5 text-[11px] text-neutral-400">
        Less
        <span className="h-3 w-3 rounded-sm bg-neutral-100" />
        <span className="h-3 w-3 rounded-sm bg-accent-200" />
        <span className="h-3 w-3 rounded-sm bg-accent-400" />
        <span className="h-3 w-3 rounded-sm bg-accent-600" />
        <span className="h-3 w-3 rounded-sm bg-accent-700" />
        More
      </div>
    </div>
  );
}
