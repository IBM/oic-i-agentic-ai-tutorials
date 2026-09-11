# Products MCP Server

A FastMCP server for managing product operations with MongoDB. This server provides comprehensive CRUD operations, search functionality, and price-based sorting for products stored in MongoDB.

## Features

- **Complete CRUD Operations**: Create, read, update, and delete products
- **Advanced Search**: Search products by name with exact or partial matching
- **Price Sorting**: Sort products by price in ascending or descending order
- **MongoDB Integration**: Optimized for MongoDB
- **Connection Pooling**: Efficient database connection management
- **Comprehensive Error Handling**: Detailed error messages and logging
- **Data Validation**: Pydantic models for robust data validation
- **Structured Responses**: Consistent API responses with success/error status

## Prerequisites

- Python 3.12.8 or higher
- Access to MongoDB server
- uv package manager

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd products-mcp
```

2. Install dependencies using uv:
```bash
uv sync
```

3. Set up environment variables:
```bash
cp .env.example .env
```

4. Edit `.env` file with your MongoDB configuration:
```env
DB_HOST=localhost
DB_PORT=27017
DB_NAME=products_db
COLLECTION_NAME=products
```

## Configuration

The server can be configured through environment variables or by modifying the `config.py` file:

### Database Configuration
- `DB_HOST`: MongoDB endpoint
- `DB_PORT`: Database port (default: 27017)
- `DB_NAME`: Database name (default: products_db)
- `COLLECTION_NAME`: Collection name (default: products)

### Server Configuration
- `SERVER_HOST`: Server host (default: localhost)
- `SERVER_PORT`: Server port (default: 8000)
- `MAX_RESULTS`: Maximum results per query (default: 100)

### Vault Configuration
- `VAULT_ADDR`: Vault server address (e.g., http://localhost:8200)
- `VAULT_CACHE_ENABLED`: Enable credentials caching (default: false)
  - **Security Note**: When disabled (default), every database operation requires a fresh Vault authentication, ensuring complete audit trails and immediate token revocation. Enable caching only if performance is critical and you understand the security implications:
    - Reduced audit trail visibility (cached operations don't appear in Vault logs)
    - Delayed token revocation (revoked tokens may still work until cache expires)
    - Policy changes don't take effect immediately

### JWT Configuration
- `JWKS_URI`: JWKS endpoint for JWT verification
- `JWT_ISSUER`: Expected JWT issuer
- `JWT_AUDIENCE`: Expected JWT audience (Client ID)

## Usage

### Starting the Server

```bash
# Using uv
uv run python main.py

# Or activate the virtual environment first
source .venv/bin/activate  # On Unix/macOS
# .venv\\Scripts\\activate  # On Windows
python main.py
```

### Available MCP Tools

The server provides the following MCP tools:

#### 1. `list_products`
Retrieve all products from the database.

**Arguments:**
- `limit` (optional): Maximum number of products to return (1-100)

**Example:**
```json
{
  "limit": 50
}
```

#### 2. `search_products`
Search for products by name.

**Arguments:**
- `name` (required): Product name to search for
- `exact_match` (optional): Use exact matching (default: false)

**Example:**
```json
{
  "name": "laptop",
  "exact_match": false
}
```

#### 3. `create_product`
Create a new product.

**Arguments:**
- `name` (required): Product name (must be unique)
- `price` (required): Product price (must be positive)

**Example:**
```json
{
  "name": "Gaming Laptop",
  "price": 1299.99
}
```

#### 4. `update_product`
Update an existing product.

**Arguments:**
- `product_id` (required): Product ID to update
- `name` (optional): New product name
- `price` (optional): New product price

**Example:**
```json
{
  "product_id": "507f1f77bcf86cd799439011",
  "name": "Updated Gaming Laptop",
  "price": 1199.99
}
```

#### 5. `delete_product`
Delete a product by ID.

**Arguments:**
- `product_id` (required): Product ID to delete

**Example:**
```json
{
  "product_id": "507f1f77bcf86cd799439011"
}
```

#### 6. `get_product`
Get a single product by ID.

**Arguments:**
- `product_id` (required): Product ID to retrieve

**Example:**
```json
{
  "product_id": "507f1f77bcf86cd799439011"
}
```

#### 7. `sort_products_by_price`
Sort products by price.

**Arguments:**
- `ascending` (optional): Sort order (default: true)
- `limit` (optional): Maximum number of products to return

**Example:**
```json
{
  "ascending": false,
  "limit": 20
}
```

#### 8. `get_products_count`
Get the total count of products in the database.

**Example:**
```json
{}
```


## Data Models

### Product
```python
{
  "id": "507f1f77bcf86cd799439011",  # MongoDB ObjectId
  "name": "Product Name",              # String, 1-200 characters
  "price": 99.99                       # Float, must be positive
}
```

### Response Format
All tools return structured responses:

```python
{
  "success": true,                    # Boolean
  "message": "Operation successful",  # String
  "data": { ... },                   # Optional data
  "error": null                      # Error message if failed
}
```

## Error Handling

The server provides comprehensive error handling:

- **Validation Errors**: Invalid input parameters
- **Database Errors**: Connection issues, operation failures
- **Business Logic Errors**: Duplicate names, product not found
- **System Errors**: Unexpected failures with detailed logging


Logs can be output to console or file by setting the `LOG_FILE` environment variable.

## Database Schema

### Products Collection
```javascript
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "name": "Gaming Laptop",
  "price": 1299.99
}
```
