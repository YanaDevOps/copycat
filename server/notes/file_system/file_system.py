import glob
import html
import os
import re
import shutil
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Set, Tuple

import whoosh
from fastapi.responses import FileResponse
from whoosh import writing
from whoosh.analysis import CharsetFilter, StemmingAnalyzer
from whoosh.fields import DATETIME, ID, KEYWORD, TEXT, SchemaClass
from whoosh.highlight import ContextFragmenter, WholeFragmenter
from whoosh.index import Index, LockError
from whoosh.qparser import MultifieldParser
from whoosh.qparser.dateparse import DateParserPlugin
from whoosh.searching import Hit
from whoosh.support.charset import accent_map

from helpers import get_env, is_valid_filename, resolve_root_app_dir
from logger import logger
from metadata.file_system import FileSystemMetadata
from metadata.models import Tag, TagRef
from path_safety import UnsafeIndexPathError, assert_safe_index_directory

from ..base import BaseNotes
from ..models import Note, NoteCreate, NoteUpdate, SearchResult

MARKDOWN_EXT = ".md"
INDEX_SCHEMA_VERSION = "5"

StemmingFoldingAnalyzer = StemmingAnalyzer() | CharsetFilter(accent_map)


class IndexSchema(SchemaClass):
    filename = ID(unique=True, stored=True)
    last_modified = DATETIME(stored=True, sortable=True)
    title = TEXT(
        field_boost=2.0, analyzer=StemmingFoldingAnalyzer, sortable=True
    )
    content = TEXT(analyzer=StemmingFoldingAnalyzer)
    tags = KEYWORD(lowercase=True, field_boost=2.0)


@dataclass(frozen=True)
class ParsedSearchTerm:
    raw_term: str
    text_term: str
    tag_terms: tuple[str, ...]
    normalized_text_term: str
    normalized_tokens: tuple[str, ...]


class FileSystemNotes(BaseNotes):
    TAGS_RE = re.compile(r"(?:(?<=^#)|(?<=\s#))[a-zA-Z0-9_-]+(?=\s|$)")
    CODEBLOCK_RE = re.compile(r"`{1,3}.*?`{1,3}", re.DOTALL)
    TAGS_WITH_HASH_RE = re.compile(
        r"(?:(?<=^)|(?<=\s))#[a-zA-Z0-9_-]+(?=\s|$)"
    )

    def __init__(
        self,
        storage_path: str | None = None,
        metadata_storage=None,
        index_path: str | None = None,
        data_root: str | None = None,
    ):
        self.storage_path = storage_path or get_env(
            "COPYCAT_PATH", mandatory=True
        )
        self.data_root = data_root or get_env(
            "COPYCAT_PATH", mandatory=False, default=self.storage_path
        )
        if not os.path.exists(self.storage_path):
            raise NotADirectoryError(
                f"'{self.storage_path}' is not a valid directory."
            )
        self.metadata_storage = metadata_storage or FileSystemMetadata()
        self.index_path = index_path or os.path.join(
            resolve_root_app_dir(self.storage_path), "index"
        )
        self._warned_empty_note_metadata_history = False
        self._validate_index_path()
        logger.info(
            "Initializing notes storage: data_root='%s', notes_path='%s', "
            "metadata_path='%s', index_path='%s'.",
            self.data_root,
            self.storage_path,
            getattr(self.metadata_storage, "storage_path", "unknown"),
            self.index_path,
        )
        self.index = self._load_index()
        self._sync_index_with_retry(optimize=True)

    def create(self, data: NoteCreate) -> Note:
        """Create a new note."""
        filepath = self._path_from_title(data.title)
        self._write_file(filepath, data.content or "")
        self.metadata_storage.update_note_metadata(
            data.title,
            created_at=self._created_at_for_filepath(filepath),
            favorite=data.favorite,
            tag_ids=data.tag_ids or [],
        )
        return self.get(data.title)

    def get(self, title: str) -> Note:
        """Get a specific note."""
        is_valid_filename(title)
        return self._note_from_title(title, include_content=True)

    def update(self, title: str, data: NoteUpdate) -> Note:
        """Update a specific note."""
        is_valid_filename(title)
        filepath = self._path_from_title(title)
        existing_metadata = self.metadata_storage.get_note_metadata(
            title, fallback_created_at=self._created_at_for_filepath(filepath)
        )

        if data.new_title is not None:
            new_filepath = self._path_from_title(data.new_title)
            if filepath != new_filepath and os.path.isfile(new_filepath):
                raise FileExistsError(
                    f"Failed to rename. '{data.new_title}' already exists."
                )
            os.rename(filepath, new_filepath)
            self.metadata_storage.rename_note(title, data.new_title)
            title = data.new_title
            filepath = new_filepath

        if data.new_content is not None:
            self._write_file(filepath, data.new_content, overwrite=True)

        self.metadata_storage.update_note_metadata(
            title,
            created_at=existing_metadata.created_at
            or self._created_at_for_filepath(filepath),
            favorite=data.favorite,
            tag_ids=data.tag_ids,
            fallback_created_at=self._created_at_for_filepath(filepath),
        )
        return self.get(title)

    def duplicate(self, title: str) -> Note:
        """Duplicate a specific note."""
        is_valid_filename(title)
        note = self.get(title)
        target_title = self._next_duplicate_title(title)
        target_path = self._path_from_title(target_title)
        self._write_file(target_path, note.content or "")
        self.metadata_storage.update_note_metadata(
            target_title,
            created_at=self._created_at_for_filepath(target_path),
            favorite=False,
            tag_ids=[tag.id for tag in note.tags],
        )
        return self.get(target_title)

    def delete(self, title: str) -> None:
        """Delete a specific note."""
        is_valid_filename(title)
        filepath = self._path_from_title(title)
        os.remove(filepath)
        self.metadata_storage.delete_note(title)

    def search(
        self,
        term: str,
        sort: Literal["score", "title", "last_modified", "created_at"] = "score",
        order: Literal["asc", "desc"] = "desc",
        favorites_first: bool = True,
        tag_ids: list[str] | None = None,
        tag_mode: Literal["and", "or"] = "and",
        favorite_only: bool = False,
        limit: int = None,
    ) -> Tuple[SearchResult, ...]:
        """Search the index for the given term."""
        parsed_term = self._parse_search_term(term)
        if parsed_term.raw_term == "*":
            results = self._list_results_without_content(
                favorite_only=favorite_only,
                tag_ids=tag_ids or [],
                tag_mode=tag_mode,
            )
            sorted_results = self._sort_results(
                results,
                sort=sort,
                order=order,
                favorites_first=favorites_first,
            )
            if limit is not None:
                sorted_results = sorted_results[:limit]
            return tuple(sorted_results)

        self._sync_index_with_retry()
        indexed_results = self._search_index(parsed_term.text_term)
        results = []
        for filename in self._list_all_note_filenames():
            title = self._strip_ext(filename)
            note = self._note_from_title(title, include_content=True)
            inline_tag_ids = self._extract_inline_tag_ids(note.content or "")

            if favorite_only and note.favorite is False:
                continue
            if not self._matches_selected_tags(
                [tag.id for tag in note.tags], tag_ids or [], tag_mode
            ):
                continue

            indexed_result = indexed_results.get(title)
            manual_match = self._manual_search_result(
                note, parsed_term, inline_tag_ids
            )
            if parsed_term.raw_term != "*":
                if indexed_result is None and manual_match is None:
                    continue
                if not self._matches_search_tag_terms(
                    parsed_term.tag_terms, note.tags, inline_tag_ids
                ):
                    continue
            merged_result = self._merge_search_results(
                note, indexed_result, manual_match
            )
            results.append(merged_result)

        sorted_results = self._sort_results(
            results,
            sort=sort,
            order=order,
            favorites_first=favorites_first,
        )
        if limit is not None:
            sorted_results = sorted_results[:limit]
        return tuple(sorted_results)

    def _list_results_without_content(
        self,
        *,
        favorite_only: bool,
        tag_ids: list[str],
        tag_mode: Literal["and", "or"],
    ) -> list[SearchResult]:
        results = []
        for filename in self._list_all_note_filenames():
            title = self._strip_ext(filename)
            note = self._note_from_title(title, include_content=False)

            if favorite_only and note.favorite is False:
                continue
            if not self._matches_selected_tags(
                [tag.id for tag in note.tags], tag_ids, tag_mode
            ):
                continue

            results.append(
                SearchResult(
                    title=note.title,
                    last_modified=note.last_modified,
                    created_at=note.created_at,
                    favorite=note.favorite,
                    tags=note.tags,
                )
            )
        return results

    def export(self, title: str) -> FileResponse:
        """Export a specific note as markdown."""
        is_valid_filename(title)
        filepath = self._path_from_title(title)
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"'{title}' not found.")
        return FileResponse(
            filepath,
            media_type="text/markdown",
            filename=os.path.basename(filepath),
        )

    def get_tags(self) -> list[Tag]:
        """Return all custom tags."""
        return self.metadata_storage.list_tags()

    @property
    def _index_path(self):
        return self.index_path

    def _path_from_title(self, title: str) -> str:
        return os.path.join(self.storage_path, title + MARKDOWN_EXT)

    def _get_by_filename(self, filename: str) -> Note:
        """Get a note by its filename."""
        return self.get(self._strip_ext(filename))

    def _load_index(self) -> Index:
        """Load the note index or create new if not exists."""
        index_path = self._validate_index_path()
        index_dir_exists = os.path.exists(index_path)
        if index_dir_exists and not os.path.isdir(index_path):
            raise UnsafeIndexPathError(
                f"Refusing to use index path '{index_path}' because it is "
                "not a directory."
            )
        if index_dir_exists and whoosh.index.exists_in(
            index_path, indexname=INDEX_SCHEMA_VERSION
        ):
            logger.info("Loading existing index from '%s'.", index_path)
            return whoosh.index.open_dir(
                index_path, indexname=INDEX_SCHEMA_VERSION
            )
        else:
            if index_dir_exists:
                logger.info(
                    "Deleting outdated index cache at '%s'.", index_path
                )
                self._clear_index_dir(index_path)
            else:
                os.makedirs(index_path, exist_ok=True)
            logger.info("Creating new index at '%s'.", index_path)
            return whoosh.index.create_in(
                index_path, IndexSchema, indexname=INDEX_SCHEMA_VERSION
            )

    @classmethod
    def _extract_tags(cls, content) -> Tuple[str, Set[str]]:
        """Strip inline markdown tags from content."""
        content_ex_codeblock = re.sub(cls.CODEBLOCK_RE, "", content)
        _, tags = cls._re_extract(cls.TAGS_RE, content_ex_codeblock)
        content_ex_tags, _ = cls._re_extract(cls.TAGS_RE, content)
        tags = [tag.lower() for tag in tags]
        return (content_ex_tags, set(tags))

    def _add_note_to_index(
        self, writer: writing.IndexWriter, note: Note
    ) -> None:
        """Add a Note object to the index using the given writer."""
        content_ex_tags, tag_set = self._extract_tags(note.content or "")
        tag_string = " ".join(tag_set)
        writer.update_document(
            filename=note.title + MARKDOWN_EXT,
            last_modified=datetime.fromtimestamp(note.last_modified),
            title=note.title,
            content=content_ex_tags,
            tags=tag_string,
        )

    def _list_all_note_filenames(self) -> List[str]:
        """Return a list of all note filenames."""
        filenames = [
            os.path.split(filepath)[1]
            for filepath in glob.glob(
                os.path.join(self.storage_path, "*" + MARKDOWN_EXT)
            )
        ]
        self._warn_if_notes_missing_with_metadata_history(len(filenames))
        return filenames

    def _sync_index(self, optimize: bool = False, clean: bool = False) -> None:
        """Synchronize the index with the notes directory."""
        indexed = set()
        note_filenames = self._list_all_note_filenames()
        note_count_before = len(note_filenames)
        writer = self.index.writer()
        if clean:
            writer.mergetype = writing.CLEAR
        with self.index.searcher() as searcher:
            for idx_note in searcher.all_stored_fields():
                idx_filename = idx_note["filename"]
                idx_filepath = os.path.join(self.storage_path, idx_filename)
                if not os.path.exists(idx_filepath):
                    writer.delete_by_term("filename", idx_filename)
                    logger.info(f"'{idx_filename}' removed from index")
                elif (
                    datetime.fromtimestamp(os.path.getmtime(idx_filepath))
                    != idx_note["last_modified"]
                ):
                    logger.info(f"'{idx_filename}' updated")
                    self._add_note_to_index(
                        writer, self._get_by_filename(idx_filename)
                    )
                    indexed.add(idx_filename)
                else:
                    indexed.add(idx_filename)
        for filename in note_filenames:
            if filename not in indexed:
                self._add_note_to_index(
                    writer, self._get_by_filename(filename)
                )
                logger.info(f"'{filename}' added to index")
        writer.commit(optimize=optimize)
        note_count_after = len(self._list_all_note_filenames())
        logger.info(
            "Index synchronized for '%s' (notes_before=%d, notes_after=%d).",
            self.storage_path,
            note_count_before,
            note_count_after,
        )

    def _sync_index_with_retry(
        self,
        optimize: bool = False,
        clean: bool = False,
        max_retries: int = 8,
        retry_delay: float = 0.25,
    ) -> None:
        for _ in range(max_retries):
            try:
                self._sync_index(optimize=optimize, clean=clean)
                return
            except LockError:
                logger.warning(f"Index locked, retrying in {retry_delay}s")
                time.sleep(retry_delay)
        logger.error(f"Failed to sync index after {max_retries} retries")

    def _search_index(self, text_term: str) -> dict[str, SearchResult]:
        if text_term.strip() == "":
            return {}
        with self.index.searcher() as searcher:
            parser = MultifieldParser(["title", "content"], self.index.schema)
            parser.add_plugin(DateParserPlugin())
            query = parser.parse(text_term)
            results = searcher.search(
                query,
                sortedby=None,
                reverse=False,
                limit=None,
                terms=True,
            )
            return {
                self._strip_ext(hit["filename"]): self._search_result_from_hit(hit)
                for hit in results
            }

    def _note_from_title(self, title: str, include_content: bool) -> Note:
        filepath = self._path_from_title(title)
        content = self._read_file(filepath) if include_content else None
        created_at = self._created_at_for_filepath(filepath)
        note_metadata = self.metadata_storage.get_note_metadata(
            title, fallback_created_at=created_at
        )
        return Note(
            title=title,
            content=content,
            last_modified=os.path.getmtime(filepath),
            created_at=note_metadata.created_at or created_at,
            favorite=note_metadata.favorite,
            tags=self.metadata_storage.get_note_tags(title),
        )

    def _manual_search_result(
        self,
        note: Note,
        parsed_term: ParsedSearchTerm,
        inline_tag_ids: set[str],
    ) -> SearchResult | None:
        if parsed_term.raw_term == "*":
            return SearchResult(
                title=note.title,
                last_modified=note.last_modified,
                created_at=note.created_at,
                favorite=note.favorite,
                tags=note.tags,
            )

        if parsed_term.text_term == "":
            title_match = {"matched": False, "kind": ""}
            content_match = {"matched": False, "kind": ""}
            matched_custom_tags = []
            matched_inline_tags = []
        else:
            title_match = self._manual_text_match(
                note.title,
                parsed_term.normalized_text_term,
                parsed_term.normalized_tokens,
            )
            content_match = self._manual_text_match(
                note.content or "",
                parsed_term.normalized_text_term,
                parsed_term.normalized_tokens,
            )
            matched_custom_tags = self._matched_tag_labels(
                note.tags,
                parsed_term.normalized_text_term,
                parsed_term.normalized_tokens,
            )
            matched_inline_tags = [
                inline_tag_id
                for inline_tag_id in inline_tag_ids
                if self._matches_normalized_text(
                    inline_tag_id,
                    parsed_term.normalized_text_term,
                    parsed_term.normalized_tokens,
                )
            ]

        if (
            parsed_term.text_term
            and not title_match["matched"]
            and not content_match["matched"]
            and len(matched_custom_tags) == 0
            and len(matched_inline_tags) == 0
        ):
            return None

        if not self._matches_search_tag_terms(
            parsed_term.tag_terms, note.tags, inline_tag_ids
        ):
            return None

        score = 0.0
        title_highlights = None
        content_highlights = None
        if title_match["matched"]:
            score = 500.0 if title_match["kind"] == "full" else 350.0
            title_highlights = self._highlight_text(
                note.title, parsed_term.normalized_text_term, parsed_term.normalized_tokens
            )
        elif matched_custom_tags or matched_inline_tags:
            score = 275.0
        elif content_match["matched"]:
            score = 200.0 if content_match["kind"] == "full" else 125.0
            content_highlights = self._highlight_excerpt(
                note.content or "",
                parsed_term.normalized_text_term,
                parsed_term.normalized_tokens,
            )

        matched_labels = list(dict.fromkeys(matched_custom_tags + matched_inline_tags))
        return SearchResult(
            title=note.title,
            last_modified=note.last_modified,
            created_at=note.created_at,
            favorite=note.favorite,
            tags=note.tags,
            score=score,
            title_highlights=title_highlights,
            content_highlights=content_highlights,
            tag_matches=matched_labels or None,
        )

    def _merge_search_results(
        self,
        note: Note,
        indexed_result: SearchResult | None,
        manual_result: SearchResult | None,
    ) -> SearchResult:
        if indexed_result is None and manual_result is not None:
            return manual_result
        if indexed_result is not None and manual_result is None:
            indexed_result.favorite = note.favorite
            indexed_result.created_at = note.created_at
            indexed_result.tags = note.tags
            return indexed_result
        if indexed_result is None:
            return SearchResult(
                title=note.title,
                last_modified=note.last_modified,
                created_at=note.created_at,
                favorite=note.favorite,
                tags=note.tags,
            )
        return SearchResult(
            title=note.title,
            last_modified=note.last_modified,
            created_at=note.created_at,
            favorite=note.favorite,
            tags=note.tags,
            score=max(indexed_result.score or 0.0, manual_result.score or 0.0),
            title_highlights=
            indexed_result.title_highlights or manual_result.title_highlights,
            content_highlights=indexed_result.content_highlights
            or manual_result.content_highlights,
            tag_matches=self._merge_tag_matches(
                indexed_result.tag_matches, manual_result.tag_matches
            ),
        )

    def _sort_results(
        self,
        results: list[SearchResult],
        *,
        sort: str,
        order: str,
        favorites_first: bool,
    ) -> list[SearchResult]:
        reverse = order == "desc"
        if sort == "title":
            sorted_results = sorted(
                results,
                key=lambda result: self._alphabetical_sort_key(result.title),
                reverse=reverse,
            )
        elif sort == "created_at":
            sorted_results = sorted(
                results,
                key=lambda result: result.created_at,
                reverse=reverse,
            )
        elif sort == "last_modified":
            sorted_results = sorted(
                results,
                key=lambda result: result.last_modified,
                reverse=reverse,
            )
        else:
            sorted_results = sorted(
                results,
                key=lambda result: result.score or 0.0,
                reverse=reverse,
            )
        if favorites_first:
            favorites = [result for result in sorted_results if result.favorite]
            others = [result for result in sorted_results if not result.favorite]
            return favorites + others
        return sorted_results

    def _search_result_from_hit(self, hit: Hit):
        matched_fields = self._get_matched_fields(hit.matched_terms())

        title = self._strip_ext(hit["filename"])
        filepath = self._path_from_title(title)
        note_metadata = self.metadata_storage.get_note_metadata(
            title, fallback_created_at=self._created_at_for_filepath(filepath)
        )
        tags = self.metadata_storage.get_note_tags(title)
        last_modified = hit["last_modified"].timestamp()
        score = hit.score if isinstance(hit.score, float) else None

        if "title" in matched_fields:
            hit.results.fragmenter = WholeFragmenter()
            title_highlights = hit.highlights("title", text=title)
        else:
            title_highlights = None

        if "content" in matched_fields:
            hit.results.fragmenter = ContextFragmenter()
            content = self._read_file(self._path_from_title(title))
            content_ex_tags, _ = FileSystemNotes._extract_tags(content)
            content_highlights = hit.highlights(
                "content",
                text=content_ex_tags,
            )
        else:
            content_highlights = None

        return SearchResult(
            title=title,
            last_modified=last_modified,
            created_at=note_metadata.created_at
            or self._created_at_for_filepath(filepath),
            favorite=note_metadata.favorite,
            tags=tags,
            score=score,
            title_highlights=title_highlights,
            content_highlights=content_highlights,
        )

    @classmethod
    def _parse_search_term(cls, term: str) -> ParsedSearchTerm:
        raw_term = term.strip() or "*"
        tag_terms = tuple(
            match.lower()
            for match in re.findall(
                r"(?:(?<=^)|(?<=\s))#([a-zA-Z0-9_-]+)(?=\s|$)", raw_term
            )
        )
        text_term = re.sub(
            r"(?:(?<=^)|(?<=\s))#[a-zA-Z0-9_-]+(?=\s|$)", "", raw_term
        ).strip()
        normalized_text_term = cls._normalize_text(text_term)
        normalized_tokens = tuple(
            token for token in re.split(r"\s+", normalized_text_term) if token
        )
        return ParsedSearchTerm(
            raw_term=raw_term,
            text_term=text_term,
            tag_terms=tag_terms,
            normalized_text_term=normalized_text_term,
            normalized_tokens=normalized_tokens,
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        value = unicodedata.normalize("NFKD", value)
        value = value.encode("ascii", "ignore").decode("ascii")
        value = re.sub(r"\s+", " ", value.lower()).strip()
        return value

    @classmethod
    def _manual_text_match(
        cls,
        value: str,
        normalized_text_term: str,
        normalized_tokens: tuple[str, ...],
    ) -> dict[str, str | bool]:
        if normalized_text_term == "":
            return {"matched": True, "kind": "full"}
        normalized_value = cls._normalize_text(value)
        if normalized_text_term in normalized_value:
            return {"matched": True, "kind": "full"}
        if normalized_tokens and all(
            token in normalized_value for token in normalized_tokens
        ):
            return {"matched": True, "kind": "token"}
        return {"matched": False, "kind": ""}

    @classmethod
    def _matches_normalized_text(
        cls,
        value: str,
        normalized_text_term: str,
        normalized_tokens: tuple[str, ...],
    ) -> bool:
        return cls._manual_text_match(
            value, normalized_text_term, normalized_tokens
        )["matched"]

    @classmethod
    def _matched_tag_labels(
        cls,
        tags: list[TagRef],
        normalized_text_term: str,
        normalized_tokens: tuple[str, ...],
    ) -> list[str]:
        matched_labels = []
        for tag in tags:
            if cls._matches_normalized_text(
                tag.label, normalized_text_term, normalized_tokens
            ) or cls._matches_normalized_text(
                tag.id, normalized_text_term, normalized_tokens
            ):
                matched_labels.append(tag.label)
        return matched_labels

    @staticmethod
    def _matches_search_tag_terms(
        tag_terms: tuple[str, ...], tags: list[TagRef], inline_tag_ids: set[str]
    ) -> bool:
        if len(tag_terms) == 0:
            return True
        custom_tag_ids = {tag.id.lower() for tag in tags}
        inline_tag_ids = {tag_id.lower() for tag_id in inline_tag_ids}
        return all(
            tag_term in custom_tag_ids or tag_term in inline_tag_ids
            for tag_term in tag_terms
        )

    @staticmethod
    def _matches_selected_tags(
        note_tag_ids: list[str],
        selected_tag_ids: list[str],
        tag_mode: Literal["and", "or"],
    ) -> bool:
        if len(selected_tag_ids) == 0:
            return True
        note_tag_ids = set(note_tag_ids)
        if tag_mode == "or":
            return any(tag_id in note_tag_ids for tag_id in selected_tag_ids)
        return all(tag_id in note_tag_ids for tag_id in selected_tag_ids)

    @staticmethod
    def _merge_tag_matches(
        indexed_matches: list[str] | None,
        manual_matches: list[str] | None,
    ) -> list[str] | None:
        merged = list(dict.fromkeys((indexed_matches or []) + (manual_matches or [])))
        return merged or None

    @classmethod
    def _highlight_text(
        cls,
        text: str,
        normalized_text_term: str,
        normalized_tokens: tuple[str, ...],
    ) -> str:
        highlight_term = cls._first_highlight_term(
            text, normalized_text_term, normalized_tokens
        )
        return cls._replace_first_match(text, highlight_term)

    @classmethod
    def _highlight_excerpt(
        cls,
        text: str,
        normalized_text_term: str,
        normalized_tokens: tuple[str, ...],
        context_window: int = 60,
    ) -> str:
        highlight_term = cls._first_highlight_term(
            text, normalized_text_term, normalized_tokens
        )
        if highlight_term is None:
            return html.escape(text[: context_window * 2])
        match = re.search(re.escape(highlight_term), text, re.IGNORECASE)
        if match is None:
            return html.escape(text[: context_window * 2])
        start = max(match.start() - context_window, 0)
        end = min(match.end() + context_window, len(text))
        excerpt = text[start:end]
        highlighted_excerpt = cls._replace_first_match(excerpt, highlight_term)
        if start > 0:
            highlighted_excerpt = "..." + highlighted_excerpt
        if end < len(text):
            highlighted_excerpt += "..."
        return highlighted_excerpt

    @classmethod
    def _first_highlight_term(
        cls,
        text: str,
        normalized_text_term: str,
        normalized_tokens: tuple[str, ...],
    ) -> str | None:
        if normalized_text_term and re.search(
            re.escape(normalized_text_term), cls._normalize_text(text)
        ):
            return normalized_text_term
        for token in normalized_tokens:
            if re.search(re.escape(token), cls._normalize_text(text)):
                return token
        return None

    @staticmethod
    def _replace_first_match(text: str, term: str | None) -> str:
        if term is None or term == "":
            return html.escape(text)
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        match = pattern.search(text)
        if match is None:
            return html.escape(text)
        return (
            html.escape(text[: match.start()])
            + '<span class="match">'
            + html.escape(text[match.start() : match.end()])
            + "</span>"
            + html.escape(text[match.end() :])
        )

    @classmethod
    def _extract_inline_tag_ids(cls, content: str) -> set[str]:
        _, tags = cls._extract_tags(content)
        return tags

    @classmethod
    def _alphabetical_sort_key(cls, title: str) -> tuple[str, str]:
        normalized = cls._normalize_text(title)
        trimmed = re.sub(r"^[^a-z0-9]+", "", normalized)
        trimmed = trimmed or normalized or title.lower()
        return (trimmed, normalized)

    @staticmethod
    def _re_extract(pattern, string) -> Tuple[str, List[str]]:
        matches = []
        text = re.sub(pattern, lambda tag: matches.append(tag.group()), string)
        return (text, matches)

    @staticmethod
    def _strip_ext(filename):
        return os.path.splitext(filename)[0]

    def _validate_index_path(self) -> str:
        try:
            return assert_safe_index_directory(
                index_path=self.index_path,
                data_root=self.data_root,
                notes_path=self.storage_path,
            )
        except UnsafeIndexPathError:
            logger.critical(
                "Unsafe index path configuration: data_root='%s', "
                "notes_path='%s', index_path='%s'. Refusing to continue.",
                self.data_root,
                self.storage_path,
                self.index_path,
            )
            raise

    def _clear_index_dir(self, path):
        path = assert_safe_index_directory(
            index_path=path,
            data_root=self.data_root,
            notes_path=self.storage_path,
        )
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)

    def _warn_if_notes_missing_with_metadata_history(
        self, note_count: int
    ) -> None:
        if note_count != 0 or self._warned_empty_note_metadata_history:
            return
        metadata_note_count = self._metadata_note_count()
        if metadata_note_count == 0:
            return
        self._warned_empty_note_metadata_history = True
        logger.error(
            "No markdown notes were found in '%s', but metadata at '%s' "
            "references %d notes. This can indicate a wrong mount, stale "
            "mount, or data loss on the persistent volume.",
            self.storage_path,
            getattr(self.metadata_storage, "file_path", "unknown"),
            metadata_note_count,
        )

    def _metadata_note_count(self) -> int:
        note_count = getattr(self.metadata_storage, "note_count", None)
        if not callable(note_count):
            return 0
        try:
            return int(note_count())
        except Exception:
            logger.exception("Failed to inspect note metadata count.")
            return 0

    @staticmethod
    def _get_matched_fields(matched_terms):
        return set([matched_term[0] for matched_term in matched_terms])

    @staticmethod
    def _read_file(filepath: str):
        logger.debug(f"Reading from '{filepath}'")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return content

    @staticmethod
    def _write_file(filepath: str, content: str, overwrite: bool = False):
        logger.debug(f"Writing to '{filepath}'")
        if not overwrite:
            with open(filepath, "x", encoding="utf-8") as f:
                f.write(content)
            return

        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(filepath),
            prefix=".copycat-note-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, filepath)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @staticmethod
    def _created_at_for_filepath(filepath: str) -> float:
        try:
            return os.path.getctime(filepath)
        except OSError:
            return os.path.getmtime(filepath)

    def _next_duplicate_title(self, title: str) -> str:
        candidate = f"{title}-copy"
        suffix = 2
        while os.path.exists(self._path_from_title(candidate)):
            candidate = f"{title}-copy-{suffix}"
            suffix += 1
        return candidate
