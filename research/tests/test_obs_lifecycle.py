"""Log rotation, retention, storage budget and shutdown flush (#160)."""

import io
import json
import logging
import os
import signal
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import obs_lifecycle as lc  # noqa: E402
import obs_logging as ol  # noqa: E402

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
DAY = 86400


@pytest.fixture(autouse=True)
def clean_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    for handler in [h for h in root.handlers if h not in handlers]:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(level)


def _age(path, days, seconds=0):
    stamp = NOW.timestamp() - days * DAY - seconds
    os.utime(path, (stamp, stamp))


def _logs(tmp_path, ages):
    """An active log and rotated backups ``app.log.1``... of the given ages in days."""
    active = tmp_path / "logs" / "app.log"
    active.parent.mkdir()
    active.write_text("a" * 100)
    _age(active, 0)
    for number, days in enumerate(ages, start=1):
        backup = active.with_name(f"app.log.{number}")
        backup.write_text("b" * 100)
        _age(backup, days)
    return active


def test_the_rotation_settings_have_defaults_and_validate_by_name():
    chosen = ol.settings({})
    assert (chosen["max_bytes"], chosen["backups"]) == (10 * 1024 * 1024, 5)
    chosen = ol.settings({"ETL_LOG_MAX_BYTES": "2048", "ETL_LOG_BACKUPS": "0"})
    assert (chosen["max_bytes"], chosen["backups"]) == (2048, 0)
    for env, message in (
        ({"ETL_LOG_MAX_BYTES": "0"}, "ETL_LOG_MAX_BYTES must be an integer of at least 1"),
        ({"ETL_LOG_MAX_BYTES": "big"}, "ETL_LOG_MAX_BYTES must be an integer of at least 1"),
        ({"ETL_LOG_BACKUPS": "-1"}, "ETL_LOG_BACKUPS must be an integer of at least 0"),
    ):
        with pytest.raises(ValueError, match=message):
            ol.settings(env)


def test_a_file_log_rotates_at_the_size_limit_and_keeps_the_configured_backups(tmp_path):
    path = tmp_path / "app.log"
    env = {"ETL_LOG_DEST": "file", "ETL_LOG_FILE": str(path), "ETL_LOG_MAX_BYTES": "400"}
    ol.configure({**env, "ETL_LOG_BACKUPS": "2"})
    log = logging.getLogger("etl.rotate")
    for number in range(60):
        log.info("record %03d %s", number, "x" * 30)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["app.log", "app.log.1", "app.log.2"]
    assert all(p.stat().st_size <= 500 for p in tmp_path.iterdir())
    assert "record 059" in path.read_text()


def test_a_stream_destination_has_no_rotation_files(tmp_path):
    ol.configure({"ETL_LOG_MAX_BYTES": "400"}, stream=io.StringIO())
    logging.getLogger("etl.x").info("x")
    assert list(tmp_path.iterdir()) == []


def test_the_lifecycle_settings_have_defaults_and_validate_by_name():
    assert lc.settings({}) == {
        "retention_days": 14,
        "budget_bytes": 100 * 1024 * 1024,
        "protected": (),
    }
    chosen = lc.settings(
        {
            "ETL_LOG_RETENTION_DAYS": "3",
            "ETL_LOG_BUDGET_BYTES": "5000",
            "ETL_LOG_PROTECTED": f"a{os.pathsep}b",
        }
    )
    assert chosen == {"retention_days": 3, "budget_bytes": 5000, "protected": ("a", "b")}
    with pytest.raises(
        ValueError, match="^ETL_LOG_RETENTION_DAYS must be an integer of at least 1; got '0'$"
    ):
        lc.settings({"ETL_LOG_RETENTION_DAYS": "0"})
    with pytest.raises(
        ValueError, match="^ETL_LOG_BUDGET_BYTES must be an integer of at least 1; got 'x'$"
    ):
        lc.settings({"ETL_LOG_BUDGET_BYTES": "x"})
    minimum = lc.settings({"ETL_LOG_RETENTION_DAYS": "1", "ETL_LOG_BUDGET_BYTES": "1"})
    assert (minimum["retention_days"], minimum["budget_bytes"]) == (1, 1)


def test_prune_removes_only_rotated_backups_older_than_the_retention(tmp_path):
    active = _logs(tmp_path, [1, 10, 20])
    other = active.parent / "keep.txt"
    other.write_text("keep")
    _age(other, 99)
    removed = lc.prune(active, now=NOW, retention_days=14, budget_bytes=10_000, root=tmp_path)
    assert sorted(p.name for p in removed) == ["app.log.3"]
    assert sorted(p.name for p in active.parent.iterdir()) == [
        "app.log",
        "app.log.1",
        "app.log.2",
        "keep.txt",
    ]


def test_the_retention_boundary_keeps_a_backup_exactly_at_the_period(tmp_path):
    active = _logs(tmp_path, [14, 14.001])
    removed = lc.prune(active, now=NOW, retention_days=14, budget_bytes=10_000, root=tmp_path)
    assert [p.name for p in removed] == ["app.log.2"]


def test_the_budget_removes_the_oldest_backups_first_and_never_the_active_file(tmp_path):
    active = _logs(tmp_path, [1, 3, 2])  # sizes 100 each, active 100: total 400
    removed = lc.prune(active, now=NOW, retention_days=14, budget_bytes=250, root=tmp_path)
    assert [p.name for p in removed] == ["app.log.2", "app.log.3"]
    assert active.exists() and (active.parent / "app.log.1").exists()
    removed = lc.prune(active, now=NOW, retention_days=14, budget_bytes=10, root=tmp_path)
    assert [p.name for p in removed] == ["app.log.1"] and active.exists()


def test_a_budget_that_is_met_removes_nothing(tmp_path):
    active = _logs(tmp_path, [1, 2])
    assert lc.prune(active, now=NOW, retention_days=14, budget_bytes=300, root=tmp_path) == []


def test_rotated_backups_are_numbered_siblings_only(tmp_path):
    active = _logs(tmp_path, [1])
    (active.parent / "app.log.bak").write_text("x")
    (active.parent / "app.log.1.gz").write_text("x")
    (active.parent / "other.log.1").write_text("x")
    assert [p.name for p in lc.rotated(active)] == ["app.log.1"]


@pytest.mark.parametrize(
    "relative",
    [
        "docs/thesis-remediation/evidence",
        "docs/thesis-remediation/evidence/run1",
        "verification/evidence",
        "experiments/results",
        "experiments/results/deep/sub",
    ],
)
def test_a_log_inside_a_protected_evidence_path_is_never_cleaned(tmp_path, relative):
    folder = tmp_path / relative
    folder.mkdir(parents=True)
    active = folder / "app.log"
    active.write_text("x")
    (folder / "app.log.1").write_text("old")
    _age(folder / "app.log.1", 99)
    with pytest.raises(ValueError, match="protected evidence path"):
        lc.prune(active, now=NOW, retention_days=1, budget_bytes=1, root=tmp_path)
    assert (folder / "app.log.1").exists()


def test_a_log_folder_that_contains_an_evidence_path_is_refused_too(tmp_path):
    (tmp_path / "verification" / "evidence").mkdir(parents=True)
    active = tmp_path / "verification" / "app.log"
    active.write_text("x")
    with pytest.raises(ValueError, match="protected evidence path"):
        lc.prune(active, now=NOW, retention_days=1, budget_bytes=1, root=tmp_path)


def test_extra_protected_paths_come_from_the_settings(tmp_path):
    active = _logs(tmp_path, [99])
    with pytest.raises(ValueError, match="protected evidence path"):
        lc.prune(
            active,
            now=NOW,
            retention_days=1,
            budget_bytes=1,
            root=tmp_path,
            protected=("logs",),
        )
    assert (active.parent / "app.log.1").exists()


def test_a_symlink_into_evidence_is_resolved_before_the_check(tmp_path):
    evidence = tmp_path / "verification" / "evidence"
    evidence.mkdir(parents=True)
    link = tmp_path / "linked"
    link.symlink_to(evidence, target_is_directory=True)
    (evidence / "app.log").write_text("x")
    with pytest.raises(ValueError, match="protected evidence path"):
        lc.prune(link / "app.log", now=NOW, retention_days=1, budget_bytes=1, root=tmp_path)


def test_a_sanitized_export_keeps_clean_lines_and_skips_the_rest(tmp_path):
    active = tmp_path / "logs" / "app.log"
    active.parent.mkdir()
    good = json.dumps({"event": "stage.completed", "stage": "load", "rows": 3})
    secret = json.dumps({"message": "token=abc123"})
    truth = json.dumps({"message": "ground_truth loaded"})
    active.write_text("\n".join(["not json", good, secret, truth, "[1, 2]", "also bad"]) + "\n")
    result = lc.export_sanitized(active, tmp_path / "exports", now=NOW, root=tmp_path)
    exported = tmp_path / "exports" / "app-20261126.jsonl"
    assert exported.read_text() == good + "\n"
    assert (result["lines"], result["skipped"]) == (1, 5)
    assert result["file"] == str(exported)
    digest = (tmp_path / "exports" / "app-20261126.jsonl.sha256").read_text().split()[0]
    assert digest == result["sha256"] and len(digest) == 64


def test_an_export_includes_the_rotated_backups_oldest_first(tmp_path):
    active = _logs(tmp_path, [5, 2])
    active.write_text(json.dumps({"event": "run.started"}) + "\n")
    (active.parent / "app.log.1").write_text(json.dumps({"event": "run.failed"}) + "\n")
    (active.parent / "app.log.2").write_text(json.dumps({"event": "run.completed"}) + "\n")
    _age(active.parent / "app.log.1", 2)
    _age(active.parent / "app.log.2", 5)
    lc.export_sanitized(active, tmp_path / "exports", now=NOW, root=tmp_path)
    events = [
        json.loads(line)["event"]
        for line in (tmp_path / "exports" / "app-20261126.jsonl").read_text().splitlines()
    ]
    assert events == ["run.completed", "run.failed", "run.started"]


def test_an_export_is_never_overwritten_and_never_pruned(tmp_path):
    active = _logs(tmp_path, [])
    active.write_text(json.dumps({"event": "run.started"}) + "\n")
    folder = tmp_path / "exports"
    lc.export_sanitized(active, folder, now=NOW, root=tmp_path)
    with pytest.raises(ValueError, match="already exists"):
        lc.export_sanitized(active, folder, now=NOW, root=tmp_path)
    exported = folder / "app-20261126.jsonl"
    _age(exported, 400)
    lc.prune(active, now=NOW, retention_days=1, budget_bytes=1, root=tmp_path)
    assert exported.exists()


def test_an_export_folder_inside_the_log_folder_is_refused(tmp_path):
    active = _logs(tmp_path, [])
    with pytest.raises(ValueError, match="log folder"):
        lc.export_sanitized(active, active.parent, now=NOW, root=tmp_path)


def test_shutdown_flushes_and_closes_only_our_handler(tmp_path):
    path = tmp_path / "app.log"
    ol.configure({"ETL_LOG_DEST": "file", "ETL_LOG_FILE": str(path)})
    foreign = logging.StreamHandler(io.StringIO())
    logging.getLogger().addHandler(foreign)
    logging.getLogger("etl.x").info("last words")
    lc.shutdown()
    (ours,) = [h for h in logging.getLogger().handlers if getattr(h, ol.MARK, False)] or [None]
    assert ours is None and foreign in logging.getLogger().handlers
    assert "last words" in path.read_text()


def test_a_terminated_process_flushes_its_log_and_exits_with_the_signal_code(tmp_path):
    path = tmp_path / "app.log"
    root = Path(__file__).resolve().parents[1]
    code = (
        "import logging, os, signal, sys\n"
        f"sys.path.insert(0, {str(root)!r})\n"
        "import obs_lifecycle as lc, obs_logging as ol\n"
        f"ol.configure({{'ETL_LOG_DEST': 'file', 'ETL_LOG_FILE': {str(path)!r}}})\n"
        "lc.install_shutdown()\n"
        "logging.getLogger('etl.child').info('before the signal')\n"
        "os.kill(os.getpid(), signal.SIGTERM)\n"
        "logging.getLogger('etl.child').info('never written')\n"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert done.returncode == 128 + signal.SIGTERM
    text = path.read_text()
    assert "before the signal" in text and "never written" not in text


def test_the_handler_restores_the_default_signal_behaviour_after_the_first_signal():
    previous = signal.getsignal(signal.SIGTERM)
    try:
        lc.install_shutdown()
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler) and handler is not previous
        with pytest.raises(SystemExit) as exit_info:
            handler(signal.SIGTERM, None)
        assert exit_info.value.code == 128 + signal.SIGTERM
        assert signal.getsignal(signal.SIGTERM) == signal.SIG_DFL
    finally:
        signal.signal(signal.SIGTERM, previous)


def test_the_retention_boundary_is_exact_to_the_second(tmp_path):
    active = _logs(tmp_path, [14])
    backup = active.parent / "app.log.1"
    _age(backup, 14, seconds=-1)
    assert lc.prune(active, now=NOW, retention_days=14, budget_bytes=10_000, root=tmp_path) == []
    _age(backup, 14, seconds=1)
    assert lc.prune(active, now=NOW, retention_days=14, budget_bytes=10_000, root=tmp_path) == [
        backup
    ]


def test_exports_create_nested_folders_and_share_an_existing_one(tmp_path):
    active = _logs(tmp_path, [])
    active.write_text(json.dumps({"event": "run.started"}) + "\n")
    folder = tmp_path / "out" / "deep"
    lc.export_sanitized(active, folder, now=NOW, root=tmp_path)
    second = active.with_name("other.log")
    second.write_text(json.dumps({"event": "run.started", "note": "é"}, ensure_ascii=False) + "\n")
    lc.export_sanitized(second, folder, now=NOW, root=tmp_path)
    assert (folder / "other-20261126.jsonl").read_bytes().decode() == second.read_text()
    assert (folder / "app-20261126.jsonl.sha256").exists()


def test_the_export_folder_error_names_the_rule(tmp_path):
    active = _logs(tmp_path, [])
    with pytest.raises(ValueError, match="^the export folder must not be the log folder$"):
        lc.export_sanitized(active, active.parent, now=NOW, root=tmp_path)
