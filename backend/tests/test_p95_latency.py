import pytest

from backend.scripts import p95_latency as p95


def test_percentile_empty():
    assert p95.percentile([], 95) is None


def test_percentile_uses_nearest_rank():
    values = list(range(1, 101))

    assert p95.percentile(values, 50) == 50
    assert p95.percentile(values, 95) == 95
    assert p95.percentile(values, 99) == 99


def test_percentile_rejects_invalid_fraction():
    with pytest.raises(ValueError):
        p95.percentile([1.0], 0)


def test_collect_samples_filters_event_route_and_type():
    lines = [
        '{"event":"request_timing","route":"/a","duration_ms":10}',
        "not json",
        '{"event":"note_processing","route":"/a","duration_ms":99}',
        '{"event":"request_timing","route":"/b","duration_ms":20}',
        '{"event":"request_timing","route":"/a","duration_ms":30.5}',
        '{"event":"request_timing","route":"/a","duration_ms":null}',
        '{"event":"request_timing","route":"/a","duration_ms":true}',
        '{"event":"request_timing","route":"/a","duration_ms":"40"}',
    ]

    samples = p95.collect_samples(lines, event="request_timing", route="/a")

    assert samples == [10.0, 30.5]


def test_summarize_and_cli_file(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"event":"request_timing","duration_ms":10}',
                '{"event":"request_timing","duration_ms":20}',
                '{"event":"request_timing","duration_ms":30}',
            ]
        ),
        encoding="utf-8",
    )

    exit_code = p95.main(["--file", str(path), "--event", "request_timing"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "event=request_timing" in output
    assert "n=3" in output
    assert "p95=30.0ms" in output


def test_cli_reports_no_samples(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    path.write_text('{"event":"other","duration_ms":10}\n', encoding="utf-8")

    exit_code = p95.main(["--file", str(path), "--event", "request_timing"])

    assert exit_code == 1
    assert "No samples found" in capsys.readouterr().err
