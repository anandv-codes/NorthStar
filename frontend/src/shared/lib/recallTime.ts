const STORAGE_KEY = "northstar_recall_time";

interface RecallTimeRecord {
  date: string;
  seconds: number;
}

function todayKey(): string {
  return new Date().toISOString().slice(0, 10);
}

function readRecord(): RecallTimeRecord {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { date: todayKey(), seconds: 0 };
    }
    const parsed = JSON.parse(raw) as RecallTimeRecord;
    if (parsed.date !== todayKey()) {
      return { date: todayKey(), seconds: 0 };
    }
    return parsed;
  } catch {
    return { date: todayKey(), seconds: 0 };
  }
}

export function getTodayRecallSeconds(): number {
  return readRecord().seconds;
}

export function addTodayRecallSeconds(deltaSeconds: number): number {
  const current = readRecord();
  const next: RecallTimeRecord = { date: todayKey(), seconds: current.seconds + deltaSeconds };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return next.seconds;
}
