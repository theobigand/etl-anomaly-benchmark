# ruff: noqa: E501
"""Archive the verdict files that the consolidator reads, so that the record can be rebuilt.

    python docs/thesis-remediation/evidence/archive_verdicts.py

`mutants/` is not tracked. This writes `l4-campaign-2026-11-13/verdicts.tgz` with every `mutants/**/*.meta`
(and the `.meta.mac` files kept by `merge_case_sensitive.py`) and `verdicts.sha256`. Extract the archive into the
repository root and run `consolidate_l4_campaign.py` to rebuild `final-measurement.json`.
"""

import hashlib
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent / "l4-campaign-2026-11-13"


def main() -> None:
    files = sorted(
        path
        for pattern in ("*.meta", "*.meta.mac")
        for path in (ROOT / "mutants").rglob(pattern)
        if "tests" not in path.relative_to(ROOT / "mutants").parts[:2]
    )
    archive = OUT / "verdicts.tgz"
    with tarfile.open(archive, "w:gz", format=tarfile.GNU_FORMAT) as tar:
        for path in files:
            info = tar.gettarinfo(path, arcname=path.relative_to(ROOT).as_posix())
            info.mtime, info.uid, info.gid, info.uname, info.gname = 0, 0, 0, "", ""
            with path.open("rb") as handle:
                tar.addfile(info, handle)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (OUT / "verdicts.sha256").write_text(f"{digest}  verdicts.tgz\n")
    print(len(files), "files", archive.stat().st_size, "bytes", digest[:12])


if __name__ == "__main__":
    main()
