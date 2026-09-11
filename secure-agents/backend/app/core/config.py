import secrets
import warnings
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    computed_field,
    model_validator,
)
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl | Literal["*"]] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    PROJECT_NAME: str
    POSTGRES_SERVER: str | None = None
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> MultiHostUrl | None:
        if not self.POSTGRES_SERVER or not self.POSTGRES_USER:
            return None
        return MultiHostUrl.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    # IBM Verify OAuth Configuration
    IBM_VERIFY_CLIENT_ID: str = ""
    IBM_VERIFY_CLIENT_SECRET: str = ""
    IBM_VERIFY_TENANT_ID: str = ""
    IBM_VERIFY_SCOPE: str = "openid profile email"
    IBM_VERIFY_REDIRECT_URI: str = "http://localhost:5173/oauth2callback"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def IBM_VERIFY_BASE_URL(self) -> str:
        if self.IBM_VERIFY_TENANT_ID:
            return f"https://{self.IBM_VERIFY_TENANT_ID}/oauth2"
        return ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def IBM_VERIFY_AUTHORIZE_URL(self) -> str:
        if self.IBM_VERIFY_BASE_URL:
            return f"{self.IBM_VERIFY_BASE_URL}/authorize"
        return ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def IBM_VERIFY_TOKEN_URL(self) -> str:
        if self.IBM_VERIFY_BASE_URL:
            return f"{self.IBM_VERIFY_BASE_URL}/token"
        return ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def IBM_VERIFY_REVOKE_URL(self) -> str:
        if self.IBM_VERIFY_BASE_URL:
            return f"{self.IBM_VERIFY_BASE_URL}/revoke"
        return ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def IBM_VERIFY_LOGOUT_URL(self) -> str:
        if self.IBM_VERIFY_TENANT_ID:
            return f"https://{self.IBM_VERIFY_TENANT_ID}/oidc/endpoint/default/logout"
        return ""

    # Watson Orchestrate Configuration (using VITE_ prefix for frontend compatibility)
    VITE_WXO_ORCHESTRATION_ID: str = ""
    VITE_WXO_HOST_URL: str = ""
    VITE_WXO_DEPLOYMENT_PLATFORM: str = "ibmcloud"
    VITE_WXO_CRN: str = ""
    VITE_WXO_AGENT_ID: str = ""
    VITE_WXO_AGENT_ENVIRONMENT_ID: str = ""
    VITE_WXO_TENANT_ID: str = ""

    # RSA Keys for Watson Orchestrate integration (base64 encoded PEM format)
    # YOUR private key - used to SIGN JWT tokens sent to Watson Orchestrate
    JWT_PRIVATE_KEY_BASE64: str = ""
    # WATSON ORCHESTRATE's public key - used to ENCRYPT user payload that WXO will decrypt
    WXO_PUBLIC_KEY_BASE64: str = ""

    # Aliases for backend use (without VITE_ prefix)
    @computed_field  # type: ignore[prop-decorator]
    @property
    def WXO_ORCHESTRATION_ID(self) -> str:
        return self.VITE_WXO_ORCHESTRATION_ID

    @computed_field  # type: ignore[prop-decorator]
    @property
    def WXO_HOST_URL(self) -> str:
        return self.VITE_WXO_HOST_URL

    @computed_field  # type: ignore[prop-decorator]
    @property
    def WXO_DEPLOYMENT_PLATFORM(self) -> str:
        return self.VITE_WXO_DEPLOYMENT_PLATFORM

    @computed_field  # type: ignore[prop-decorator]
    @property
    def WXO_CRN(self) -> str:
        return self.VITE_WXO_CRN

    @computed_field  # type: ignore[prop-decorator]
    @property
    def WXO_AGENT_ID(self) -> str:
        return self.VITE_WXO_AGENT_ID

    @computed_field  # type: ignore[prop-decorator]
    @property
    def WXO_AGENT_ENVIRONMENT_ID(self) -> str:
        return self.VITE_WXO_AGENT_ENVIRONMENT_ID

    @computed_field  # type: ignore[prop-decorator]
    @property
    def WXO_TENANT_ID(self) -> str:
        return self.VITE_WXO_TENANT_ID

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        # Only check POSTGRES_PASSWORD if database is configured
        if self.POSTGRES_SERVER and self.POSTGRES_USER:
            self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)

        return self


settings = Settings()  # type: ignore
