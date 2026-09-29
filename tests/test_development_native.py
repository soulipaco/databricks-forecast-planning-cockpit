"""Synthetic v2 development grid: retry policy, failure visibility and query bounds."""

from datetime import date, timedelta

from nyc311_forecast.development_native import TransientNativeError, run_native

ORIGINS = (date(2024, 10, 31), date(2024, 11, 30))


def _rows():
    first, last = date(2021, 10, 1), date(2024, 12, 28)
    return [{"ds": first + timedelta(days=i), "y": 10 + i % 7}
            for i in range((last - first).days + 1)]


def _output(origin, value=12.0):
    return [{"ds": (origin + timedelta(days=i)).isoformat(), "y_forecast": value,
             "y_lower": value - 2, "y_upper": value + 2} for i in range(1, 29)]


class Executor:
    """Replays a scripted outcome per (series, origin) call sequence."""

    def __init__(self, script=None):
        self.script = script or {}
        self.calls = []

    def __call__(self, sql):
        series = next(s for s in ("BRONX|A", "QUEENS|B") if s in sql)
        origin = next(o for o in ORIGINS if f"DATE '{o.isoformat()}'" in sql)
        n = sum(1 for s, o in self.calls if (s, o) == (series, origin))
        self.calls.append((series, origin))
        assert "version => '2'" in sql and "run-x" in sql
        assert f"horizon => '{(origin + timedelta(days=28)).isoformat()}'" in sql
        outcome = self.script.get((series, origin), ["ok"])[n]
        if outcome == "transient":
            raise TransientNativeError("TEMPORARILY_UNAVAILABLE")
        if outcome == "bad":
            return "q-bad", _output(origin)[:-1], 1.0
        return f"q-{series}-{origin}-{n}", _output(origin), 1.0


def _run(executor):
    return run_native(("BRONX|A", "QUEENS|B"), {"BRONX|A": _rows(), "QUEENS|B": _rows()},
                      executor, catalog="workspace", schema="nyc311_forecast",
                      snapshot_id="silver-x", run_tag="run-x", retry_wait_seconds=0)


def test_complete_grid_scores_every_cell_with_intervals():
    out = _run(Executor())
    assert (out["expected_cells"], out["complete_cells"], out["failed_cells"]) == (4, 4, 0)
    assert len(out["forecast_values"]) == 4 * 28
    cell = out["evaluation_cells"][0]
    assert cell["metrics"]["wape"] is not None and cell["metrics"]["interval_n"] == 28
    assert all(v["lower"] <= v["prediction"] <= v["upper"] for v in out["forecast_values"])


def test_transient_error_is_retried_and_every_attempt_kept():
    key = ("BRONX|A", ORIGINS[0])
    out = _run(Executor({key: ["transient", "ok"]}))
    tries = [a for a in out["attempts"]
             if (a["series_id"], a["origin"]) == (key[0], key[1].isoformat())]
    assert [a["status"] for a in tries] == ["failed", "success"]
    assert out["complete_cells"] == 4


def test_contract_error_is_not_retried_and_stays_in_denominator():
    key = ("QUEENS|B", ORIGINS[1])
    executor = Executor({key: ["bad", "ok"]})
    out = _run(executor)
    assert executor.calls.count(key) == 1
    assert (out["expected_cells"], out["complete_cells"], out["failed_cells"]) == (4, 3, 1)


def test_exhausted_transient_retries_fail_after_three_attempts():
    key = ("BRONX|A", ORIGINS[1])
    executor = Executor({key: ["transient"] * 3})
    out = _run(executor)
    assert executor.calls.count(key) == 3
    assert out["failed_cells"] == 1
