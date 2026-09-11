"""
FastMCP server for MongoDB product operations.

Uses FastMCP's built-in JWTVerifier for token verification and
get_access_token() / get_http_headers() dependency injection
to access the verified token and headers in tool handlers.

No custom middleware needed — FastMCP handles it.
"""

import asyncio
import logging
import os
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers, get_access_token

from config import get_config
from db_utils import get_db_manager
from models import Product, ProductListResponse, ProductResponse
from product_service import ProductService

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------
config = get_config()

LOG_LEVEL = config.log_level.upper()
logging.basicConfig(
    level=logging.getLevelNamesMapping().get(LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.getLevelNamesMapping().get(LOG_LEVEL, logging.INFO))

# Enable DEBUG for FastMCP internals (auth flow visibility)
for _name in ["fastmcp", "fastmcp.server", "fastmcp.server.auth"]:
    logging.getLogger(_name).setLevel(logging.DEBUG)


# ---------------------------------------------------------------------------
# JWT Verifier — FastMCP's built-in auth
# ---------------------------------------------------------------------------
def _create_jwt_verifier():
    """
    Create a JWTVerifier using environment variables.

    FastMCP's JWTVerifier handles:
    - Fetching public keys from JWKS endpoint (with caching)
    - Verifying token signature, expiration, issuer, audience
    - Making the verified AccessToken available via get_access_token()
    """
    jwks_uri = os.environ.get("JWKS_URI")
    jwt_issuer = os.environ.get("JWT_ISSUER")
    jwt_audience = os.environ.get("JWT_AUDIENCE")

    if not jwks_uri:
        logger.warning(
            "JWKS_URI not set — JWT verification disabled. "
            "Set JWKS_URI, JWT_ISSUER, JWT_AUDIENCE env vars to enable."
        )
        return None

    from fastmcp.server.auth.providers.jwt import JWTVerifier

    logger.info(
        f"JWT verification enabled: jwks_uri={jwks_uri}, issuer={jwt_issuer}, audience={jwt_audience}"
    )

    return JWTVerifier(
        jwks_uri=jwks_uri,
        issuer=jwt_issuer,
        audience=jwt_audience,
    )


# ---------------------------------------------------------------------------
# FastMCP Server
# ---------------------------------------------------------------------------
jwt_verifier = _create_jwt_verifier()

mcp = FastMCP(
    "products-mcp",
    version="1.0.0",
    auth=jwt_verifier,  # FastMCP verifies JWT before any tool call
)


# ---------------------------------------------------------------------------
# Health Check Server
# ---------------------------------------------------------------------------
health_app = FastAPI(title="MCP Health Check")


@health_app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes/OpenShift probes."""
    return {"status": "healthy", "service": "products-mcp", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_correlation_id() -> str:
    """Extract x-correlation-id from current request headers."""
    try:
        headers = get_http_headers()
        return headers.get("x-correlation-id", "no-correlation-id")
    except Exception:
        return "no-correlation-id"


def _get_jwt_token() -> Optional[str]:
    """
    Get the raw JWT token string from the verified AccessToken.

    FastMCP's get_access_token() returns the AccessToken object
    that was verified by JWTVerifier. We extract the raw token
    to pass to ProductService / db_utils.
    """
    try:
        access_token = get_access_token()
        if access_token is None:
            logger.warning("No access token available (auth disabled or no token sent)")
            return None

        logger.debug(
            f"Verified JWT — client_id={access_token.client_id}, scopes={access_token.scopes}"
        )

        # Try to get the raw token string from AccessToken
        if hasattr(access_token, "token"):
            return access_token.token

        # Fallback: extract from Authorization header
        headers = get_http_headers(include_all=True)
        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]

        return None
    except Exception as e:
        logger.debug(f"Could not get access token via get_access_token(): {e}")
        # Fallback: try raw header extraction
        try:
            headers = get_http_headers(include_all=True)
            auth_header = headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                return auth_header[7:]
        except Exception:
            pass
        return None


async def _create_product_service() -> ProductService:
    """Create a ProductService with JWT token and correlation ID from current request."""
    jwt_token = _get_jwt_token()
    x_correlation_id = _get_correlation_id()
    return ProductService(jwt_token=jwt_token, x_correlation_id=x_correlation_id)


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_products(limit: Optional[int] = 10) -> ProductListResponse:
    """
    List all products from the database.

    This tool retrieves all products stored. You can optionally
    limit the number of results returned. Use this tool when you need to see
    all available products or get a general overview of the product catalog.

    Example response:
        {
            "success": true,
            "message": "Product retrieved successfully",
            "products": [
                {
                    "id": "P12345",
                    "name": "Ultra Comfort Running Shoes",
                    "price": 89.99
                }
            ],
            "count": 1
        }

    Args:
        limit: Maximum number of products to return. Default is 10, maximum is 100.

    Returns:
        ProductListResponse with success status, message, products list, and count.
    """
    x_correlation_id = _get_correlation_id()
    logger.info(f"{x_correlation_id} - list_products(limit={limit})")

    try:
        product_service = await _create_product_service()
        products = await product_service.list_all_products(limit)

        return ProductListResponse(
            success=True,
            message=f"Successfully retrieved {len(products)} products",
            products=products,
            count=len(products),
        )
    except Exception as e:
        logger.error(f"{x_correlation_id} - Error listing products: {e}")
        return ProductListResponse(
            success=False,
            message=f"Failed to list products: {str(e)}",
            products=[],
            count=0,
        )


@mcp.tool()
async def search_products(name: str, exact_match: bool = False) -> ProductListResponse:
    """
    Search for products by name.

    This tool searches for products based on their name. It supports both exact
    and partial matching with case-insensitive search.

    Args:
        name: Product name to search for.
        exact_match: If True, search for exact match; otherwise, partial match. Default is False.

    Returns:
        ProductListResponse with success status, message, products list, and count.
    """
    x_correlation_id = _get_correlation_id()
    logger.info(
        f"{x_correlation_id} - search_products(name='{name}', exact={exact_match})"
    )

    try:
        product_service = await _create_product_service()
        products = await product_service.search_by_name(
            name=name, exact_match=exact_match
        )

        match_type = "exact" if exact_match else "partial"
        message = (
            f"Found {len(products)} products matching '{name}' ({match_type} match)"
        )

        return ProductListResponse(
            success=True, message=message, products=products, count=len(products)
        )
    except ValueError as e:
        logger.error(f"{x_correlation_id} - Invalid search parameters: {e}")
        return ProductListResponse(
            success=False,
            message=f"Invalid search parameters: {str(e)}",
            products=[],
            count=0,
        )
    except Exception as e:
        logger.error(f"{x_correlation_id} - Error searching products: {e}")
        return ProductListResponse(
            success=False,
            message=f"Failed to search products: {str(e)}",
            products=[],
            count=0,
        )


@mcp.tool()
async def create_product(product: Product) -> ProductResponse:
    """
    Create a new product.

    Product names must be unique (case-insensitive). The product will be assigned
    an auto-generated ID.

    Args:
        product: A JSON object with 'name' (str) and 'price' (float).

    Returns:
        ProductResponse with success status, message, and created product data.
    """
    x_correlation_id = _get_correlation_id()
    logger.info(
        f"{x_correlation_id} - create_product(name='{product.name}', price={product.price})"
    )

    try:
        product_service = await _create_product_service()
        product_data = Product(name=product.name, price=product.price)
        created_product = await product_service.create_product(product_data)

        return ProductResponse(
            success=True,
            message=f"Successfully created product '{created_product.name}' with ID {created_product.id}",
            data={
                "id": str(created_product.id),
                "name": created_product.name,
                "price": created_product.price,
            },
        )
    except Exception as e:
        error_msg = str(e)
        if "already exists" in error_msg.lower():
            logger.error(f"{x_correlation_id} - Product name conflict: {e}")
            return ProductResponse(
                success=False, message=f"Product name already exists: {str(e)}"
            )
        else:
            logger.error(f"{x_correlation_id} - Error creating product: {e}")
            return ProductResponse(
                success=False, message=f"Failed to create product: {str(e)}"
            )


@mcp.tool()
async def update_product(product_id: str, product: Product) -> ProductResponse:
    """
    Update an existing product.

    Product names must remain unique (case-insensitive).

    Args:
        product_id: Product ID to update.
        product: A JSON object with 'name' (str) and 'price' (float).

    Returns:
        ProductResponse with success status and message.
    """
    x_correlation_id = _get_correlation_id()
    logger.info(
        f"{x_correlation_id} - update_product(id='{product_id}', name='{product.name}', price={product.price})"
    )

    try:
        product_service = await _create_product_service()

        if not product_id or not product_id.strip():
            return ProductResponse(
                success=False, message="Product ID is required for updates"
            )
        if not product.name or not product.name.strip():
            return ProductResponse(
                success=False, message="Product name is required and cannot be empty"
            )
        if product.price is None or product.price < 0:
            return ProductResponse(
                success=False, message="Product price must be a non-negative number"
            )

        updated_product = await product_service.update_product_by_id(
            product_id=product_id, update_product=product
        )

        if updated_product is None:
            return ProductResponse(success=False, message="Product not found")

        return ProductResponse(success=True, message="Product updated successfully")

    except ValueError as e:
        logger.error(f"{x_correlation_id} - Invalid product ID or data: {e}")
        return ProductResponse(
            success=False, message=f"Invalid input parameters: {str(e)}"
        )
    except Exception as e:
        error_msg = str(e)
        if "already exists" in error_msg.lower():
            logger.error(
                f"{x_correlation_id} - Product name conflict during update: {e}"
            )
            return ProductResponse(
                success=False, message=f"Product name {product.name} already exists"
            )
        else:
            logger.error(f"{x_correlation_id} - Error updating product: {e}")
            return ProductResponse(
                success=False, message=f"Failed to update product: {str(e)}"
            )


@mcp.tool()
async def delete_product(product_id: str) -> ProductResponse:
    """
    Delete a product by ID. The operation cannot be undone.

    Args:
        product_id: Product ID to delete.

    Returns:
        ProductResponse with success status and message.
    """
    x_correlation_id = _get_correlation_id()
    logger.info(f"{x_correlation_id} - delete_product(id='{product_id}')")

    try:
        product_service = await _create_product_service()
        deleted = await product_service.delete_product_by_id(product_id)

        if deleted:
            return ProductResponse(
                success=True,
                message=f"Successfully deleted product with ID '{product_id}'",
            )
        else:
            return ProductResponse(
                success=False, message=f"Product with ID '{product_id}' not found"
            )
    except ValueError as e:
        logger.error(f"{x_correlation_id} - Invalid product ID: {e}")
        return ProductResponse(success=False, message=f"Invalid product ID: {str(e)}")
    except Exception as e:
        logger.error(f"{x_correlation_id} - Error deleting product: {e}")
        return ProductResponse(
            success=False, message=f"Failed to delete product: {str(e)}"
        )


@mcp.tool()
async def sort_products_by_price(
    ascending: bool = True, limit: Optional[int] = 10
) -> ProductListResponse:
    """
    Sort products by price (ascending or descending).

    Args:
        ascending: If True, sort low to high; otherwise high to low. Default is True.
        limit: Maximum number of products to return. Default is 10.

    Returns:
        ProductListResponse with products sorted by price.
    """
    x_correlation_id = _get_correlation_id()
    logger.info(
        f"{x_correlation_id} - sort_products_by_price(ascending={ascending}, limit={limit})"
    )

    try:
        product_service = await _create_product_service()
        products = await product_service.sort_products_by_price(
            ascending=ascending, limit=limit
        )

        sort_direction = (
            "ascending (low to high)" if ascending else "descending (high to low)"
        )
        message = f"Successfully retrieved {len(products)} products sorted by price ({sort_direction})"

        return ProductListResponse(
            success=True, message=message, products=products, count=len(products)
        )
    except Exception as e:
        logger.error(f"{x_correlation_id} - Error sorting products: {e}")
        return ProductListResponse(
            success=False,
            message=f"Failed to sort products by price: {str(e)}",
            products=[],
            count=0,
        )


# ---------------------------------------------------------------------------
# Server Startup
# ---------------------------------------------------------------------------


async def run_health_server():
    """Run the FastAPI health check server on port 8002."""
    health_config = uvicorn.Config(
        health_app, host="0.0.0.0", port=8002, log_level="info"
    )
    health_server = uvicorn.Server(health_config)
    await health_server.serve()


async def run_mcp_server():
    """Run the MCP server on SSE transport."""
    await mcp.run_async(
        transport="sse",
        host=config.server_host,
        port=config.server_port,
    )


async def main():
    """Run both the MCP server and health check server in parallel."""
    try:
        logger.info("=" * 60)
        logger.info("Starting Products MCP Server (SSE transport)")
        logger.info(f"Server config: {config.get_server_info()}")
        logger.info(f"JWT auth: {'enabled' if jwt_verifier else 'DISABLED'}")
        logger.info("Health check: http://0.0.0.0:8002/health")
        logger.info(f"MCP SSE: http://{config.server_host}:{config.server_port}/sse")
        logger.info("=" * 60)

        mcp_task = asyncio.create_task(run_mcp_server())
        health_task = asyncio.create_task(run_health_server())

        await asyncio.gather(mcp_task, health_task)

    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise
    finally:
        get_db_manager().close_all_connections()
        logger.info("Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
