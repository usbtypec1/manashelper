import hmac

from aiohttp import web
from aiohttp.typedefs import Handler
from pydantic import BaseModel, Field, ValidationError

from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.i18n.service import TextCatalogService
from manashelper.platform.web.auth import COOKIE_NAME, AdminAuthService, AuthenticationError, ForbiddenError, web_origin
from manashelper.platform.web.keys import (
    ADMIN_KEY,
    AUTH_TOKEN_KEY,
    BEARER_KEY,
    CONTAINER_KEY,
    REQUEST_CONTAINER_KEY,
    SETTINGS_KEY,
)
from ui_flows.domain.contracts import ContractIssue


class RequestContractError(Exception):
    def __init__(self, issues: list[ContractIssue]) -> None:
        self.issues = issues


class Pagination(BaseModel):
    cursor: str | None = Field(default=None, max_length=256)
    limit: int = Field(default=50, ge=1, le=100)


def validate[Model: BaseModel](model: type[Model], value: object, location: str) -> Model:
    try:
        return model.model_validate(value)
    except ValidationError as error:
        raise RequestContractError(
            [
                ContractIssue(
                    code="schema_" + item["type"],
                    path="/" + "/".join([location, *(str(part) for part in item["loc"])]),
                    message="Value does not match the contract: " + item["type"],
                )
                for item in error.errors()
            ]
        ) from error


async def body[Model: BaseModel](request: web.Request, model: type[Model]) -> Model:
    if "Content-Type" in request.headers and not (
        request.content_type == "application/json"
        or (request.content_type.startswith("application/") and request.content_type.endswith("+json"))
    ):
        raise RequestContractError(
            [ContractIssue(code="schema_model_attributes_type", path="/body", message="A JSON body is required")]
        )
    try:
        value = await request.json()
    except (ValueError, UnicodeDecodeError) as error:
        raise RequestContractError(
            [ContractIssue(code="schema_json_invalid", path="/body", message="A JSON body is required")]
        ) from error
    return validate(model, value, "body")


def pagination(request: web.Request) -> Pagination:
    return validate(Pagination, dict(request.query), "query")


class IntegerPath(BaseModel):
    value: int


def path_integer(request: web.Request, name: str) -> int:
    return validate(IntegerPath, {"value": request.match_info[name]}, "path/" + name).value


def response(value: BaseModel, status: int = 200) -> web.Response:
    return web.json_response(value.model_dump(mode="json"), status=status)


@web.middleware
async def admin_scope(request: web.Request, handler: Handler) -> web.StreamResponse:
    if not (request.match_info.route.name or "").startswith("admin."):
        return await handler(request)
    async with request.app[CONTAINER_KEY]() as scope:
        request[REQUEST_CONTAINER_KEY] = scope
        auth = await scope.get(AdminAuthService)
        mutation = request.method not in {"GET", "HEAD"}
        if mutation and request.headers.get("Origin") != web_origin(request.app[SETTINGS_KEY]):
            raise ForbiddenError("Same-origin requests are required")
        if request.path not in {"/admin/api/v1/auth/exchange", "/admin/api/v1/auth/telegram"}:
            authorization = request.headers.get("Authorization")
            bearer = authorization is not None
            if bearer:
                scheme, _, token = (authorization or "").partition(" ")
                if scheme.lower() != "bearer" or not token:
                    raise AuthenticationError("Administrative bearer session required")
            else:
                token = request.cookies.get(COOKIE_NAME, "")
            request[ADMIN_KEY] = await auth.authenticate(token, bearer=bearer)
            request[AUTH_TOKEN_KEY], request[BEARER_KEY] = token, bearer
            if mutation and not bearer:
                expected = auth.csrf(token)
                provided = request.headers.get("X-CSRF-Token", "")
                if not hmac.compare_digest(expected.encode(), provided.encode()):
                    raise ForbiddenError("CSRF token is invalid")
        # Exit (including commit) before aiohttp sends this response or cookies.
        # Exceptions escape the scope to the outer HTTP error mapper.
        if request.path.startswith("/admin/api/v1/auth/"):
            return await handler(request)
        snapshot = await (await scope.get(TextCatalogService)).current()
        with i18n.use_catalog(snapshot):
            return await handler(request)
