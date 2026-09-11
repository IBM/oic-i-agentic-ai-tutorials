"""
Configuration management for the MCP server.

This module handles environment variables and application settings
for MongoDB connection and server configuration.
"""

from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config(BaseSettings):
    """
    Configuration settings for the MCP server.

    All settings can be overridden via environment variables.
    """

    # Database configuration
    db_host: str = Field(default="localhost", description="MongoDB host")
    db_port: int = Field(default=27017, description="MongotDB port")
    db_name: str = Field(default="products_db", description="Database name")
    collection_name: str = Field(
        default="products", description="Products collection name"
    )

    # MCP Server configuration
    server_host: str = Field(
        default="localhost", description="MCP server host")
    server_port: int = Field(default=8000, description="MCP server port")
    server_name: str = Field(default="products-mcp",
                             description="MCP server name")
    max_results: int = Field(
        default=100, description="Maximum number of results to return"
    )

    # JWT validation  settings
    jwt_issuer: str = Field(default=None, description="JWT issuer")
    jwt_audience: str = Field(default=None, description="JWT audience")
    jwks_uri: str = Field(default=None, description="JWT signing keys")
    # entra_tenant_id: str = Field(default=None, description="Entra tenant ID")

    # Vault settings
    vault_addr: str = Field(default=None, description="Vault address")
    vault_cache_enabled: bool = Field(
        default=False, description="Enable caching of Vault credentials (default: disabled for security)"
    )

    # Log level
    log_level: str = Field(default="INFO", description="Logging level")

    @field_validator("db_port", "server_port")
    @classmethod
    def validate_port(cls, v):
        """Validate port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    @field_validator("max_results")
    @classmethod
    def validate_max_results(cls, v):
        """Validate max results is positive."""
        if v <= 0:
            raise ValueError("Max results must be positive")
        return v

    def get_server_info(self) -> dict:
        """
        Get server information dictionary.

        Returns:
            dict: Server information
        """
        return {
            "name": self.server_name,
            "host": self.server_host,
            "port": self.server_port,
        }

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get global configuration instance.

    Returns:
        Config: Global configuration instance
    """
    global _config
    if _config is None:
        _config = Config()
    return _config
