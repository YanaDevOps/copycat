import glob
import os
import threading
from typing import Literal

from fastapi import HTTPException, UploadFile

from attachments.file_system import FileSystemAttachments
from attachments.models import AttachmentCreateResponse
from auth.models import AuthPrincipal
from helpers import get_env, resolve_root_app_dir
from logger import logger
from metadata.file_system import FileSystemMetadata
from metadata.models import Tag, TagCreate, TagUpdate
from notes.file_system import FileSystemNotes
from notes.models import Note, NoteCreate, NoteUpdate, SearchResult
from global_config import AuthType, GlobalConfig

from .models import (
    AdminGroup,
    AdminUser,
    GroupCreate,
    GroupSummary,
    GroupUpdate,
    LibraryScope,
    UserCreate,
    UserUpdate,
)
from .passwords import hash_password
from .store import AccessRegistryStore


class AccessService:
    GROUPS_DIR = "groups"
    GROUP_METADATA_DIR = ".copycat"

    def __init__(self, base_path: str | None = None) -> None:
        self.base_path = base_path or get_env("COPYCAT_PATH", mandatory=True)
        self.bootstrap_admin_username = get_env(
            "COPYCAT_USERNAME", mandatory=False, default=""
        ).lower()
        self.auth_type = GlobalConfig().auth_type
        if not os.path.isdir(self.base_path):
            raise NotADirectoryError(
                f"'{self.base_path}' is not a valid directory."
            )
        self.registry = AccessRegistryStore(self.base_path)
        self._metadata_cache: dict[str, FileSystemMetadata] = {}
        self._notes_cache: dict[str, FileSystemNotes] = {}
        self._attachments_cache: dict[str, FileSystemAttachments] = {}
        self._cache_lock = threading.RLock()

    def list_available_groups(
        self, principal: AuthPrincipal
    ) -> list[GroupSummary]:
        if principal.is_admin:
            groups = self.registry.list_groups()
        else:
            allowed_ids = set(principal.group_ids)
            groups = [
                group
                for group in self.registry.list_groups()
                if group.id in allowed_ids
            ]
        return [GroupSummary(id=group.id, name=group.name) for group in groups]

    def default_group_id(self, principal: AuthPrincipal) -> str | None:
        if principal.is_admin:
            return "legacy"
        if len(principal.group_ids) == 0:
            return None
        return sorted(principal.group_ids)[0]

    def list_admin_groups(self, principal: AuthPrincipal) -> list[AdminGroup]:
        self._require_admin_console_access()
        self._require_admin(principal)
        user_counts = {}
        for user in self.registry.list_users():
            for group_id in user.group_ids:
                user_counts[group_id] = user_counts.get(group_id, 0) + 1

        groups = []
        for group in self.registry.list_groups():
            scope = self._group_scope(group.id)
            groups.append(
                AdminGroup(
                    id=group.id,
                    name=group.name,
                    slug=group.slug,
                    created_at=group.created_at,
                    is_active=group.is_active,
                    note_count=self._note_count(scope),
                    user_count=user_counts.get(group.id, 0),
                )
            )
        return groups

    def create_group(
        self, principal: AuthPrincipal, data: GroupCreate
    ) -> AdminGroup:
        self._require_write_mode()
        self._require_admin(principal)
        group = self.registry.create_group(data)
        scope = self._group_scope(group.id)
        self._ensure_scope_dirs(scope)
        logger.info(
            "Admin '%s' created group '%s'.",
            principal.username,
            group.id,
        )
        return AdminGroup(
            id=group.id,
            name=group.name,
            slug=group.slug,
            created_at=group.created_at,
            is_active=group.is_active,
            note_count=0,
            user_count=0,
        )

    def update_group(
        self, principal: AuthPrincipal, group_id: str, data: GroupUpdate
    ) -> AdminGroup:
        self._require_write_mode()
        self._require_admin(principal)
        group = self.registry.update_group(group_id, data)
        scope = self._group_scope(group.id)
        logger.info(
            "Admin '%s' updated group '%s'.",
            principal.username,
            group.id,
        )
        return AdminGroup(
            id=group.id,
            name=group.name,
            slug=group.slug,
            created_at=group.created_at,
            is_active=group.is_active,
            note_count=self._note_count(scope),
            user_count=self._group_user_count(group.id),
        )

    def delete_group(self, principal: AuthPrincipal, group_id: str) -> None:
        self._require_write_mode()
        self._require_admin(principal)
        scope = self._group_scope(group_id)
        if self._note_count(scope) > 0:
            raise HTTPException(
                status_code=409,
                detail="Delete all notes from this group before removing it.",
            )
        self.registry.delete_group(group_id)
        logger.info(
            "Admin '%s' deleted group '%s'.",
            principal.username,
            group_id,
        )

    def list_admin_users(self, principal: AuthPrincipal) -> list[AdminUser]:
        self._require_admin_console_access()
        self._require_admin(principal)
        return [
            self._admin_user_from_record(user)
            for user in self.registry.list_users()
        ]

    def create_user(self, principal: AuthPrincipal, data: UserCreate) -> AdminUser:
        self._require_write_mode()
        self._require_admin(principal)
        if data.username.lower() == self.bootstrap_admin_username:
            raise ValueError(
                "This username is reserved for the bootstrap administrator."
            )
        group_ids = self._validated_group_ids(data.group_ids)
        display_name = data.display_name or data.username
        user = self.registry.create_user(
            data.model_copy(update={"display_name": display_name}),
            hash_password(data.password),
            group_ids=group_ids,
        )
        logger.info(
            "Admin '%s' created user '%s'.",
            principal.username,
            user.username,
        )
        return self._admin_user_from_record(user)

    def update_user(
        self, principal: AuthPrincipal, username: str, data: UserUpdate
    ) -> AdminUser:
        self._require_write_mode()
        self._require_admin(principal)
        group_ids = (
            self._validated_group_ids(data.group_ids)
            if data.group_ids is not None
            else None
        )
        password_hash = hash_password(data.password) if data.password else None
        user = self.registry.update_user(
            username,
            data,
            password_hash=password_hash,
            group_ids=group_ids,
        )
        logger.info(
            "Admin '%s' updated user '%s'.",
            principal.username,
            user.username,
        )
        return self._admin_user_from_record(user)

    def delete_user(self, principal: AuthPrincipal, username: str) -> None:
        self._require_write_mode()
        self._require_admin(principal)
        self.registry.delete_user(username)
        logger.info(
            "Admin '%s' deleted user '%s'.",
            principal.username,
            username,
        )

    def get_note(
        self, principal: AuthPrincipal, title: str, group: str | None
    ) -> Note:
        scope = self.resolve_scope(principal, group)
        note = self._notes(scope).get(title)
        return self._annotate_note(note, scope)

    def create_note(
        self, principal: AuthPrincipal, data: NoteCreate, group: str | None
    ) -> Note:
        self._require_write_mode()
        scope = self.resolve_scope(principal, group, for_write=True)
        note = self._notes(scope).create(data)
        logger.info(
            "User '%s' created note '%s' in scope '%s'.",
            principal.username,
            note.title,
            scope.query_value,
        )
        return self._annotate_note(note, scope)

    def update_note(
        self,
        principal: AuthPrincipal,
        title: str,
        data: NoteUpdate,
        group: str | None,
    ) -> Note:
        self._require_write_mode()
        scope = self.resolve_scope(principal, group, for_write=True)
        note = self._notes(scope).update(title, data)
        logger.info(
            "User '%s' updated note '%s' in scope '%s'.",
            principal.username,
            note.title,
            scope.query_value,
        )
        return self._annotate_note(note, scope)

    def duplicate_note(
        self, principal: AuthPrincipal, title: str, group: str | None
    ) -> Note:
        self._require_write_mode()
        scope = self.resolve_scope(principal, group, for_write=True)
        note = self._notes(scope).duplicate(title)
        logger.info(
            "User '%s' duplicated note '%s' to '%s' in scope '%s'.",
            principal.username,
            title,
            note.title,
            scope.query_value,
        )
        return self._annotate_note(note, scope)

    def delete_note(
        self, principal: AuthPrincipal, title: str, group: str | None
    ) -> None:
        self._require_write_mode()
        scope = self.resolve_scope(principal, group, for_write=True)
        self._notes(scope).delete(title)
        logger.info(
            "User '%s' deleted note '%s' in scope '%s'.",
            principal.username,
            title,
            scope.query_value,
        )

    def export_note(
        self, principal: AuthPrincipal, title: str, group: str | None
    ):
        scope = self.resolve_scope(principal, group)
        logger.info(
            "User '%s' exported note '%s' from scope '%s'.",
            principal.username,
            title,
            scope.query_value,
        )
        return self._notes(scope).export(title)

    def export_all_notes(
        self, principal: AuthPrincipal, group: str | None
    ):
        import shutil
        import tempfile
        import zipfile

        from fastapi.responses import FileResponse
        from starlette.background import BackgroundTask

        scopes = self._export_archive_scopes(principal, group)
        archive_name = self._archive_filename(scopes)
        archive_root = os.path.splitext(archive_name)[0]
        temp_dir = tempfile.mkdtemp(prefix="copycat-export-")
        archive_path = os.path.join(temp_dir, archive_name)

        with zipfile.ZipFile(
            archive_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            archive.writestr(f"{archive_root}/", "")
            multiple_scopes = len(scopes) > 1
            for scope in scopes:
                scope_prefix = self._archive_scope_prefix(
                    archive_root, scope, multiple_scopes=multiple_scopes
                )
                archive.writestr(f"{scope_prefix}/", "")
                for note_path in sorted(
                    glob.glob(os.path.join(scope.notes_path, "*.md"))
                ):
                    archive.write(
                        note_path,
                        arcname=os.path.join(
                            scope_prefix, os.path.basename(note_path)
                        ),
                    )

        logger.info(
            "User '%s' exported archive '%s'.",
            principal.username,
            archive_name,
        )
        return FileResponse(
            archive_path,
            media_type="application/zip",
            filename=archive_name,
            background=BackgroundTask(
                shutil.rmtree, temp_dir, ignore_errors=True
            ),
        )

    def search_notes(
        self,
        principal: AuthPrincipal,
        *,
        group: str | None,
        term: str,
        sort: Literal["score", "title", "last_modified", "created_at"] = "score",
        order: Literal["asc", "desc"] = "desc",
        favorites_first: bool = True,
        tag_ids: list[str] | None = None,
        tag_mode: Literal["and", "or"] = "and",
        favorite_only: bool = False,
        limit: int | None = None,
    ) -> list[SearchResult]:
        normalized_group = (group or "").strip().lower()
        logger.debug(
            "Searching notes: user='%s', group='%s', term='%s', sort='%s', order='%s'.",
            principal.username,
            normalized_group or "<default>",
            term,
            sort,
            order,
        )
        if normalized_group == "all":
            scopes = self._all_scopes(principal)
            results = []
            for scope in scopes:
                results.extend(
                    self._annotate_search_results(
                        self._notes(scope).search(
                            term,
                            sort=sort,
                            order=order,
                            favorites_first=False,
                            tag_ids=tag_ids,
                            tag_mode=tag_mode,
                            favorite_only=favorite_only,
                            limit=None,
                        ),
                        scope,
                    )
                )
            sorted_results = self._sort_results(
                results,
                sort=sort,
                order=order,
                favorites_first=favorites_first,
            )
            return sorted_results[:limit] if limit is not None else sorted_results

        scope = self.resolve_scope(principal, group)
        results = self._notes(scope).search(
            term,
            sort=sort,
            order=order,
            favorites_first=favorites_first,
            tag_ids=tag_ids,
            tag_mode=tag_mode,
            favorite_only=favorite_only,
            limit=limit,
        )
        return self._annotate_search_results(results, scope)

    def get_tags(
        self, principal: AuthPrincipal, group: str | None
    ) -> list[Tag]:
        if (group or "").strip().lower() == "all":
            tags_by_id = {}
            for scope in self._all_scopes(principal):
                for tag in self._notes(scope).get_tags():
                    if tag.id not in tags_by_id:
                        tags_by_id[tag.id] = tag
                    else:
                        tags_by_id[tag.id].usage_count += tag.usage_count
            return sorted(
                tags_by_id.values(), key=lambda tag: tag.label.lower()
            )
        scope = self.resolve_scope(principal, group)
        return self._notes(scope).get_tags()

    def create_tag(
        self, principal: AuthPrincipal, data: TagCreate, group: str | None
    ) -> Tag:
        self._require_write_mode()
        scope = self.resolve_scope(principal, group, for_write=True)
        return self._metadata(scope).create_tag(data)

    def update_tag(
        self,
        principal: AuthPrincipal,
        tag_id: str,
        data: TagUpdate,
        group: str | None,
    ) -> Tag:
        self._require_write_mode()
        scope = self.resolve_scope(principal, group, for_write=True)
        return self._metadata(scope).update_tag(tag_id, data)

    def delete_tag(
        self, principal: AuthPrincipal, tag_id: str, group: str | None
    ) -> None:
        self._require_write_mode()
        scope = self.resolve_scope(principal, group, for_write=True)
        self._metadata(scope).delete_tag(tag_id)

    def get_attachment(
        self, principal: AuthPrincipal, filename: str, group: str | None
    ):
        scope = self.resolve_scope(principal, group)
        return self._attachments(scope).get(filename)

    def create_attachment(
        self,
        principal: AuthPrincipal,
        file: UploadFile,
        group: str | None,
    ) -> AttachmentCreateResponse:
        self._require_write_mode()
        scope = self.resolve_scope(principal, group, for_write=True)
        return self._attachments(scope).create(file)

    def resolve_scope(
        self,
        principal: AuthPrincipal,
        group: str | None,
        *,
        for_write: bool = False,
    ) -> LibraryScope:
        normalized_group = (group or "").strip().lower()
        if normalized_group == "all":
            if not principal.is_admin:
                logger.warning(
                    "Forbidden all-groups access for user '%s'.",
                    principal.username,
                )
                raise HTTPException(status_code=403, detail="Forbidden.")
            if for_write:
                raise HTTPException(
                    status_code=400,
                    detail="Select a specific group before modifying notes.",
                )
            raise HTTPException(
                status_code=400,
                detail="Use 'all' only for list and search requests.",
            )

        if not normalized_group:
            default_group_id = self.default_group_id(principal)
            if principal.is_admin:
                if for_write:
                    return self._legacy_scope()
                return self._legacy_scope()
            if default_group_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="You do not have access to any groups yet.",
                )
            normalized_group = default_group_id

        if normalized_group == "legacy":
            if not principal.is_admin:
                logger.warning(
                    "Forbidden legacy-scope access for user '%s'.",
                    principal.username,
                )
                raise HTTPException(status_code=403, detail="Forbidden.")
            return self._legacy_scope()

        group_record = self.registry.get_group(normalized_group)
        if group_record is None:
            raise HTTPException(status_code=404, detail="Group not found.")
        if not principal.is_admin and group_record.id not in principal.group_ids:
            logger.warning(
                "Forbidden group access for user '%s' to group '%s'.",
                principal.username,
                group_record.id,
            )
            raise HTTPException(status_code=403, detail="Forbidden.")
        scope = self._group_scope(group_record.id)
        self._ensure_scope_dirs(scope)
        return scope

    def _all_scopes(self, principal: AuthPrincipal) -> list[LibraryScope]:
        self._require_admin(principal)
        scopes = [self._legacy_scope()]
        for group in self.registry.list_groups():
            scope = self._group_scope(group.id)
            self._ensure_scope_dirs(scope)
            scopes.append(scope)
        return scopes

    def _export_archive_scopes(
        self, principal: AuthPrincipal, group: str | None
    ) -> list[LibraryScope]:
        if principal.is_admin:
            return self._all_scopes(principal)
        return [self.resolve_scope(principal, group)]

    @staticmethod
    def _archive_filename(scopes: list[LibraryScope]) -> str:
        from datetime import datetime

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        if len(scopes) > 1:
            archive_label = "all-notes"
        else:
            scope = scopes[0]
            archive_label = (
                scope.group_slug if scope.kind == "group" else "my-notes"
            )
        return f"copycat-{archive_label}-{timestamp}.zip"

    @staticmethod
    def _archive_scope_prefix(
        archive_root: str, scope: LibraryScope, *, multiple_scopes: bool
    ) -> str:
        if not multiple_scopes:
            return f"{archive_root}/notes"
        if scope.kind == "legacy":
            return f"{archive_root}/my-notes"
        return f"{archive_root}/groups/{scope.group_slug or scope.query_value}"

    def _legacy_scope(self) -> LibraryScope:
        metadata_path = resolve_root_app_dir(self.base_path)
        return LibraryScope(
            kind="legacy",
            query_value="legacy",
            display_name="My notes",
            notes_path=self.base_path,
            attachments_path=os.path.join(self.base_path, "attachments"),
            metadata_path=metadata_path,
            index_path=os.path.join(metadata_path, "index"),
            group_id=None,
            group_slug=None,
        )

    def _group_scope(self, group_id: str) -> LibraryScope:
        group_record = self.registry.get_group(group_id)
        if group_record is None:
            raise HTTPException(status_code=404, detail="Group not found.")
        group_root = os.path.join(self.base_path, self.GROUPS_DIR, group_record.slug)
        metadata_path = os.path.join(group_root, self.GROUP_METADATA_DIR)
        return LibraryScope(
            kind="group",
            query_value=group_record.id,
            display_name=group_record.name,
            notes_path=os.path.join(group_root, "notes"),
            attachments_path=os.path.join(group_root, "attachments"),
            metadata_path=metadata_path,
            index_path=os.path.join(metadata_path, "index"),
            group_id=group_record.id,
            group_slug=group_record.slug,
        )

    def _ensure_scope_dirs(self, scope: LibraryScope) -> None:
        os.makedirs(scope.notes_path, exist_ok=True)
        os.makedirs(scope.attachments_path, exist_ok=True)
        os.makedirs(scope.metadata_path, exist_ok=True)
        os.makedirs(scope.index_path, exist_ok=True)

    def _metadata(self, scope: LibraryScope) -> FileSystemMetadata:
        cache_key = scope.metadata_path
        with self._cache_lock:
            if cache_key not in self._metadata_cache:
                self._metadata_cache[cache_key] = FileSystemMetadata(
                    storage_path=scope.metadata_path
                )
            return self._metadata_cache[cache_key]

    def _notes(self, scope: LibraryScope) -> FileSystemNotes:
        cache_key = scope.notes_path
        with self._cache_lock:
            if cache_key not in self._notes_cache:
                metadata = self._metadata(scope)
                self._notes_cache[cache_key] = FileSystemNotes(
                    storage_path=scope.notes_path,
                    metadata_storage=metadata,
                    index_path=scope.index_path,
                    data_root=self.base_path,
                )
            return self._notes_cache[cache_key]

    def _attachments(self, scope: LibraryScope) -> FileSystemAttachments:
        cache_key = scope.attachments_path
        with self._cache_lock:
            if cache_key not in self._attachments_cache:
                query_params = (
                    {"group": scope.query_value}
                    if scope.kind == "group"
                    else {"group": "legacy"}
                )
                self._attachments_cache[cache_key] = FileSystemAttachments(
                    storage_path=scope.attachments_path,
                    url_prefix="attachments",
                    query_params=query_params,
                )
            return self._attachments_cache[cache_key]

    def _annotate_note(self, note: Note, scope: LibraryScope) -> Note:
        return note.model_copy(
            update={
                "group_id": scope.group_id,
                "group_name": scope.display_name,
            }
        )

    def _annotate_search_results(
        self,
        results: list[SearchResult] | tuple[SearchResult, ...],
        scope: LibraryScope,
    ) -> list[SearchResult]:
        return [
            result.model_copy(
                update={
                    "group_id": scope.group_id,
                    "group_name": scope.display_name,
                }
            )
            for result in results
        ]

    @staticmethod
    def _sort_results(
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
                key=lambda result: FileSystemNotes._alphabetical_sort_key(
                    result.title
                ),
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

    def _note_count(self, scope: LibraryScope) -> int:
        if not os.path.isdir(scope.notes_path):
            return 0
        return len(glob.glob(os.path.join(scope.notes_path, "*.md")))

    def _group_user_count(self, group_id: str) -> int:
        return sum(
            1 for user in self.registry.list_users() if group_id in user.group_ids
        )

    def _validated_group_ids(self, group_ids: list[str]) -> list[str]:
        normalized_group_ids = list(
            dict.fromkeys(group_id.lower() for group_id in group_ids)
        )
        missing_group_ids = [
            group_id
            for group_id in normalized_group_ids
            if self.registry.get_group(group_id) is None
        ]
        if missing_group_ids:
            raise ValueError(
                "Unknown groups: " + ", ".join(sorted(missing_group_ids))
            )
        return normalized_group_ids

    @staticmethod
    def _admin_user_from_record(user) -> AdminUser:
        return AdminUser(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            group_ids=user.group_ids,
            is_active=user.is_active,
            created_at=user.created_at,
        )

    @staticmethod
    def _require_admin(principal: AuthPrincipal) -> None:
        if not principal.is_admin:
            logger.warning(
                "Forbidden admin access attempt by user '%s'.",
                principal.username,
            )
            raise HTTPException(status_code=403, detail="Forbidden.")

    def _require_admin_console_access(self) -> None:
        if self.auth_type == AuthType.READ_ONLY:
            raise HTTPException(status_code=403, detail="Read-only mode.")

    def _require_write_mode(self) -> None:
        if self.auth_type == AuthType.READ_ONLY:
            raise HTTPException(status_code=403, detail="Read-only mode.")
