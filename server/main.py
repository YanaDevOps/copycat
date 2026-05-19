from typing import List, Literal

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import api_messages
from access.models import AdminGroup, AdminUser, GroupCreate, GroupUpdate, UserCreate, UserUpdate
from access.service import AccessService
from attachments.file_system.file_system import (
    AttachmentTooLargeError,
    AttachmentTypeBlockedError,
)
from attachments.models import AttachmentCreateResponse
from auth.base import BaseAuth
from auth.models import AuthPrincipal, Login, Token
from data_guard import guard_data_root
from global_config import AuthType, GlobalConfig, GlobalConfigResponseModel
from helpers import replace_base_href
from logger import logger
from metadata.models import Tag, TagCreate, TagUpdate
from notes.models import Note, NoteCreate, NoteUpdate, SearchResult
from security import (
    LoginRateLimiter,
    apply_security_headers,
    get_client_ip,
    is_private_path,
    request_uses_https,
)

global_config = GlobalConfig()
data_root_summary = guard_data_root()
auth: BaseAuth = global_config.load_auth()
access_service = AccessService()
router = APIRouter()
app = FastAPI(
    docs_url=global_config.path_prefix + "/docs",
    openapi_url=global_config.path_prefix + "/openapi.json",
)
replace_base_href("client/dist/index.html", global_config.path_prefix)
login_rate_limiter = LoginRateLimiter(
    enabled=global_config.login_rate_limit_enabled,
    window_seconds=global_config.login_rate_limit_window_seconds,
    ip_max_attempts=global_config.login_rate_limit_ip_max,
    user_ip_max_attempts=global_config.login_rate_limit_user_ip_max,
)

logger.info(
    "CopyCat startup configuration: auth_type='%s', path_prefix='%s', "
    "csp_mode='%s', login_rate_limit_enabled=%s, data_root='%s'.",
    global_config.auth_type.value,
    global_config.path_prefix or "/",
    global_config.csp_mode,
    global_config.login_rate_limit_enabled,
    data_root_summary.data_root,
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled request error: method=%s path=%s",
            request.method,
            request.url.path,
        )
        raise
    apply_security_headers(
        response,
        csp_mode=global_config.csp_mode,
        cache_private=is_private_path(
            request.url.path,
            global_config.path_prefix,
        ),
    )
    return response


if auth:

    def get_current_principal(
        principal: AuthPrincipal = Depends(auth.authenticate),
    ) -> AuthPrincipal:
        return principal


else:

    def get_current_principal() -> AuthPrincipal:
        return AuthPrincipal(
            username="anonymous",
            role="admin",
            group_ids=[],
            is_admin=True,
        )


def get_optional_principal(request: Request) -> AuthPrincipal | None:
    if auth is None:
        return AuthPrincipal(
            username="anonymous",
            role="admin",
            group_ids=[],
            is_admin=True,
        )
    token = None
    authorization = request.headers.get("Authorization")
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    if token is None:
        token = request.cookies.get("token")
    if token is None:
        return None
    try:
        return auth.authenticate(request, token)
    except HTTPException:
        return None


# region UI
@router.get("/", include_in_schema=False)
@router.get("/login", include_in_schema=False)
@router.get("/search", include_in_schema=False)
@router.get("/tags", include_in_schema=False)
@router.get("/new", include_in_schema=False)
@router.get("/note/{title}", include_in_schema=False)
@router.get("/admin/groups-users", include_in_schema=False)
def root(title: str = ""):
    with open("client/dist/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    response = HTMLResponse(content=html)
    apply_security_headers(
        response,
        csp_mode=global_config.csp_mode,
        cache_private=True,
    )
    return response


# endregion


# region Auth
if global_config.auth_type not in [AuthType.NONE, AuthType.READ_ONLY]:

    @router.post("/api/token", response_model=Token)
    def token(data: Login, request: Request, response: Response):
        client_ip = get_client_ip(request)
        is_allowed, retry_after = login_rate_limiter.check(
            client_ip, data.username
        )
        if not is_allowed:
            logger.warning(
                "Rate-limited login attempt for username '%s' from '%s'.",
                data.username,
                client_ip,
            )
            raise HTTPException(
                status_code=429,
                detail=api_messages.login_rate_limited,
                headers={"Retry-After": str(retry_after or 1)},
            )
        try:
            token_response = auth.login(data)
            logger.info(
                "Successful login for username '%s' from '%s'.",
                data.username,
                client_ip,
            )
            if global_config.set_httponly_auth_cookie:
                response.set_cookie(
                    key="token",
                    value=token_response.access_token,
                    httponly=True,
                    samesite="strict",
                    secure=request_uses_https(request),
                    max_age=getattr(auth, "session_expiry_days", 30) * 86400,
                    path=(global_config.path_prefix or "/"),
                )
            return token_response
        except ValueError:
            login_rate_limiter.register_failure(client_ip, data.username)
            logger.warning(
                "Failed login for username '%s' from '%s'.",
                data.username,
                client_ip,
            )
            raise HTTPException(
                status_code=401, detail=api_messages.login_failed
            )

    @router.post("/api/logout", response_model=None)
    def logout(response: Response):
        response.delete_cookie(
            key="token",
            path=(global_config.path_prefix or "/"),
            samesite="strict",
        )
        response.status_code = 204
        return response


@router.get("/api/auth-check", response_model=AuthPrincipal)
def auth_check(principal: AuthPrincipal = Depends(get_current_principal)):
    return principal


# endregion


# region Notes
@router.get("/api/notes/export-all")
def export_all_notes(
    group: str | None = Query(default=None),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    return access_service.export_all_notes(principal, group)


@router.get("/api/notes/{title}", response_model=Note)
def get_note(
    title: str,
    group: str | None = Query(default=None),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    try:
        return access_service.get_note(principal, title, group)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=api_messages.invalid_note_title
        )
    except FileNotFoundError:
        raise HTTPException(404, api_messages.note_not_found)


if global_config.auth_type != AuthType.READ_ONLY:

    @router.post("/api/notes", response_model=Note)
    def post_note(
        note: NoteCreate,
        group: str | None = Query(default=None),
        principal: AuthPrincipal = Depends(get_current_principal),
    ):
        try:
            return access_service.create_note(principal, note, group)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error) or api_messages.invalid_note_title,
            )
        except FileExistsError:
            raise HTTPException(
                status_code=409, detail=api_messages.note_exists
            )

    @router.patch("/api/notes/{title}", response_model=Note)
    def patch_note(
        title: str,
        data: NoteUpdate,
        group: str | None = Query(default=None),
        principal: AuthPrincipal = Depends(get_current_principal),
    ):
        try:
            return access_service.update_note(principal, title, data, group)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error) or api_messages.invalid_note_title,
            )
        except FileExistsError:
            raise HTTPException(
                status_code=409, detail=api_messages.note_exists
            )
        except FileNotFoundError:
            raise HTTPException(404, api_messages.note_not_found)

    @router.post("/api/notes/{title}/duplicate", response_model=Note)
    def duplicate_note(
        title: str,
        group: str | None = Query(default=None),
        principal: AuthPrincipal = Depends(get_current_principal),
    ):
        try:
            return access_service.duplicate_note(principal, title, group)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error) or api_messages.invalid_note_title,
            )
        except FileNotFoundError:
            raise HTTPException(404, api_messages.note_not_found)

    @router.delete("/api/notes/{title}", response_model=None)
    def delete_note(
        title: str,
        group: str | None = Query(default=None),
        principal: AuthPrincipal = Depends(get_current_principal),
    ):
        try:
            access_service.delete_note(principal, title, group)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=api_messages.invalid_note_title,
            )
        except FileNotFoundError:
            raise HTTPException(404, api_messages.note_not_found)


@router.get("/api/notes/{title}/export")
def export_note(
    title: str,
    group: str | None = Query(default=None),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    try:
        return access_service.export_note(principal, title, group)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error) or api_messages.invalid_note_title,
        )
    except FileNotFoundError:
        raise HTTPException(404, api_messages.note_not_found)


# endregion


# region Search
@router.get("/api/search", response_model=List[SearchResult])
def search(
    term: str,
    sort: Literal["score", "title", "lastModified", "createdAt"] = "score",
    order: Literal["asc", "desc"] = "desc",
    favorites_first: bool = Query(True, alias="favoritesFirst"),
    tag_ids: List[str] = Query(default=[], alias="tagIds"),
    tag_mode: Literal["and", "or"] = Query("and", alias="tagMode"),
    favorite_only: bool = Query(False, alias="favoriteOnly"),
    limit: int = None,
    group: str | None = Query(default=None),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    if sort == "lastModified":
        sort = "last_modified"
    elif sort == "createdAt":
        sort = "created_at"
    return access_service.search_notes(
        principal,
        group=group,
        term=term,
        sort=sort,
        order=order,
        favorites_first=favorites_first,
        tag_ids=tag_ids,
        tag_mode=tag_mode,
        favorite_only=favorite_only,
        limit=limit,
    )


@router.get("/api/tags", response_model=List[Tag])
def get_tags(
    group: str | None = Query(default=None),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    return access_service.get_tags(principal, group)


if global_config.auth_type != AuthType.READ_ONLY:

    @router.post("/api/tags", response_model=Tag)
    def post_tag(
        data: TagCreate,
        group: str | None = Query(default=None),
        principal: AuthPrincipal = Depends(get_current_principal),
    ):
        try:
            return access_service.create_tag(principal, data, group)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error) or api_messages.invalid_tag,
            )
        except FileExistsError:
            raise HTTPException(status_code=409, detail=api_messages.tag_exists)

    @router.patch("/api/tags/{tag_id}", response_model=Tag)
    def patch_tag(
        tag_id: str,
        data: TagUpdate,
        group: str | None = Query(default=None),
        principal: AuthPrincipal = Depends(get_current_principal),
    ):
        try:
            return access_service.update_tag(principal, tag_id, data, group)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error) or api_messages.invalid_tag,
            )
        except FileExistsError:
            raise HTTPException(status_code=409, detail=api_messages.tag_exists)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=api_messages.tag_not_found)

    @router.delete("/api/tags/{tag_id}", response_model=None)
    def delete_tag(
        tag_id: str,
        group: str | None = Query(default=None),
        principal: AuthPrincipal = Depends(get_current_principal),
    ):
        try:
            access_service.delete_tag(principal, tag_id, group)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=api_messages.tag_not_found)


# endregion


# region Admin
@router.get("/api/admin/groups", response_model=List[AdminGroup])
def get_admin_groups(
    principal: AuthPrincipal = Depends(get_current_principal),
):
    return access_service.list_admin_groups(principal)


@router.post("/api/admin/groups", response_model=AdminGroup)
def post_admin_group(
    data: GroupCreate,
    principal: AuthPrincipal = Depends(get_current_principal),
):
    try:
        return access_service.create_group(principal, data)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except FileExistsError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.patch("/api/admin/groups/{group_id}", response_model=AdminGroup)
def patch_admin_group(
    group_id: str,
    data: GroupUpdate,
    principal: AuthPrincipal = Depends(get_current_principal),
):
    try:
        return access_service.update_group(principal, group_id, data)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except FileExistsError as error:
        raise HTTPException(status_code=409, detail=str(error))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Group not found.")


@router.delete("/api/admin/groups/{group_id}", response_model=None)
def delete_admin_group(
    group_id: str,
    principal: AuthPrincipal = Depends(get_current_principal),
):
    try:
        access_service.delete_group(principal, group_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Group not found.")


@router.get("/api/admin/users", response_model=List[AdminUser])
def get_admin_users(
    principal: AuthPrincipal = Depends(get_current_principal),
):
    return access_service.list_admin_users(principal)


@router.post("/api/admin/users", response_model=AdminUser)
def post_admin_user(
    data: UserCreate,
    principal: AuthPrincipal = Depends(get_current_principal),
):
    try:
        return access_service.create_user(principal, data)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except FileExistsError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.patch("/api/admin/users/{username}", response_model=AdminUser)
def patch_admin_user(
    username: str,
    data: UserUpdate,
    principal: AuthPrincipal = Depends(get_current_principal),
):
    try:
        return access_service.update_user(principal, username, data)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="User not found.")


@router.delete("/api/admin/users/{username}", response_model=None)
def delete_admin_user(
    username: str,
    principal: AuthPrincipal = Depends(get_current_principal),
):
    try:
        access_service.delete_user(principal, username)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="User not found.")


# endregion


# region Config
@router.get("/api/config", response_model=GlobalConfigResponseModel)
def get_config(request: Request):
    principal = get_optional_principal(request)
    available_groups = []
    role = "guest"
    default_group_id = None
    show_legacy_library = False
    if principal is not None:
        available_groups = [
            {"id": group.id, "name": group.name}
            for group in access_service.list_available_groups(principal)
        ]
        role = principal.role
        default_group_id = access_service.default_group_id(principal)
        show_legacy_library = principal.is_admin
    return GlobalConfigResponseModel(
        auth_type=global_config.auth_type,
        quick_access_hide=global_config.quick_access_hide,
        quick_access_title=global_config.quick_access_title,
        quick_access_term=global_config.quick_access_term,
        quick_access_sort=global_config.quick_access_sort,
        quick_access_limit=global_config.quick_access_limit,
        role=role,
        available_groups=available_groups,
        default_group_id=default_group_id,
        show_legacy_library=show_legacy_library,
        http_only_auth_cookie=global_config.set_httponly_auth_cookie,
    )


# endregion


# region Attachments
@router.get("/api/attachments/{filename}")
@router.get("/attachments/{filename}", include_in_schema=False)
def get_attachment(
    filename: str,
    group: str | None = Query(default=None),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    try:
        return access_service.get_attachment(principal, filename, group)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=api_messages.invalid_attachment_filename,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail=api_messages.attachment_not_found
        )


if global_config.auth_type != AuthType.READ_ONLY:

    @router.post("/api/attachments", response_model=AttachmentCreateResponse)
    def post_attachment(
        file: UploadFile,
        group: str | None = Query(default=None),
        principal: AuthPrincipal = Depends(get_current_principal),
    ):
        try:
            return access_service.create_attachment(principal, file, group)
        except AttachmentTooLargeError:
            raise HTTPException(
                status_code=413,
                detail=api_messages.attachment_too_large,
            )
        except AttachmentTypeBlockedError:
            raise HTTPException(
                status_code=400,
                detail=api_messages.attachment_type_blocked,
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=api_messages.invalid_attachment_filename,
            )
        except FileExistsError:
            raise HTTPException(409, api_messages.attachment_exists)


# endregion


# region Healthcheck
@router.get("/health")
def healthcheck() -> str:
    return "OK"


# endregion

app.include_router(router, prefix=global_config.path_prefix)
app.mount(
    global_config.path_prefix,
    StaticFiles(directory="client/dist"),
    name="dist",
)
