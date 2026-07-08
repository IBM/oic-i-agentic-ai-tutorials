"""
Product service class for CRUD operations.

This module provides the ProductService class that handles all
product-related operations against MongoDB.
"""

import logging
from typing import List, Optional

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.errors import (
    DuplicateKeyError,
    OperationFailure,
)

from config import get_config
from db_utils import get_db_manager
from models import Product, SuccessResponse

# Configure logging
logger = logging.getLogger(__name__)


class ProductService:
    """
    Product service class for managing product operations.

    This class provides methods to perform CRUD operations on products
    stored in MongoDB with proper error handling and validation.
    """

    def __init__(self, jwt_token: str = None, x_correlation_id: str = None):
        """Initialize the product service."""
        self.config = get_config()
        self.jwt_token = jwt_token
        self.x_correlation_id = x_correlation_id

    def _get_collection_for_read(self) -> Collection:
        """
        Get the products collection with explicit read permissions.

        Returns:
            Collection: Products collection instance with read access
        """
        client = get_db_manager().get_mongo_client(
            self.jwt_token, self.x_correlation_id, operation="read"
        )
        # Explicitly access database by name instead of using get_default_database()
        # to avoid potential issues with database name resolution
        return client[self.config.db_name][self.config.collection_name]

    def _get_collection_for_write(self) -> Collection:
        """
        Get the products collection with explicit write permissions.

        Returns:
            Collection: Products collection instance with write access
        """
        client = get_db_manager().get_mongo_client(
            self.jwt_token, self.x_correlation_id, operation="write"
        )
        # Explicitly access database by name instead of using get_default_database()
        # to avoid potential issues with database name resolution
        return client[self.config.db_name][self.config.collection_name]

    async def list_all_products(self, limit: Optional[int] = None) -> List[Product]:
        """
        List all products from the database.

        Args:
            limit: Maximum number of products to return

        Returns:
            List[Product]: List of all products

        Raises:
            OperationFailure: If database operation fails
        """
        try:
            collection = self._get_collection_for_read()
            query_limit = min(limit or self.config.max_results,
                              self.config.max_results)

            logger.info(
                f"{self.x_correlation_id} - Fetching products with limit: {query_limit}"
            )

            cursor = collection.find({}).limit(query_limit)
            products = []

            for doc in cursor:
                try:
                    product = Product(
                        id=str(doc["_id"]),
                        name=doc.get("name"),
                        price=doc.get("price"),
                    )
                    products.append(product)
                except Exception as e:
                    logger.error(
                        f"{self.x_correlation_id} - Error parsing product document {doc.get('_id', 'unknown')}: {e}"
                    )
                    continue

            logger.info(
                f"{self.x_correlation_id} - Retrieved {len(products)} products")
            return products

        except OperationFailure as e:
            logger.error(
                f"{self.x_correlation_id} - Database operation failed while listing products: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"{self.x_correlation_id} - Unexpected error while listing products: {e}"
            )
            raise OperationFailure(f"Failed to list products: {e}")

    async def search_by_name(
        self, name: str, exact_match: bool = False
    ) -> List[Product]:
        """
        Search products by name.

        Args:
            name: Product name to search for
            exact_match: If True, search for exact match; otherwise, partial match

        Returns:
            List[Product]: List of matching products

        Raises:
            OperationFailure: If database operation fails
            ValueError: If name is empty
        """
        if not name or not name.strip():
            raise ValueError("Search name cannot be empty")

        try:
            collection = self._get_collection_for_read()
            name = name.strip()

            if exact_match:
                # Case-insensitive exact match
                query = {"name": {"$regex": f"^{name}$", "$options": "i"}}
                logger.info(
                    f"{self.x_correlation_id} - Searching for exact match: {name}"
                )
            else:
                # Case-insensitive partial match
                query = {"name": {"$regex": name, "$options": "i"}}
                logger.info(
                    f"{self.x_correlation_id} - Searching for partial match: {name}"
                )

            cursor = collection.find(query).limit(self.config.max_results)
            products = []

            for doc in cursor:
                try:
                    product = Product(
                        id=str(doc["_id"]),
                        name=doc.get("name"),
                        price=doc.get("price"),
                    )
                    products.append(product)
                except Exception as e:
                    logger.error(
                        f"{self.x_correlation_id} - Error parsing product document {doc.get('_id', 'unknown')}: {e}"
                    )
                    continue

            logger.info(
                f"{self.x_correlation_id} - Found {len(products)} products matching '{name}'"
            )
            return products

        except OperationFailure as e:
            logger.error(
                f"{self.x_correlation_id} - Database operation failed while searching products: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"{self.x_correlation_id} - Unexpected error while searching products: {e}"
            )
            raise OperationFailure(f"Failed to search products: {e}")

    async def create_product(self, product: Product) -> Product:
        """
        Create a new product.

        Args:
            product: Product data to create (id will be ignored if provided)

        Returns:
            Product: Created product with generated ID

        Raises:
            DuplicateKeyError: If product with same name already exists
            OperationFailure: If database operation fails
        """
        try:
            collection = self._get_collection_for_write()

            # Check if product with same name already exists
            existing = collection.find_one(
                {"name": {"$regex": f"^{product.name}$", "$options": "i"}}
            )
            if existing:
                raise DuplicateKeyError(
                    f"Product with name '{product.name}' already exists"
                )

            logger.info(
                f"{self.x_correlation_id} - Creating product: {product.name}")

            # Insert validated data into MongoDB
            result = collection.insert_one(product.model_dump(exclude={"id"}))

            # Return the created product
            created_product = Product(
                id=str(result.inserted_id),
                name=product.name,
                price=product.price,
            )
            logger.info(
                f"{self.x_correlation_id} - Successfully created product with ID: {created_product.id}"
            )

            return created_product

        except DuplicateKeyError:
            raise Exception(
                f"Product with name '{product.name}' already exists")
        except OperationFailure as e:
            logger.error(
                f"{self.x_correlation_id} - Database operation failed while creating product: {e}"
            )
            raise Exception(f"Failed to create product: {e}")
        except Exception as e:
            logger.error(
                f"{self.x_correlation_id} - Unexpected error while creating product: {e}"
            )
            raise Exception(f"Failed to create product: {e}")

    async def delete_product_by_id(self, product_id: str) -> bool:
        """
        Delete a product by ID.

        Args:
            product_id: Product ID to delete

        Returns:
            bool: True if product was deleted, False if not found

        Raises:
            ValueError: If product_id is invalid
            OperationFailure: If database operation fails
        """
        if not product_id or not product_id.strip():
            raise ValueError("Product ID cannot be empty")

        if not ObjectId.is_valid(product_id):
            raise ValueError(f"Invalid product ID format: {product_id}")

        try:
            collection = self._get_collection_for_write()
            object_id = ObjectId(product_id)

            logger.info(
                f"{self.x_correlation_id} - Deleting product with ID: {product_id}"
            )

            result = collection.delete_one({"_id": object_id})

            if result.deleted_count == 1:
                logger.info(
                    f"{self.x_correlation_id} - Successfully deleted product with ID: {product_id}"
                )
                return True
            else:
                logger.info(
                    f"{self.x_correlation_id} - Product with ID {product_id} not found"
                )
                return False

        except OperationFailure as e:
            logger.error(
                f"{self.x_correlation_id} - Database operation failed while deleting product: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"{self.x_correlation_id} - Unexpected error while deleting product: {e}"
            )
            raise OperationFailure(f"Failed to delete product: {e}")

    async def update_product_by_id(
        self, product_id: str, update_product: Product
    ) -> SuccessResponse:
        """
        Update an exiting product by ID.

        Args:
            product_id: Product ID to update
            update_product: Product data to update (only non-None fields will be updated)

        Returns:
            SuccessResponse: Success message confirming the update

        Raises:
            ValueError: If product_id is invalid
            DuplicateKeyError: If updated name conflicts with existing product
            OperationFailure: If database operation fails
        """
        if not product_id or not product_id.strip():
            raise ValueError("Product ID cannot be empty")

        if not ObjectId.is_valid(product_id):
            raise ValueError(f"Invalid product ID format: {product_id}")

        try:
            collection = self._get_collection_for_write()
            # Update document with validated data
            result = collection.update_one(
                {"_id": ObjectId(product_id)},
                {"$set": update_product.model_dump(exclude={"id"})},
            )

            if not result.modified_count:
                logger.info(
                    f"{self.x_correlation_id} - Product with ID {product_id} not found"
                )
                raise Exception("Product not found")

            logger.info(
                f"{self.x_correlation_id} - Successfully updated product with ID: {product_id}"
            )

            return SuccessResponse(message="Product updated successfully")

        except DuplicateKeyError:
            raise
        except OperationFailure as e:
            logger.error(
                f"{self.x_correlation_id} - Database operation failed while updating product: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"{self.x_correlation_id} - Unexpected error while updating product: {e}"
            )
            raise OperationFailure(f"Failed to update product: {e}")

    async def sort_products_by_price(
        self, ascending: bool = True, limit: Optional[int] = None
    ) -> List[Product]:
        """
        Sort products by price.

        Args:
            ascending: If True, sort ascending; otherwise, descending
            limit: Maximum number of products to return

        Returns:
            List[Product]: List of products sorted by price

        Raises:
            OperationFailure: If database operation fails
        """
        try:
            collection = self._get_collection_for_read()
            query_limit = min(limit or self.config.max_results,
                              self.config.max_results)
            sort_order = ASCENDING if ascending else DESCENDING
            sort_direction = "ascending" if ascending else "descending"

            logger.info(
                f"{self.x_correlation_id} - Sorting products by price ({sort_direction}) with limit: {query_limit}"
            )

            cursor = collection.find({}).sort(
                "price", sort_order).limit(query_limit)
            products = []

            for doc in cursor:
                try:
                    product = Product(
                        id=str(doc["_id"]), name=doc.get("name"), price=doc.get("price")
                    )
                    products.append(product)
                except Exception as e:
                    logger.error(
                        f"{self.x_correlation_id} - Error parsing product document {doc.get('_id', 'unknown')}: {e}"
                    )
                    continue

            logger.info(
                f"{self.x_correlation_id} - Retrieved {len(products)} products sorted by price ({sort_direction})"
            )
            return products

        except OperationFailure as e:
            logger.error(
                f"{self.x_correlation_id} - Database operation failed while sorting products: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"{self.x_correlation_id} - Unexpected error while sorting products: {e}"
            )
            raise OperationFailure(f"Failed to sort products: {e}")

    async def get_product_by_id(self, product_id: str) -> Optional[Product]:
        """
        Get a single product by ID.

        Args:
            product_id: Product ID to retrieve

        Returns:
            Optional[Product]: Product or None if not found

        Raises:
            ValueError: If product_id is invalid
            OperationFailure: If database operation fails
        """
        if not product_id or not product_id.strip():
            raise ValueError("Product ID cannot be empty")

        if not ObjectId.is_valid(product_id):
            raise ValueError(f"Invalid product ID format: {product_id}")

        try:
            collection = self._get_collection_for_read()
            object_id = ObjectId(product_id)

            logger.info(
                f"{self.x_correlation_id} - Fetching product with ID: {product_id}"
            )

            doc = collection.find_one({"_id": object_id})

            if doc is None:
                logger.info(
                    f"{self.x_correlation_id} - Product with ID {product_id} not found"
                )
                return None

            product = Product(
                id=str(doc["_id"]),
                name=doc.get("name"),
                price=doc.get("price"),
            )
            logger.info(
                f"{self.x_correlation_id} - Successfully retrieved product with ID: {product_id}"
            )

            return product

        except OperationFailure as e:
            logger.error(
                f"{self.x_correlation_id} - Database operation failed while fetching product: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"{self.x_correlation_id} - Unexpected error while fetching product: {e}"
            )
            raise OperationFailure(f"Failed to fetch product: {e}")
