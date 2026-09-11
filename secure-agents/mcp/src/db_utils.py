"""
Database utilities for MongoDB connection management.

This module provides a MongoDB connection manager with connection pooling,
error handling, and MongoDB specific configurations.
"""

import logging
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

from pymongo import MongoClient

from config import Config, get_config
from jwt_verifier import decode_jwt_token
from vault_client import get_mongodb_credentials

# Configure logging level from .env (default to INFO)
LOG_LEVEL = get_config().log_level.upper()
# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.getLevelNamesMapping().get(LOG_LEVEL))


class DatabaseManager:
    """
    MongoDB connection manager.

    Provides connection management, connection pooling, and database operations
    for MongoDB with proper SSL configuration and error handling.
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the database manager.

        Args:
            config: Configuration object with database settings
        """
        self.config = config or Config()
        self._connections: Dict[str, Tuple[MongoClient, float, float]] = {}

    def get_mongo_client(
        self, jwt_token: str, x_correlation_id: str, operation: str = "read"
    ) -> MongoClient:
        """
        Establish connection to MongoDB with explicit operation permissions.

        Args:
            jwt_token: JWT token for authentication
            x_correlation_id: Correlation ID for tracking
            operation: Type of operation ("read" or "write")

        Returns:
            MongoClient: Connected MongoDB client

        Raises:
            ConnectionFailure: If connection cannot be established
            ConfigurationError: If configuration is invalid
            ValueError: If operation is not "read" or "write"
        """
        if operation not in ["read", "write"]:
            raise ValueError(
                f"Invalid operation: {operation}. Must be 'read' or 'write'"
            )
        logger.info("=" * 60)
        logger.info("=== GETTING MONGODB CONNECTION ===")
        logger.info("=" * 60)

        try:
            # Decode JWT to get subject claim
            logger.info("Step 1: Decoding JWT token to extract 'sub' claim...")
            logger.info(f"  JWT token length: {len(jwt_token)}")
            logger.info(
                f"  JWT token preview: {jwt_token[:20]}...{jwt_token[-10:]}")

            token_data = decode_jwt_token(jwt_token)
            sub = token_data.get("sub")
            if not sub:
                logger.error("✗ JWT token does not contain 'sub' claim")
                raise ValueError("JWT token does not contain 'sub' claim")

            logger.info(f"✓ Extracted 'sub' claim: {sub}")

            # Create cache key with operation to separate read/write connections
            cache_key = f"{sub}:{operation}"

            # Check if we have a cached connection (only if caching is enabled)
            logger.info(
                f"Step 2: Checking for cached MongoDB connection (operation: {operation})..."
            )
            logger.info(f"  Cache enabled: {self.config.vault_cache_enabled}")

            if self.config.vault_cache_enabled and cache_key in self._connections:
                client, creation_time, valid_until = self._connections[cache_key]
                logger.info(
                    f"  Found cached connection for user: {sub} (operation: {operation})"
                )
                logger.info(
                    f"  Connection created at: {datetime.fromtimestamp(creation_time).strftime('%Y-%m-%d %H:%M:%S')}"
                )
                logger.info(
                    f"  Valid until: {datetime.fromtimestamp(valid_until).strftime('%Y-%m-%d %H:%M:%S')}"
                )

                # Check if connection has expired is about to expire
                if time.time() + 10 < valid_until:
                    logger.info(
                        "  Connection still valid, checking if active...")

                    # Check if the client is still connected
                    try:
                        # The 'ping' command is a lightweight way to check connection health
                        client.admin.command("ping")
                        logger.info(
                            "✓ Cached connection is active and healthy")
                        logger.info("=" * 60)
                        return client
                    except Exception as e:
                        logger.warning(
                            f"✗ Cached connection is no longer active: {e}")
                        logger.info(
                            "  Closing stale connection and reconnecting...")
                        self.close_connection(cache_key)
                else:
                    # Connection expired, clean up
                    logger.info("✗ Connection expired, cleaning up...")
                    self.close_connection(cache_key)
            else:
                logger.info(
                    f"  No cached connection found for user: {sub} (operation: {operation})"
                )

            # Get fresh credentials from Vault with explicit operation
            logger.info(
                f"Step 3: Getting fresh credentials from Vault for '{operation}' operation..."
            )
            credentials = get_mongodb_credentials(
                jwt_token, x_correlation_id, operation
            )
            config = get_config()
            logger.info("✓ Received credentials from Vault")
            logger.info(f"  Correlation ID: {x_correlation_id}")
            logger.info(f"  Dynamic username: {credentials['username']}")
            logger.debug(
                f"  Dynamic password: {credentials['password'][:5]}...{credentials['password'][-5:]}"
            )
            logger.info(
                f"  Database role: {credentials['user_metadata']['database_role']}"
            )
            ttl_timestamp = datetime.fromtimestamp(
                credentials["credentials_ttl"]
            ).strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                f"  Credentials valid until: {ttl_timestamp} ({credentials['credentials_ttl']} epoch)"
            )

            connection_string = (
                f"mongodb://{credentials['username']}:{credentials['password']}"
                f"@{config.db_host}:{config.db_port}"
                f"/{config.db_name}?authSource=admin&retryWrites=false"
            )

            client_options = {
                "maxIdleTimeMS": 30000,  # 30 seconds
                "waitQueueTimeoutMS": 10000,  # 10 seconds
                "directConnection": True,
            }

            # # Configure SSL for MongoDB if enabled
            # if self.config.use_ssl:
            #     client_options["tls"] = True
            #     client_options["tlsCAFile"] = self.config.ssl_ca_cert_path

            logger.info("Step 4: Creating MongoDB connection...")
            client = MongoClient(connection_string, **client_options)
            logger.info("✓ MongoDB connection established")

            # Cache the connection with its creation time and TTL (only if caching is enabled)
            if self.config.vault_cache_enabled:
                self._connections[cache_key] = (
                    client,
                    time.time(),
                    credentials["credentials_ttl"],
                )
                logger.info(
                    f"✓ Cached connection for user: {sub} (operation: {operation})"
                )
                logger.info(
                    f"  Total cached connections: {len(self._connections)}")
            else:
                logger.info(
                    "✓ Connection caching is disabled (vault_cache_enabled=False)"
                )

            logger.info("=" * 60)
            return client

        except Exception as e:
            logger.error("=" * 60)
            logger.error("✗ FAILED TO GET MONGODB CONNECTION")
            logger.error(f"  Error: {str(e)}")
            logger.error("=" * 60)
            raise RuntimeError(f"Failed to get MongoDB connection: {str(e)}")

    def close_connection(self, cache_key: str) -> None:
        """Close and remove a specific connection"""
        if cache_key in self._connections:
            client, _, _ = self._connections[cache_key]
            client.close()
            del self._connections[cache_key]

    def close_all_connections(self) -> None:
        """Close all connections"""
        for cache_key in list(self._connections.keys()):
            self.close_connection(cache_key)


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """
    Get global database manager instance.

    Returns:
        DatabaseManager: Global database manager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
