"""Deployment-as-code guards: unscheduled, single-run jobs and no premature benchmark stage."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _jobs() -> dict:
    return yaml.safe_load((ROOT / "resources/jobs.yml").read_text(encoding="utf-8"))[
        "resources"
    ]["jobs"]


def test_jobs_are_unscheduled_single_run_and_bounded():
    for key, job in _jobs().items():
        assert not {"schedule", "trigger", "continuous"} & set(job), key
        assert job["max_concurrent_runs"] == 1, key
        assert 0 < job["timeout_seconds"] <= 7200, key


def test_benchmark_stages_are_absent_until_protocol_freeze():
    assert not {"benchmark", "publish_results"} & set(_jobs())


def test_job_entry_points_exist_and_use_a_python312_environment():
    for job in _jobs().values():
        for task in job["tasks"]:
            script = (ROOT / "resources" / task["spark_python_task"]["python_file"]).resolve()
            assert script.is_file()
        for env in job["environments"]:
            assert env["spec"]["client"] == "3"
