from abc import ABC, abstractmethod

from .models import NoteMetadata, Tag, TagCreate, TagRef, TagUpdate


class BaseMetadata(ABC):
    @abstractmethod
    def get_note_metadata(
        self, title: str, fallback_created_at: float | None = None
    ) -> NoteMetadata:
        """Return metadata for a note, falling back to defaults if missing."""
        pass

    @abstractmethod
    def update_note_metadata(
        self,
        title: str,
        *,
        created_at: float | None = None,
        favorite: bool | None = None,
        tag_ids: list[str] | None = None,
        fallback_created_at: float | None = None,
    ) -> NoteMetadata:
        """Create or update note metadata."""
        pass

    @abstractmethod
    def rename_note(self, old_title: str, new_title: str) -> None:
        """Move note metadata between note titles."""
        pass

    @abstractmethod
    def delete_note(self, title: str) -> None:
        """Delete note metadata."""
        pass

    @abstractmethod
    def note_count(self) -> int:
        """Return the number of notes tracked by metadata."""
        pass

    @abstractmethod
    def get_note_tags(self, title: str) -> list[TagRef]:
        """Return resolved tag references for a note."""
        pass

    @abstractmethod
    def list_tags(self) -> list[Tag]:
        """Return all global tags."""
        pass

    @abstractmethod
    def create_tag(self, data: TagCreate) -> Tag:
        """Create a new global tag."""
        pass

    @abstractmethod
    def update_tag(self, tag_id: str, data: TagUpdate) -> Tag:
        """Update an existing global tag."""
        pass

    @abstractmethod
    def delete_tag(self, tag_id: str) -> None:
        """Delete a global tag and remove it from all notes."""
        pass
