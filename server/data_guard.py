import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass

from logger import logger

APP_DIR = ".copycat"
INSTALL_MARKER = "install.json"
VALID_MODES = {"fail_existing", "warn", "off"}


class DataGuardError(RuntimeError):
    pass


@dataclass(frozen=True)
class DataRootSummary:
    data_root: str
    root_note_count: int
    group_note_count: int
    metadata_file_count: int
    auth_file_count: int
    attachment_file_count: int
    group_dir_count: int
    index_file_count: int
    log_file_count: int
    install_marker_exists: bool
    previous_durable_count: int

    @property
    def note_count(self) -> int:
        return self.root_note_count + self.group_note_count

    @property
    def durable_count(self) -> int:
        return (
            self.note_count
            + self.metadata_file_count
            + self.auth_file_count
            + self.attachment_file_count
            + self.group_dir_count
        )

    @property
    def has_cache_only_shape(self) -> bool:
        return self.durable_count == 0 and self.index_file_count > 0

    @property
    def lost_known_data(self) -> bool:
        return self.previous_durable_count > 0 and self.durable_count == 0


def guard_data_root(data_root: str | None = None) -> DataRootSummary:
    mode = _data_guard_mode()
    data_root = data_root or os.environ.get("COPYCAT_PATH", "/data")
    data_root = _validate_data_root(data_root)
    summary = summarize_data_root(data_root)

    logger.info(
        "Data root summary: root='%s', notes=%d, metadata_files=%d, "
        "auth_files=%d, attachments=%d, groups=%d, index_files=%d, "
        "log_files=%d, install_marker=%s, previous_durable_count=%d, "
        "durable_count=%d, guard_mode='%s'.",
        summary.data_root,
        summary.note_count,
        summary.metadata_file_count,
        summary.auth_file_count,
        summary.attachment_file_count,
        summary.group_dir_count,
        summary.index_file_count,
        summary.log_file_count,
        summary.install_marker_exists,
        summary.previous_durable_count,
        summary.durable_count,
        mode,
    )

    if mode == "off":
        _write_install_marker(summary)
        return summary

    problem = None
    if summary.lost_known_data:
        problem = (
            "The data root previously contained durable CopyCat data, but no "
            "durable notes, metadata, auth registry, groups, or attachments "
            "are visible now."
        )
    elif not summary.install_marker_exists and summary.has_cache_only_shape:
        problem = (
            "The data root contains only CopyCat cache/index files and no "
            "durable application data. This usually indicates a wrong, stale, "
            "or empty restored volume."
        )

    if problem is not None:
        if mode == "warn":
            message = (
                "COPYCAT_DATA_GUARD_MODE=warn allowed startup despite a "
                f"suspicious data root: {problem} COPYCAT_PATH='{summary.data_root}'."
            )
            logger.critical(message)
        else:
            message = (
                f"{problem} Refusing to start with COPYCAT_PATH='{summary.data_root}'. "
                "Inspect the PVC/PV before writing new data, or set "
                "COPYCAT_DATA_GUARD_MODE=warn for an emergency read-through start."
            )
            logger.critical(message)
            raise DataGuardError(message)

    _write_install_marker(summary)
    return summary


def summarize_data_root(data_root: str) -> DataRootSummary:
    marker_path = _install_marker_path(data_root)
    previous_durable_count = _read_previous_durable_count(marker_path)
    return DataRootSummary(
        data_root=data_root,
        root_note_count=_count_files(data_root, "*.md"),
        group_note_count=_count_files(
            os.path.join(data_root, "groups"), "*", "notes", "*.md"
        ),
        metadata_file_count=_count_existing_files(
            [
                os.path.join(data_root, APP_DIR, "metadata.json"),
                *[
                    os.path.join(group_root, APP_DIR, "metadata.json")
                    for group_root in _group_roots(data_root)
                ],
            ]
        ),
        auth_file_count=_count_existing_files(
            [
                os.path.join(data_root, APP_DIR, "auth", "users.json"),
                os.path.join(data_root, APP_DIR, "auth", "groups.json"),
            ]
        ),
        attachment_file_count=(
            _count_files(os.path.join(data_root, "attachments"), "**", "*")
            + sum(
                _count_files(os.path.join(group_root, "attachments"), "**", "*")
                for group_root in _group_roots(data_root)
            )
        ),
        group_dir_count=len(_group_roots(data_root)),
        index_file_count=(
            _count_files(os.path.join(data_root, APP_DIR, "index"), "**", "*")
            + sum(
                _count_files(os.path.join(group_root, APP_DIR, "index"), "**", "*")
                for group_root in _group_roots(data_root)
            )
        ),
        log_file_count=_count_files(os.path.join(data_root, APP_DIR, "logs"), "**", "*"),
        install_marker_exists=os.path.isfile(marker_path),
        previous_durable_count=previous_durable_count,
    )


def _data_guard_mode() -> str:
    mode = os.environ.get("COPYCAT_DATA_GUARD_MODE", "fail_existing").strip().lower()
    if mode not in VALID_MODES:
        raise DataGuardError(
            "Invalid COPYCAT_DATA_GUARD_MODE value "
            f"'{mode}'. Must be one of: {', '.join(sorted(VALID_MODES))}."
        )
    return mode


def _validate_data_root(data_root: str) -> str:
    if not data_root or not os.path.isabs(data_root):
        raise DataGuardError("COPYCAT_PATH must be an absolute path.")
    normalized = os.path.realpath(os.path.abspath(data_root))
    blocked_paths = {
        "/",
        "/app",
        "/usr",
        "/etc",
        "/var",
        "/bin",
        "/sbin",
        "/root",
        "/home",
    }
    if normalized in blocked_paths:
        raise DataGuardError(
            f"Refusing to use unsafe COPYCAT_PATH '{data_root}'."
        )
    if not os.path.isdir(normalized):
        raise DataGuardError(f"COPYCAT_PATH '{data_root}' is not a directory.")
    return normalized


def _install_marker_path(data_root: str) -> str:
    return os.path.join(data_root, APP_DIR, INSTALL_MARKER)


def _read_previous_durable_count(marker_path: str) -> int:
    if not os.path.isfile(marker_path):
        return 0
    try:
        with open(marker_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return int(data.get("lastDurableCount") or 0)
    except Exception:
        logger.exception("Failed to read CopyCat install marker '%s'.", marker_path)
        return 0


def _write_install_marker(summary: DataRootSummary) -> None:
    marker_path = _install_marker_path(summary.data_root)
    os.makedirs(os.path.dirname(marker_path), exist_ok=True)
    current_last_durable_count = max(
        summary.previous_durable_count,
        summary.durable_count,
    )
    data = {
        "version": 1,
        "updatedAt": int(time.time()),
        "dataRoot": summary.data_root,
        "lastDurableCount": current_last_durable_count,
        "lastSummary": asdict(summary),
    }
    fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(marker_path),
        prefix="install-",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, marker_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _group_roots(data_root: str) -> list[str]:
    groups_path = os.path.join(data_root, "groups")
    if not os.path.isdir(groups_path):
        return []
    return [
        entry.path
        for entry in os.scandir(groups_path)
        if entry.is_dir() and not entry.name.startswith(".")
    ]


def _count_files(*parts: str) -> int:
    import glob

    pattern = os.path.join(*parts)
    return sum(1 for path in glob.glob(pattern, recursive=True) if os.path.isfile(path))


def _count_existing_files(paths: list[str]) -> int:
    return sum(1 for path in paths if os.path.isfile(path))
