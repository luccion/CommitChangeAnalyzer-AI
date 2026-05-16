from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from commit_change_analyzer.models import CommitEvent, FileChange


TEXT_EXTENSIONS = {
    ".csv": "csv",
    ".json": "json",
    ".txt": "text",
    ".md": "text",
    ".yaml": "text",
    ".yml": "text",
}
EXCEL_EXTENSIONS = {
    ".xlsx": "excel",
    ".xlsm": "excel",
    ".xltx": "excel",
    ".xltm": "excel",
    ".xls": "excel-legacy",
    ".xlsb": "excel-binary",
}


@dataclass(slots=True)
class GitRefs:
    commit_ids: list[str]
    description: str


def _run_git(repo: Path, args: list[str], *, check: bool = True, binary: bool = False) -> str | bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr}")
    return completed.stdout if binary else completed.stdout.decode("utf-8", errors="replace")


def detect_file_type(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    if suffix in EXCEL_EXTENSIONS:
        return EXCEL_EXTENSIONS[suffix]
    if suffix in TEXT_EXTENSIONS:
        return TEXT_EXTENSIONS[suffix]
    return "other"


def resolve_commit_ids(
    repo: Path,
    *,
    since: str | None,
    until: str | None,
    base: str | None,
    head: str,
) -> GitRefs:
    if base:
        commit_text = _run_git(repo, ["rev-list", "--reverse", f"{base}..{head}"])
        description = f"{base}..{head}"
    elif since or until:
        args = ["rev-list", "--reverse"]
        if since:
            args.append(f"--since={since}")
        if until:
            args.append(f"--until={until}")
        args.append(head)
        commit_text = _run_git(repo, args)
        description = f"time range since={since or '-'} until={until or '-'} head={head}"
    else:
        commit_text = _run_git(repo, ["rev-list", "--max-count=1", head])
        description = f"latest commit at {head}"
    commit_ids = [line.strip() for line in commit_text.splitlines() if line.strip()]
    if not commit_ids:
        raise RuntimeError("No commits found for the requested range.")
    return GitRefs(commit_ids=commit_ids, description=description)


def _commit_parent(repo: Path, commit_id: str) -> str | None:
    line = _run_git(repo, ["rev-list", "--parents", "-n", "1", commit_id]).strip()
    parts = line.split()
    if len(parts) > 1:
        return parts[1]
    return None


def _commit_metadata(repo: Path, commit_id: str) -> tuple[str, str, str]:
    raw = _run_git(repo, ["show", "-s", "--format=%an%n%aI%n%s", commit_id])
    author, time, message = raw.splitlines()[:3]
    return author, time, message


def _parse_name_status_line(line: str) -> tuple[str, str | None, str]:
    parts = line.split("\t")
    status = parts[0]
    if status.startswith("R") or status.startswith("C"):
        return status, parts[1], parts[2]
    return status, None, parts[1]


def collect_commit_events(
    repo: Path,
    *,
    since: str | None,
    until: str | None,
    base: str | None,
    head: str,
) -> tuple[list[CommitEvent], str]:
    refs = resolve_commit_ids(repo, since=since, until=until, base=base, head=head)
    commits: list[CommitEvent] = []
    for commit_id in refs.commit_ids:
        parent = _commit_parent(repo, commit_id)
        author, time, message = _commit_metadata(repo, commit_id)
        raw_changes = _run_git(repo, ["diff-tree", "--root", "--no-commit-id", "--name-status", "-r", commit_id])
        changed_files: list[FileChange] = []
        for line in raw_changes.splitlines():
            status, previous_path, file_path = _parse_name_status_line(line)
            source_path = file_path
            before_path = previous_path or source_path
            file_type = detect_file_type(source_path)
            before_ref = f"{parent}:{before_path}" if parent and not status.startswith("A") else None
            after_ref = f"{commit_id}:{source_path}" if not status.startswith("D") else None
            changed_files.append(
                FileChange(
                    file_path=source_path,
                    file_type=file_type,
                    before_ref=before_ref,
                    after_ref=after_ref,
                    status=status,
                    previous_path=previous_path,
                )
            )
        commits.append(
            CommitEvent(
                commit_id=commit_id,
                author=author,
                time=time,
                message=message,
                changed_files=changed_files,
            )
        )
    return commits, refs.description


def read_blob(repo: Path, ref: str | None) -> bytes | None:
    if ref is None:
        return None
    try:
        return _run_git(repo, ["show", ref], binary=True)  # type: ignore[return-value]
    except RuntimeError:
        return None
