import os


class UnsafeIndexPathError(RuntimeError):
    pass


def assert_safe_index_directory(
    *,
    index_path: str,
    data_root: str,
    notes_path: str,
) -> str:
    normalized_index_path = _normalize_path(index_path)
    normalized_data_root = _normalize_path(data_root)
    normalized_notes_path = _normalize_path(notes_path)

    if os.path.basename(normalized_index_path) != "index":
        raise UnsafeIndexPathError(
            f"Refusing to use unsafe index path '{index_path}'. "
            "Index directory must be named 'index'."
        )
    if os.path.basename(os.path.dirname(normalized_index_path)) != ".copycat":
        raise UnsafeIndexPathError(
            f"Refusing to use unsafe index path '{index_path}'. "
            "Index directory must be under a '.copycat' directory."
        )
    if not _is_relative_to(normalized_index_path, normalized_data_root):
        raise UnsafeIndexPathError(
            f"Refusing to use unsafe index path '{index_path}'. "
            "Index directory must be inside COPYCAT_PATH."
        )

    blocked_paths = {
        normalized_data_root,
        normalized_notes_path,
        os.path.join(normalized_data_root, "attachments"),
        os.path.dirname(normalized_notes_path),
    }
    if normalized_index_path in blocked_paths:
        raise UnsafeIndexPathError(
            f"Refusing to use unsafe index path '{index_path}'. "
            "Index directory cannot be a data, notes, attachments, "
            "or group root."
        )
    return normalized_index_path


def _normalize_path(path: str) -> str:
    return os.path.realpath(os.path.abspath(path))


def _is_relative_to(path: str, parent: str) -> bool:
    try:
        return os.path.commonpath([path, parent]) == parent
    except ValueError:
        return False
