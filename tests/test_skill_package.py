from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from scripts.build_skill_package import NAME, build


def test_share_archive_is_allowlisted_and_runs_outside_repository(tmp_path):
    archive = tmp_path / "skill.zip"
    build(archive)
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        assert len(names) == 8
        assert all(name.startswith(NAME + "/") for name in names)
        assert not any(name.endswith((".db", ".pdf", ".env", "access.json")) for name in names)
        package.extractall(tmp_path / "unpacked")
    runner = tmp_path / "unpacked" / NAME / "scripts/package_data.py"
    result = subprocess.run([sys.executable, str(runner), "--help"], cwd=tmp_path,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "--extractions" in result.stdout
    assert "--import-staging" not in result.stdout
    submitter = runner.with_name("submit_extraction.py")
    submit_help = subprocess.run([sys.executable, str(submitter), "--help"], cwd=tmp_path,
                                 text=True, capture_output=True)
    assert submit_help.returncode == 0, submit_help.stderr
    assert "--server" in submit_help.stdout
    with pytest.raises(FileExistsError):
        build(archive)

