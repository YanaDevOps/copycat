import json
import os
import tempfile
import threading
import time

from file_lock import FileLock
from helpers import get_env, resolve_root_app_dir
from logger import logger

from ..base import BaseMetadata
from ..models import (
    MAX_NOTE_TAGS,
    MetadataState,
    MetadataTag,
    NoteMetadata,
    Tag,
    TagCreate,
    TagRef,
    TagUpdate,
    slugify_tag_id,
)


class FileSystemMetadata(BaseMetadata):
    STATE_VERSION = 1

    def __init__(self, storage_path: str | None = None) -> None:
        if storage_path is None:
            self.base_path = get_env("COPYCAT_PATH", mandatory=True)
            if not os.path.exists(self.base_path):
                raise NotADirectoryError(
                    f"'{self.base_path}' is not a valid directory."
                )
            self.storage_path = resolve_root_app_dir(self.base_path)
        else:
            self.base_path = os.path.dirname(storage_path)
            self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)
        self.file_path = os.path.join(self.storage_path, "metadata.json")
        self.lock_path = os.path.join(self.storage_path, "metadata.lock")
        self._lock = threading.Lock()

    def get_note_metadata(
        self, title: str, fallback_created_at: float | None = None
    ) -> NoteMetadata:
        state = self._load_state()
        note_metadata = state.notes.get(title, NoteMetadata())
        created_at = note_metadata.created_at or fallback_created_at
        return NoteMetadata(
            created_at=created_at,
            favorite=note_metadata.favorite,
            tag_ids=self._filter_existing_tag_ids(state, note_metadata.tag_ids),
        )

    def update_note_metadata(
        self,
        title: str,
        *,
        created_at: float | None = None,
        favorite: bool | None = None,
        tag_ids: list[str] | None = None,
        fallback_created_at: float | None = None,
    ) -> NoteMetadata:
        with self._lock, FileLock(self.lock_path):
            state = self._load_state()
            existing = state.notes.get(title, NoteMetadata())
            resolved_tag_ids = (
                self._validate_tag_ids(state, tag_ids)
                if tag_ids is not None
                else self._filter_existing_tag_ids(state, existing.tag_ids)
            )
            next_metadata = NoteMetadata(
                created_at=created_at
                or existing.created_at
                or fallback_created_at
                or time.time(),
                favorite=existing.favorite if favorite is None else favorite,
                tag_ids=resolved_tag_ids,
            )
            state.notes[title] = next_metadata
            self._write_state(state)
            return next_metadata

    def rename_note(self, old_title: str, new_title: str) -> None:
        if old_title == new_title:
            return
        with self._lock, FileLock(self.lock_path):
            state = self._load_state()
            if old_title in state.notes:
                state.notes[new_title] = state.notes.pop(old_title)
                self._write_state(state)

    def delete_note(self, title: str) -> None:
        with self._lock, FileLock(self.lock_path):
            state = self._load_state()
            if state.notes.pop(title, None) is not None:
                self._write_state(state)

    def note_count(self) -> int:
        return len(self._load_state().notes)

    def get_note_tags(self, title: str) -> list[TagRef]:
        state = self._load_state()
        note_metadata = state.notes.get(title, NoteMetadata())
        tag_ids = self._filter_existing_tag_ids(state, note_metadata.tag_ids)
        return [self._tag_ref_from_metadata(state.tags[tag_id]) for tag_id in tag_ids]

    def list_tags(self) -> list[Tag]:
        state = self._load_state()
        usage_counts = self._usage_counts(state)
        tags = [
            Tag(
                id=tag.id,
                label=tag.label,
                color=tag.color,
                created_at=tag.created_at,
                usage_count=usage_counts.get(tag.id, 0),
            )
            for tag in state.tags.values()
        ]
        return sorted(tags, key=lambda tag: tag.label.lower())

    def create_tag(self, data: TagCreate) -> Tag:
        with self._lock, FileLock(self.lock_path):
            state = self._load_state()
            self._ensure_unique_label(state, data.label)
            tag_id = self._generate_unique_tag_id(state, data.label)
            tag = MetadataTag(
                id=tag_id,
                label=data.label,
                color=data.color,
                created_at=time.time(),
            )
            state.tags[tag_id] = tag
            self._write_state(state)
            return Tag(
                id=tag.id,
                label=tag.label,
                color=tag.color,
                created_at=tag.created_at,
                usage_count=0,
            )

    def update_tag(self, tag_id: str, data: TagUpdate) -> Tag:
        with self._lock, FileLock(self.lock_path):
            state = self._load_state()
            tag = state.tags.get(tag_id)
            if tag is None:
                raise FileNotFoundError(f"Tag '{tag_id}' not found.")
            label = data.label if data.label is not None else tag.label
            color = data.color if data.color is not None else tag.color
            if label.lower() != tag.label.lower():
                self._ensure_unique_label(state, label, excluding_id=tag_id)
            updated_tag = MetadataTag(
                id=tag.id,
                label=label,
                color=color,
                created_at=tag.created_at,
            )
            state.tags[tag_id] = updated_tag
            self._write_state(state)
            return Tag(
                id=updated_tag.id,
                label=updated_tag.label,
                color=updated_tag.color,
                created_at=updated_tag.created_at,
                usage_count=self._usage_counts(state).get(tag_id, 0),
            )

    def delete_tag(self, tag_id: str) -> None:
        with self._lock, FileLock(self.lock_path):
            state = self._load_state()
            if tag_id not in state.tags:
                raise FileNotFoundError(f"Tag '{tag_id}' not found.")
            state.tags.pop(tag_id)
            for note_metadata in state.notes.values():
                note_metadata.tag_ids = [
                    current_tag_id
                    for current_tag_id in note_metadata.tag_ids
                    if current_tag_id != tag_id
                ]
            self._write_state(state)

    def _load_state(self) -> MetadataState:
        if not os.path.isfile(self.file_path):
            return MetadataState(version=self.STATE_VERSION)
        with open(self.file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                logger.warning(
                    "Metadata file is invalid JSON. Falling back to empty metadata."
                )
                return MetadataState(version=self.STATE_VERSION)
        return MetadataState.model_validate(data)

    def _write_state(self, state: MetadataState) -> None:
        state.version = self.STATE_VERSION
        fd, tmp_path = tempfile.mkstemp(
            dir=self.storage_path, prefix="metadata-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state.model_dump(by_alias=True), f, indent=2)
            os.replace(tmp_path, self.file_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @staticmethod
    def _tag_ref_from_metadata(tag: MetadataTag) -> TagRef:
        return TagRef(id=tag.id, label=tag.label, color=tag.color)

    @staticmethod
    def _usage_counts(state: MetadataState) -> dict[str, int]:
        usage_counts = {tag_id: 0 for tag_id in state.tags.keys()}
        for note_metadata in state.notes.values():
            for tag_id in note_metadata.tag_ids:
                if tag_id in usage_counts:
                    usage_counts[tag_id] += 1
        return usage_counts

    @staticmethod
    def _filter_existing_tag_ids(
        state: MetadataState, tag_ids: list[str]
    ) -> list[str]:
        return [tag_id for tag_id in tag_ids if tag_id in state.tags]

    @staticmethod
    def _validate_tag_ids(
        state: MetadataState, tag_ids: list[str] | None
    ) -> list[str]:
        if tag_ids is None:
            return []
        deduped_tag_ids = list(dict.fromkeys(tag_ids))
        if len(deduped_tag_ids) > MAX_NOTE_TAGS:
            raise ValueError(
                f"Notes can have at most {MAX_NOTE_TAGS} custom tags."
            )
        invalid_tag_ids = [
            tag_id for tag_id in deduped_tag_ids if tag_id not in state.tags
        ]
        if invalid_tag_ids:
            raise ValueError(
                "Unknown tag ids: " + ", ".join(sorted(invalid_tag_ids))
            )
        return deduped_tag_ids

    @staticmethod
    def _ensure_unique_label(
        state: MetadataState, label: str, excluding_id: str | None = None
    ) -> None:
        label_lower = label.lower()
        for current_tag in state.tags.values():
            if current_tag.id == excluding_id:
                continue
            if current_tag.label.lower() == label_lower:
                raise FileExistsError(
                    f"A tag with the label '{label}' already exists."
                )

    @staticmethod
    def _generate_unique_tag_id(state: MetadataState, label: str) -> str:
        candidate = slugify_tag_id(label)
        if candidate not in state.tags:
            return candidate
        suffix = 2
        while f"{candidate}-{suffix}" in state.tags:
            suffix += 1
        return f"{candidate}-{suffix}"
