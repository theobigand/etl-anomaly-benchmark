"""The campaign context names what can change a verdict, not the runner that happened to host it.

Hosted runners differ in kernel build and cloud provider (`Linux-...-azure-...` against
`Linux-...-aws-...`) while running the same operating system family, architecture and C library.
A context that embedded the full platform string made one shard on another provider fail the
whole aggregation.
"""

from __future__ import annotations

import platform

import pytest

from tests.test_mutation_shards import _git_repository
from verification import mutation_cache, mutation_run
from verification import mutation_shards as shards

AZURE = "Linux-7.0.0-1019-azure-x86_64-with-glibc2.43"
AWS = "Linux-7.0.0-1016-aws-x86_64-with-glibc2.43"


def _host(monkeypatch, system, machine, libc, full):
    monkeypatch.setattr(platform, "system", lambda: system)
    monkeypatch.setattr(platform, "machine", lambda: machine)
    monkeypatch.setattr(platform, "libc_ver", lambda *args, **kwargs: libc)
    monkeypatch.setattr(platform, "platform", lambda *args, **kwargs: full)


def test_the_platform_names_the_system_architecture_and_c_library(monkeypatch):
    _host(monkeypatch, "Linux", "x86_64", ("glibc", "2.43"), AZURE)
    assert mutation_cache.stable_platform() == "Linux-x86_64-glibc-2.43"


def test_runners_that_differ_only_in_kernel_build_and_provider_agree(monkeypatch):
    _host(monkeypatch, "Linux", "x86_64", ("glibc", "2.43"), AZURE)
    azure = mutation_cache.stable_platform()
    _host(monkeypatch, "Linux", "x86_64", ("glibc", "2.43"), AWS)
    assert mutation_cache.stable_platform() == azure


@pytest.mark.parametrize(
    ("system", "machine", "libc"),
    [
        ("Darwin", "x86_64", ("glibc", "2.43")),
        ("Linux", "aarch64", ("glibc", "2.43")),
        ("Linux", "x86_64", ("glibc", "2.44")),
        ("Linux", "x86_64", ("musl", "2.43")),
    ],
)
def test_a_different_system_architecture_or_c_library_is_a_different_platform(
    monkeypatch, system, machine, libc
):
    _host(monkeypatch, "Linux", "x86_64", ("glibc", "2.43"), AZURE)
    reference = mutation_cache.stable_platform()
    _host(monkeypatch, system, machine, libc, AZURE)
    assert mutation_cache.stable_platform() != reference


def test_empty_parts_are_left_out(monkeypatch):
    _host(monkeypatch, "Darwin", "arm64", ("", ""), "macOS-27.2-arm64-arm-64bit-Mach-O")
    assert mutation_cache.stable_platform() == "Darwin-arm64"
    _host(monkeypatch, "Linux", "x86_64", ("glibc", ""), AZURE)
    assert mutation_cache.stable_platform() == "Linux-x86_64-glibc"


def test_the_shard_context_and_the_execution_runtime_use_it(tmp_path, monkeypatch):
    _git_repository(tmp_path)
    monkeypatch.setattr(mutation_run, "distributions", lambda: [])
    _host(monkeypatch, "Linux", "x86_64", ("glibc", "2.43"), AZURE)
    first = shards.current_context(tmp_path)
    runtime = mutation_run.collect_runtime({})
    _host(monkeypatch, "Linux", "x86_64", ("glibc", "2.43"), AWS)
    second = shards.current_context(tmp_path)
    assert first["runtime"]["platform"] == "Linux-x86_64-glibc-2.43"
    assert runtime["platform"] == "Linux-x86_64-glibc-2.43"
    assert second == first
