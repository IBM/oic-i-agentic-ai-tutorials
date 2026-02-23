from unittest.mock import MagicMock, patch

from requests.auth import HTTPBasicAuth

from agent_ready_tools.clients.ariba_soap_client import AribaSOAPClient


@patch("agent_ready_tools.clients.ariba_soap_client.requests.post")
def test_ariba_soap_client(mock_client: MagicMock) -> None:
    """Test that the `AribaSOAPClient` is working as expected."""

    # Define mock API response data
    test_data = {
        "base_url": "https://s1.ariba.com",
        "realm": "IBM-TEST_REALM",
        "access_token": "e9c95590-5eb4-47e0-b8c1-27a021b66ee3",
        "username": "aaa",
        "password": "pass1234",
        "requester_pass": "PasswordAdapter1",
    }

    # Create a mock instance for API requests
    mock_client.return_value = MagicMock()
    # mock_client.return_value.status_code = 200  # Ensure no HTTP error
    mock_client.return_value.raise_for_status = MagicMock()  # Prevent raising errors

    # Call the AribaClient client with params
    client: AribaSOAPClient = AribaSOAPClient(
        base_url=test_data["base_url"],
        realm=test_data["realm"],
        username=test_data["username"],
        password=test_data["password"],
        requester_password=test_data["requester_pass"],
    )

    endpoint = "Buyer/soap/IBMInnovationDSAPP-T/RequisitionImportPull"
    xml_payload = b"""<?xml version="1.0" encoding="UTF-8"?>\n<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">\n  <soapenv:Body><ns1:RequisitionImportPullRequest xmlns:ns1="urn:Ariba:Buyer:vrealm_3841" partition="prealm_3841" variant="vrealm_3841"><ns1:Requisition_RequisitionImportPull_Item>  <ns1:item><ns1:LineItems><ns1:item><ns1:Description><ns1:Description>Test item</ns1:Description><ns1:Price><ns1:Amount>12.00</ns1:Amount><ns1:Currency><ns1:UniqueName>USD</ns1:UniqueName></ns1:Currency></ns1:Price><ns1:UnitOfMeasure><ns1:UniqueName>EA</ns1:UniqueName></ns1:UnitOfMeasure></ns1:Description><ns1:NumberInCollection>1</ns1:NumberInCollection><ns1:OriginatingSystemLineNumber>1</ns1:OriginatingSystemLineNumber><ns1:Quantity>1</ns1:Quantity><ns1:ImportedDeliverToStaging>3000</ns1:ImportedDeliverToStaging><ns1:ImportedLineCommentStaging>test</ns1:ImportedLineCommentStaging><ns1:ImportedLineExternalCommentStaging>true</ns1:ImportedLineExternalCommentStaging><ns1:ImportedNeedByStaging>2025-06-01T12:00:00</ns1:ImportedNeedByStaging></ns1:item></ns1:LineItems><ns1:Name>PR by Gee</ns1:Name><ns1:OriginatingSystem>API-test</ns1:OriginatingSystem><ns1:OriginatingSystemReferenceID>32b6d112-42af-42be-b610-e1e7a57389d6</ns1:OriginatingSystemReferenceID><ns1:Preparer><ns1:UniqueName>pp1</ns1:UniqueName><ns1:PasswordAdapter>PA33456</ns1:PasswordAdapter></ns1:Preparer><ns1:Requester><ns1:UniqueName>pp1</ns1:UniqueName><ns1:PasswordAdapter>PA33456</ns1:PasswordAdapter></ns1:Requester><ns1:UniqueName>3000</ns1:UniqueName>  </ns1:item></ns1:Requisition_RequisitionImportPull_Item></ns1:RequisitionImportPullRequest>\n  </soapenv:Body>\n</soapenv:Envelope>"""

    headers = {
        "Content-Type": "text/xml;charset=UTF-8",
        "soapAction": "/Process Definition",
        "realm": test_data["realm"],
    }
    # Call get_request function from Ariba SOAP Client client''
    # Make request to Ariba
    json_response = client.post_request(headers=headers, endpoint=endpoint, payload=xml_payload)
    # Ensure that _post_request() executed and returned proper values
    assert json_response

    _, called_kwargs = mock_client.call_args
    assert called_kwargs["headers"] == headers
    auth_arg = called_kwargs.get("auth")
    assert isinstance(called_kwargs["auth"], HTTPBasicAuth)
    assert auth_arg.username == test_data["username"]
    assert auth_arg.password == test_data["password"]
