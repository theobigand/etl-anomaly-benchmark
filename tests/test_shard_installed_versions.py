"""The installed version a shard records is the real one, and an absent package is unknown."""

from importlib.metadata import version as installed

from verification import mutation_shards as shards


def test_an_installed_package_reports_its_exact_version():
    assert shards.version("pytest") == installed("pytest")
    assert isinstance(shards.version("pytest"), str)


def test_a_package_that_is_not_installed_is_unknown_not_an_error():
    assert shards.version("no-such-package-for-the-shard-context") is None
