#!/usr/bin/env python3
"""Calculate nearest-rank latency percentiles from JSON timing events.

Examples:
    sudo journalctl -u northstar-api -o cat --since "1 hour ago" \\
        | python3 backend/scripts/p95_latency.py --event request_timing

    sudo journalctl -u northstar-note-worker -o cat --since "24 hours ago" \\
        | python3 backend/scripts/p95_latency.py \\
        --event note_processing --field end_to_end_ms
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Iterable, Sequence


def percentile(values: Sequence[float], pct: float) -> float | None:
    """Return the nearest-rank percentile, or ``None`` for no samples."""
    if not values:
        return None
    if not 0 < pct <= 100:
        raise ValueError("pct must be between 0 and 100")
    ordered = sorted(values)
    rank = math.ceil((pct / 100) * len(ordered))
    return ordered[min(max(rank, 1), len(ordered)) - 1]


def collect_samples(
    lines: Iterable[str],
    *,
    event: str = "request_timing",
    field: str = "duration_ms",
    route: str | None = None,
) -> list[float]:
    """Extract numeric samples from JSON-lines events, skipping non-events."""
    samples: list[float] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or payload.get("event") != event:
            continue
        if route is not None and payload.get("route") != route:
            continue
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        samples.append(float(value))
    return samples


def summarize(values: Sequence[float]) -> dict[str, float | int | None]:
    return {
        "n": len(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "max": max(values) if values else None,
    }


def _format_ms(value: float | int | None) -> str:
    return "n/a" if value is None else f"{value:.1f}ms"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Calculate p50/p95/p99 latency from JSON timing events.",
    )
    parser.add_argument("--file", type=Path, help="JSON-lines file (default: stdin)")
    parser.add_argument("--event", default="request_timing", help="Event name to include")
    parser.add_argument("--field", default="duration_ms", help="Numeric field to measure")
    parser.add_argument("--route", help="Only include events with this route")
    args = parser.parse_args(argv)

    if args.file:
        with args.file.open(encoding="utf-8") as handle:
            samples = collect_samples(
                handle,
                event=args.event,
                field=args.field,
                route=args.route,
            )
    else:
        samples = collect_samples(
            sys.stdin,
            event=args.event,
            field=args.field,
            route=args.route,
        )

    if not samples:
        print(
            f"No samples found for event={args.event} field={args.field}",
            file=sys.stderr,
        )
        return 1

    stats = summarize(samples)
    print(
        f"event={args.event} field={args.field} route={args.route or 'all'} "
        f"n={stats['n']} p50={_format_ms(stats['p50'])} "
        f"p95={_format_ms(stats['p95'])} p99={_format_ms(stats['p99'])} "
        f"max={_format_ms(stats['max'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
