from ibm_watsonx_orchestrate.agent_builder.connections.types import (
    ConnectionType,
    ExpectedCredentials,
)
import pytest

from agent_ready_tools.clients.clients_enums import DNBEntitlements
from agent_ready_tools.utils.systems import Systems
from agent_ready_tools.utils.tool_cred_utils import InvalidConnectionSubCategoryError
from agent_ready_tools.utils.tool_credentials import get_expected_credentials, published_app_id


def test_get_expected_connections() -> None:
    """Tests getting connections for a given system."""
    # TO DO: Add more testing once different systems are added
    sap_conns = get_expected_credentials(Systems.SAP_SUCCESSFACTORS)
    assert sap_conns
    assert sap_conns == [
        ExpectedCredentials(
            app_id=published_app_id("sap_successfactors_basic"), type=ConnectionType.BASIC_AUTH
        ),
        ExpectedCredentials(
            app_id=published_app_id("sap_successfactors_key_value"), type=ConnectionType.KEY_VALUE
        ),
    ]

    adobe_conns = get_expected_credentials(Systems.ADOBEWORKFRONT)
    assert adobe_conns
    assert adobe_conns == [
        ExpectedCredentials(
            app_id=published_app_id("adobe_workfront_key_value"), type=ConnectionType.KEY_VALUE
        ),
    ]

    dropbox_conns = get_expected_credentials(Systems.DROPBOX)
    assert dropbox_conns
    assert dropbox_conns == [
        ExpectedCredentials(
            app_id=published_app_id("dropbox_oauth2_auth_code"),
            type=ConnectionType.OAUTH2_AUTH_CODE,
        ),
    ]

    with pytest.raises(InvalidConnectionSubCategoryError):
        # sub_category required
        get_expected_credentials(Systems.DNB)

    with pytest.raises(InvalidConnectionSubCategoryError):
        # sub_category must be in DnBEntitlements for DnB
        get_expected_credentials(Systems.DNB, "INVALID")

    dnb_sales_conns = get_expected_credentials(Systems.DNB, DNBEntitlements.SALES)
    assert dnb_sales_conns
    assert dnb_sales_conns == [
        ExpectedCredentials(
            app_id=published_app_id("dnb_sales_oauth2_client_credentials"),
            type=ConnectionType.OAUTH2_CLIENT_CREDS,
        ),
    ]
