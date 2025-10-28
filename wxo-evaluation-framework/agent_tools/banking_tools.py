from datetime import datetime
import json
from decimal import Decimal, InvalidOperation
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from datetime import datetime, date
import json

# Utility function (reuse your date validator)
def _is_valid_date(date_str: str) -> bool:
    """Check if the provided date string is in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

@tool(name="banking_fetch_account_id", description="Fetch account ID using customer username or customer number.", permission=ToolPermission.ADMIN)
def banking_fetch_account_id(identifier: str) -> str:
    """
    Return the account ID for a given customer identifier (username or customer number).
    :param identifier: customer's username or customer number
    :return: account ID as a string or 'not found'
    """
    # Mock mapping - replace with DB lookup in production
    account_map = {
        "alice": "ACC10001",
        "bob": "ACC10002",
        "cust-555": "ACC10003"
    }
    return account_map.get(identifier, "not found")


@tool(name="banking_retrieve_account_balance", description="Get account balance for a given account ID.", permission=ToolPermission.ADMIN)
def banking_retrieve_account_balance(account_id: str) -> str:
    """
    Retrieve the current balance for an account.
    :param account_id: Account identifier (string)
    :return: Balance as stringified JSON or error message
    """
    mock_balances = {
        "ACC10001": {"currency": "USD", "available": "12500.75", "ledger": "12750.75"},
        "ACC10002": {"currency": "USD", "available": "320.50", "ledger": "320.50"},
        "ACC10003": {"currency": "EUR", "available": "9800.00", "ledger": "9800.00"}
    }

    bal = mock_balances.get(account_id)
    if bal is None:
        return json.dumps({"error": "account not found"})
    return json.dumps(bal)


# @tool(name="banking_list_recent_transactions", description="List recent transactions for an account within optional date range.", permission=ToolPermission.ADMIN)
# def banking_list_recent_transactions(account_id: str, start_date: str = None, end_date: str = None, limit: int = 20) -> str:
#     """
#     Return a list of recent transactions for the account.
#     :param account_id: Account identifier
#     :param start_date: Optional start date YYYY-MM-DD
#     :param end_date: Optional end date YYYY-MM-DD
#     :param limit: Max number of transactions to return
#     :return: JSON-encoded list of transactions or error message
#     """
#     # Validate dates if provided
#     if start_date and not _is_valid_date(start_date):
#         return f"Invalid start_date: {start_date}. Expected YYYY-MM-DD."
#     if end_date and not _is_valid_date(end_date):
#         return f"Invalid end_date: {end_date}. Expected YYYY-MM-DD."

#     # Mock transactions store
#     mock_txns = {
#         "ACC10001": [
#             {"id": "T1001", "date": "2025-10-01", "type": "debit", "amount": "-50.00", "desc": "Coffee Shop"},
#             {"id": "T1002", "date": "2025-09-28", "type": "credit", "amount": "1500.00", "desc": "Payroll"},
#             {"id": "T1003", "date": "2025-09-15", "type": "debit", "amount": "-200.00", "desc": "Electric Bill"},
#         ],
#         "ACC10002": [
#             {"id": "T2001", "date": "2025-10-02", "type": "debit", "amount": "-20.00", "desc": "Lunch"},
#         ],
#         "ACC10003": []
#     }

#     txns = mock_txns.get(account_id)
#     if txns is None:
#         return json.dumps({"error": "account not found"})

#     # Filter by date range if provided
#     def in_range(tx):
#         tx_date = tx["date"]
#         if start_date and tx_date < start_date:
#             return False
#         if end_date and tx_date > end_date:
#             return False
#         return True

#     filtered = [t for t in txns if in_range(t)]
#     # Apply limit
#     result = filtered[:max(0, int(limit))]
#     return json.dumps(result)

@tool(
    name="banking_list_recent_transactions",
    description="List recent transactions for an account within optional date range.",
    permission=ToolPermission.ADMIN
)
def banking_list_recent_transactions(
    account_id: str,
    start_date: str = None,
    end_date: str = None,
    limit: str = "20"  # Default as string for safety with orchestrator inputs
) -> str:
    """
    Return a list of recent transactions for the account.
    Handles missing or invalid 'limit' parameter gracefully.
    """

    # --- Validate and normalize limit ---
    if limit is None or str(limit).strip() == "":
        parsed_limit = 20
    else:
        try:
            parsed_limit = int(limit)
            if parsed_limit < 0:
                parsed_limit = 20
        except (ValueError, TypeError):
            parsed_limit = 20

    # --- Validate dates if provided ---
    if start_date and not _is_valid_date(start_date):
        return json.dumps({"error": f"Invalid start_date: {start_date}. Expected YYYY-MM-DD."})
    if end_date and not _is_valid_date(end_date):
        return json.dumps({"error": f"Invalid end_date: {end_date}. Expected YYYY-MM-DD."})

    # --- Mock transaction data ---
    mock_txns = {
        "ACC10001": [
            {"id": "T1001", "date": "2025-10-01", "type": "debit", "amount": "-50.00", "desc": "Coffee Shop"},
            {"id": "T1002", "date": "2025-09-28", "type": "credit", "amount": "1500.00", "desc": "Payroll"},
            {"id": "T1003", "date": "2025-09-15", "type": "debit", "amount": "-200.00", "desc": "Electric Bill"},
        ],
        "ACC10002": [
            {"id": "T2001", "date": "2025-10-02", "type": "debit", "amount": "-20.00", "desc": "Lunch"},
        ],
        "ACC10003": []
    }

    txns = mock_txns.get(account_id)
    if txns is None:
        return json.dumps({"error": "account not found"})

    # --- Filter by date range ---
    def in_range(tx):
        tx_date = tx["date"]
        if start_date and tx_date < start_date:
            return False
        if end_date and tx_date > end_date:
            return False
        return True

    filtered = [t for t in txns if in_range(t)]

    # --- Apply limit safely ---
    result = filtered[:parsed_limit]
    return json.dumps(result)

@tool(name="banking_get_branch_code", description="Get branch code given branch name or city.", permission=ToolPermission.ADMIN)
def banking_get_branch_code(branch_query: str) -> str:
    """
    Return the branch code for a branch name / city search.
    :param branch_query: branch name or city (case-insensitive)
    :return: branch code or '-1' if not found
    """
    branch_map = {
        "new york": "BR001",
        "san francisco": "BR002",
        "chennai": "BR003",
        "london": "BR004"
    }
    return branch_map.get(branch_query.strip().lower(), "-1")


@tool(name="banking_update_contact_details", description="Update the contact details (email/phone) for given account ID.", permission=ToolPermission.ADMIN)
def banking_update_contact_details(account_id: str, email: str = None, phone: str = None) -> str:
    """
    Update contact details for an account (simulated).
    :param account_id: Account identifier
    :param email: New email address (optional)
    :param phone: New phone number (optional)
    :return: Success or error message
    """
    if not account_id:
        return "Account ID must be provided."
    if not email and not phone:
        return "Either email or phone must be provided to update."

    # (In production, validate email/phone formats and persist)
    updates = {}
    if email:
        updates["email"] = email
    if phone:
        updates["phone"] = phone

    return f"Contact details for {account_id} updated: {json.dumps(updates)}"


@tool(name="banking_initiate_funds_transfer", description="Initiate a funds transfer between two accounts (internal).", permission=ToolPermission.ADMIN)
def banking_initiate_funds_transfer(from_account: str, to_account: str, amount: str, currency: str = "USD", reference: str = None) -> str:
    """
    Simulate initiating a funds transfer. Validates amount and accounts.
    :param from_account: Source account ID
    :param to_account: Destination account ID
    :param amount: Amount as string (e.g., '100.50')
    :param currency: Currency code
    :param reference: Optional transaction reference/note
    :return: JSON string with transfer status or error
    """
    # Basic checks
    if from_account == to_account:
        return json.dumps({"error": "from_account and to_account must be different"})

    mock_accounts = {"ACC10001", "ACC10002", "ACC10003"}
    if from_account not in mock_accounts:
        return json.dumps({"error": "from_account not found"})
    if to_account not in mock_accounts:
        return json.dumps({"error": "to_account not found"})

    # Validate amount
    try:
        amt = Decimal(amount)
    except (InvalidOperation, TypeError):
        return json.dumps({"error": f"Invalid amount: {amount}"})
    if amt <= 0:
        return json.dumps({"error": "Amount must be greater than zero"})

    # Mock balance check (replace with real lookup)
    mock_balances = {"ACC10001": Decimal("12500.75"), "ACC10002": Decimal("320.50"), "ACC10003": Decimal("9800.00")}
    if mock_balances.get(from_account, Decimal("0")) < amt:
        return json.dumps({"error": "Insufficient funds"})

    # Simulate transfer
    # NOTE: In production, this would create a transactional record in the payments/ledger system.
    tx_id = f"FT{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    result = {
        "transaction_id": tx_id,
        "from": from_account,
        "to": to_account,
        "amount": str(amt),
        "currency": currency,
        "status": "initiated",
        "reference": reference or ""
    }
    return json.dumps(result)