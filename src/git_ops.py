from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from models import CommitComparison, CommitEvent, FileChange


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


def _repo_relative_path(repo: Path, path: Path) -> str:
    repo_root = repo.resolve()
    candidate = path if path.is_absolute() else repo_root / path
    candidate = candidate.resolve()
    try:
        return candidate.relative_to(repo_root).as_posix()
    except ValueError as error:
        raise RuntimeError(f"Path filter '{path}' must be inside repository '{repo_root}'.") from error


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


def _select_comparison_commits(repo: Path, commit_ids: list[str]) -> tuple[str | None, str]:
    if len(commit_ids) >= 2:
        return commit_ids[0], commit_ids[-1]
    target_commit = commit_ids[-1]
    return _commit_parent(repo, target_commit), target_commit


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


def _collect_file_changes(
    repo: Path,
    before_commit: str | None,
    after_commit: str,
    pathspecs: list[str] | None = None,
) -> list[FileChange]:
    if before_commit:
        args = ["diff", "--find-renames", "--name-status", before_commit, after_commit]
        if pathspecs:
            args.extend(["--", *pathspecs])
        raw_changes = _run_git(repo, args)
    else:
        args = ["diff-tree", "--root", "--no-commit-id", "--name-status", "-r", after_commit]
        if pathspecs:
            args.extend(["--", *pathspecs])
        raw_changes = _run_git(repo, args)

    changed_files: list[FileChange] = []
    for line in raw_changes.splitlines():
        if not line.strip():
            continue
        status, previous_path, file_path = _parse_name_status_line(line)
        source_path = file_path
        before_path = previous_path or source_path
        file_type = detect_file_type(source_path)
        before_ref = f"{before_commit}:{before_path}" if before_commit and not status.startswith("A") else None
        after_ref = f"{after_commit}:{source_path}" if not status.startswith("D") else None
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
    return changed_files


def collect_commit_comparison(
    repo: Path,
    *,
    since: str | None,
    until: str | None,
    base: str | None,
    head: str,
    target_path: Path | None = None,
) -> CommitComparison:
    refs = resolve_commit_ids(repo, since=since, until=until, base=base, head=head)
    before_commit, after_commit = _select_comparison_commits(repo, refs.commit_ids)
    assert after_commit is not None

    before_author = before_time = before_message = ""
    if before_commit:
        before_author, before_time, before_message = _commit_metadata(repo, before_commit)
    after_author, after_time, after_message = _commit_metadata(repo, after_commit)

    pathspecs = [_repo_relative_path(repo, target_path)] if target_path is not None else None
    changed_files = _collect_file_changes(repo, before_commit, after_commit, pathspecs)
    before_event = CommitEvent(
        commit_id=before_commit or "<empty>",
        author=before_author,
        time=before_time,
        message=before_message,
        changed_files=[],
    )
    after_event = CommitEvent(
        commit_id=after_commit,
        author=after_author,
        time=after_time,
        message=after_message,
        changed_files=changed_files,
    )
    return CommitComparison(
        before=before_event,
        after=after_event,
        changed_files=changed_files,
        description=f"{before_event.commit_id if before_commit else 'root'}..{after_event.commit_id}",
    )


def read_blob(repo: Path, ref: str | None) -> bytes | None:
    if ref is None:
        return None
    try:
        return _run_git(repo, ["show", ref], binary=True)  # type: ignore[return-value]
    except RuntimeError:
        return None
