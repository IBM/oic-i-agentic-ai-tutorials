from typing import Optional

from ibm_watsonx_orchestrate.agent_builder.connections.types import (
    ConnectionType,
    ExpectedCredentials,
)

from agent_ready_tools.clients.clients_enums import AccessLevel, AribaApplications, DNBEntitlements
from agent_ready_tools.utils.env import in_adk_env, is_running_export_catalog
from agent_ready_tools.utils.systems import Systems
from agent_ready_tools.utils.tool_cred_utils import (
    InvalidConnectionSubCategoryError,
    UnsupportedConnectionSubCategoryError,
)

# Assigned suffix for domain agents published by IBM in SaaS catalogs.
IBM_PUBLISHER_SUFFIX = "_ibm_184bdbd3"


def published_app_id(app_id: str, suffix: str = IBM_PUBLISHER_SUFFIX) -> str:
    """Returns the given app_id with the given suffix appended."""
    # For local envs, will modify the suffix var during import deliverable building.
    if in_adk_env() and not is_running_export_catalog():
        return app_id
    return app_id + suffix


### Connection Constants
ADOBE_WORKFRONT_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("adobe_workfront_key_value"),
        type=ConnectionType.KEY_VALUE,
    ),
]

AMAZON_S3_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("amazon_s3_key_value"), type=ConnectionType.KEY_VALUE
    ),
]

ARIBA_BASE_CONNECTION = ExpectedCredentials(
    app_id=published_app_id("ariba_base_key_value"), type=ConnectionType.KEY_VALUE
)

ARIBA_BUYER_CONNECTIONS = [
    ARIBA_BASE_CONNECTION,
    ExpectedCredentials(
        app_id=published_app_id("ariba_buyer_key_value"), type=ConnectionType.KEY_VALUE
    ),
]

ARIBA_APPROVALS_CONNECTIONS = [
    ARIBA_BASE_CONNECTION,
    ExpectedCredentials(
        app_id=published_app_id("ariba_approvals_key_value"),
        type=ConnectionType.KEY_VALUE,
    ),
]

ARIBA_MASTER_DATA_RETRIEVAL_CONNECTIONS = [
    ARIBA_BASE_CONNECTION,
    ExpectedCredentials(
        app_id=published_app_id("ariba_master_data_retrieval_key_value"),
        type=ConnectionType.KEY_VALUE,
    ),
]

ARIBA_OPERATIONAL_PROCUREMENT_SYNCHRONOUS_CONNECTIONS = [
    ARIBA_BASE_CONNECTION,
    ExpectedCredentials(
        app_id=published_app_id("ariba_operational_procurement_synchronous_key_value"),
        type=ConnectionType.KEY_VALUE,
    ),
]
ARIBA_SOAP_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("ariba_soap_key_value"), type=ConnectionType.KEY_VALUE
    ),
]

ARIBA_SUPPLIER_CONNECTIONS = [
    ARIBA_BASE_CONNECTION,
    ExpectedCredentials(
        app_id=published_app_id("ariba_supplier_key_value"),
        type=ConnectionType.KEY_VALUE,
    ),
]

BOX_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("box_oauth2_auth_code"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

GOOGLE_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("google_oauth2_auth_code"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

COUPA_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("coupa_oauth2_auth_code"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

DNB_PROCUREMENT_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("dnb_procurement_oauth2_client_credentials"),
        type=ConnectionType.OAUTH2_CLIENT_CREDS,
    ),
]

DNB_SALES_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("dnb_sales_oauth2_client_credentials"),
        type=ConnectionType.OAUTH2_CLIENT_CREDS,
    ),
]

DROPBOX_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("dropbox_oauth2_auth_code"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

DYNAMICS365_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("dynamics365_oauth2_client_credentials"),
        type=ConnectionType.OAUTH2_CLIENT_CREDS,
    ),
]


RED_HAT_ANSIBLE_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("red_hat_ansible_conn_type"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

GITLAB_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("gitlab_oauth2_auth_code"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

HUBSPOT_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("hubspot_oauth2_auth_code"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

IBM_PA_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("ibm_planning_analytics_basic"),
        type=ConnectionType.BASIC_AUTH,
    ),
    ExpectedCredentials(
        app_id=published_app_id("ibm_planning_analytics_key_value"),
        type=ConnectionType.KEY_VALUE,
    ),
]

IBM_COS_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("ibm_cos_key_value"), type=ConnectionType.KEY_VALUE
    ),
]

IBM_TARGETPROCESS_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("ibm_targetprocess_bearer"),
        type=ConnectionType.BEARER_TOKEN,
    ),
]

TWILIO_CONNECTIONS = [
    ExpectedCredentials(app_id=published_app_id("twilio_basic"), type=ConnectionType.BASIC_AUTH),
]

JIRA_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("jira_oauth2_auth_code"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

JENKINS_CONNECTIONS = [
    ExpectedCredentials(app_id=published_app_id("jenkins_basic"), type=ConnectionType.BASIC_AUTH),
]

MICROSOFT_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("microsoft_oauth2_auth_code"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

MONDAY_CONNECTIONS = [
    ExpectedCredentials(app_id=published_app_id("monday_bearer"), type=ConnectionType.BEARER_TOKEN),
]

OPENPAGES_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("openpages_key_value"), type=ConnectionType.KEY_VALUE
    ),
]

GITHUB_CONNECTIONS = [
    ExpectedCredentials(app_id=published_app_id("github_key_value"), type=ConnectionType.KEY_VALUE),
]

ORACLE_HCM_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("oracle_hcm_basic"),
        type=ConnectionType.BASIC_AUTH,
    ),
    ExpectedCredentials(
        app_id=published_app_id("oracle_hcm_key_value"),
        type=ConnectionType.KEY_VALUE,
    ),
]

ORACLE_FUSION_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("oracle_fusion_basic"),
        type=ConnectionType.BASIC_AUTH,
    ),
]

SALESFORCE_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("salesforce_oauth2_auth_code"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

SALESLOFT_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("salesloft_oauth2_auth_code"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

SAP_SUCCESSFACTORS_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("sap_successfactors_basic"),
        type=ConnectionType.BASIC_AUTH,
    ),
    ExpectedCredentials(
        app_id=published_app_id("sap_successfactors_key_value"),
        type=ConnectionType.KEY_VALUE,
    ),
]

SAP_S4_HANA_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("sap_s4_hana_basic"), type=ConnectionType.BASIC_AUTH
    )
]

SEISMIC_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("seismic_oauth2_auth_code"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

SERVICENOW_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("servicenow_oauth2_auth_code"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

SLACK_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("slack_oauth2_auth_code"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

WORKDAY_BASE_CONNECTION = ExpectedCredentials(
    app_id=published_app_id("workday_base_key_value"), type=ConnectionType.KEY_VALUE
)

WORKDAY_EMPLOYEE_CONNECTIONS = [
    WORKDAY_BASE_CONNECTION,
    ExpectedCredentials(
        app_id=published_app_id("workday_employee_key_value"),
        type=ConnectionType.KEY_VALUE,
    ),
]

WORKDAY_MANAGER_CONNECTIONS = [
    WORKDAY_BASE_CONNECTION,
    ExpectedCredentials(
        app_id=published_app_id("workday_manager_key_value"),
        type=ConnectionType.KEY_VALUE,
    ),
]

# TODO: use when oauth2 is supported locally by ADK
WORKDAY_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("workday_oauth2_auth_code"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

IBM_SIP_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("ibm_sip_oauth2_client_credentials"),
        type=ConnectionType.OAUTH2_CLIENT_CREDS,
    ),
]

STERLING_OMS_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("sterling_oms_basic"), type=ConnectionType.BASIC_AUTH
    ),
    ExpectedCredentials(
        app_id=published_app_id("sterling_oms_key_value"), type=ConnectionType.KEY_VALUE
    ),
]

ZENDESK_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("zendesk_conn_type"),
        type=ConnectionType.OAUTH2_AUTH_CODE,
    ),
]

ZOOMINFO_CONNECTIONS = [
    ExpectedCredentials(
        app_id=published_app_id("zoominfo_key_value"), type=ConnectionType.KEY_VALUE
    ),
]


def get_system_from_credentials(
    credentials: ExpectedCredentials,
) -> list[tuple[Systems, Optional[str]]]:
    """
    Returns the system(s) and sub-category that use the given credentials. This is the inverse of
    get_expected_credentials.

    Args:
        credentials: The ExpectedCredentials to find systems for.

    Returns:
        A list of tuples containing (system, sub_category) that use these credentials.
        sub_category will be None if the system doesn't use sub-categories.
    """
    results: list[tuple[Systems, Optional[str]]] = []

    # Check each system and its connections
    if credentials in ADOBE_WORKFRONT_CONNECTIONS:
        results.append((Systems.ADOBEWORKFRONT, None))

    if credentials in AMAZON_S3_CONNECTIONS:
        results.append((Systems.AMAZON_S3, None))

    # Ariba systems with sub-categories
    if credentials in ARIBA_BUYER_CONNECTIONS:
        results.append((Systems.ARIBA, AribaApplications.BUYER))
    if credentials in ARIBA_SUPPLIER_CONNECTIONS:
        results.append((Systems.ARIBA, AribaApplications.SUPPLIER))
    if credentials in ARIBA_APPROVALS_CONNECTIONS:
        results.append((Systems.ARIBA, AribaApplications.APPROVALS))
    if credentials in ARIBA_MASTER_DATA_RETRIEVAL_CONNECTIONS:
        results.append((Systems.ARIBA, AribaApplications.MASTER_DATA_RETRIEVAL))
    if credentials in ARIBA_OPERATIONAL_PROCUREMENT_SYNCHRONOUS_CONNECTIONS:
        results.append((Systems.ARIBA, AribaApplications.OPERATIONAL_PROCUREMENT_SYNCHRONOUS))

    if credentials in ARIBA_SOAP_CONNECTIONS:
        results.append((Systems.ARIBA_SOAP, None))

    if credentials in BOX_CONNECTIONS:
        results.append((Systems.BOX, None))

    if credentials in COUPA_CONNECTIONS:
        results.append((Systems.COUPA, None))

    # DNB systems with sub-categories
    if credentials in DNB_PROCUREMENT_CONNECTIONS:
        results.append((Systems.DNB, DNBEntitlements.PROCUREMENT))
    if credentials in DNB_SALES_CONNECTIONS:
        results.append((Systems.DNB, DNBEntitlements.SALES))

    if credentials in DROPBOX_CONNECTIONS:
        results.append((Systems.DROPBOX, None))

    if credentials in DYNAMICS365_CONNECTIONS:
        results.append((Systems.DYNAMICS365, None))

    if credentials in GITLAB_CONNECTIONS:
        results.append((Systems.GITLAB, None))

    if credentials in GOOGLE_CONNECTIONS:
        results.append((Systems.GOOGLE, None))

    if credentials in HUBSPOT_CONNECTIONS:
        results.append((Systems.HUBSPOT, None))

    if credentials in IBM_COS_CONNECTIONS:
        results.append((Systems.IBM_COS, None))

    if credentials in IBM_PA_CONNECTIONS:
        results.append((Systems.IBM_PLANNING_ANALYTICS, None))

    if credentials in IBM_SIP_CONNECTIONS:
        results.append((Systems.IBM_SIP, None))

    if credentials in IBM_TARGETPROCESS_CONNECTIONS:
        results.append((Systems.IBM_TARGETPROCESS, None))

    if credentials in JENKINS_CONNECTIONS:
        results.append((Systems.JENKINS, None))

    if credentials in JIRA_CONNECTIONS:
        results.append((Systems.JIRA, None))

    if credentials in MICROSOFT_CONNECTIONS:
        results.append((Systems.MICROSOFT, None))

    if credentials in ORACLE_FUSION_CONNECTIONS:
        results.append((Systems.ORACLE_FUSION, None))

    if credentials in ORACLE_HCM_CONNECTIONS:
        results.append((Systems.ORACLE_HCM, None))

    if credentials in RED_HAT_ANSIBLE_CONNECTIONS:
        results.append((Systems.RED_HAT_ANSIBLE, None))

    if credentials in SALESFORCE_CONNECTIONS:
        results.append((Systems.SALESFORCE, None))

    if credentials in SALESLOFT_CONNECTIONS:
        results.append((Systems.SALESLOFT, None))

    if credentials in SAP_S4_HANA_CONNECTIONS:
        results.append((Systems.SAP_S4_HANA, None))

    if credentials in SAP_SUCCESSFACTORS_CONNECTIONS:
        results.append((Systems.SAP_SUCCESSFACTORS, None))

    if credentials in SEISMIC_CONNECTIONS:
        results.append((Systems.SEISMIC, None))

    if credentials in SERVICENOW_CONNECTIONS:
        results.append((Systems.SERVICENOW, None))

    if credentials in SLACK_CONNECTIONS:
        results.append((Systems.SLACK, None))

    if credentials in STERLING_OMS_CONNECTIONS:
        results.append((Systems.STERLING_OMS, None))

    if credentials in TWILIO_CONNECTIONS:
        results.append((Systems.TWILIO, None))

    # Workday systems with sub-categories
    if credentials in WORKDAY_EMPLOYEE_CONNECTIONS:
        results.append((Systems.WORKDAY, AccessLevel.EMPLOYEE))
    if credentials in WORKDAY_MANAGER_CONNECTIONS:
        results.append((Systems.WORKDAY, AccessLevel.MANAGER))

    if credentials in ZENDESK_CONNECTIONS:
        results.append((Systems.ZENDESK, None))

    if credentials in ZOOMINFO_CONNECTIONS:
        results.append((Systems.ZOOMINFO, None))

    return results


def get_expected_credentials(
    system: Systems, sub_category: Optional[str] = None
) -> Optional[ExpectedCredentials]:
    """
    Returns the required ExpectedCredentials configuration for a given system's tools.

    Args:
        system: The system to return connections for.
        sub_category: A specific sub-category of creds for the given system.

    Returns:
        The ExpectedCredentials for the system.
    """
    if system == Systems.ADOBEWORKFRONT:
        return ADOBE_WORKFRONT_CONNECTIONS
    elif system == Systems.ARIBA:
        if sub_category not in AribaApplications:
            raise InvalidConnectionSubCategoryError(system, sub_category, AribaApplications)
        elif sub_category == AribaApplications.BUYER:
            return ARIBA_BUYER_CONNECTIONS
        elif sub_category == AribaApplications.SUPPLIER:
            return ARIBA_SUPPLIER_CONNECTIONS
        elif sub_category == AribaApplications.APPROVALS:
            return ARIBA_APPROVALS_CONNECTIONS
        elif sub_category == AribaApplications.MASTER_DATA_RETRIEVAL:
            return ARIBA_MASTER_DATA_RETRIEVAL_CONNECTIONS
        elif sub_category == AribaApplications.OPERATIONAL_PROCUREMENT_SYNCHRONOUS:
            return ARIBA_OPERATIONAL_PROCUREMENT_SYNCHRONOUS_CONNECTIONS
        raise UnsupportedConnectionSubCategoryError(system, sub_category)
    elif system == Systems.ARIBA_SOAP:
        return ARIBA_SOAP_CONNECTIONS
    elif system == Systems.AMAZON_S3:
        return AMAZON_S3_CONNECTIONS
    elif system == Systems.BOX:
        return BOX_CONNECTIONS
    elif system == Systems.COUPA:
        return COUPA_CONNECTIONS
    elif system == Systems.DNB:
        if sub_category not in DNBEntitlements:
            raise InvalidConnectionSubCategoryError(system, sub_category, DNBEntitlements)
        elif sub_category == DNBEntitlements.PROCUREMENT:
            return DNB_PROCUREMENT_CONNECTIONS
        elif sub_category == DNBEntitlements.SALES:
            return DNB_SALES_CONNECTIONS
        raise UnsupportedConnectionSubCategoryError(system, sub_category)
    elif system == Systems.DROPBOX:
        return DROPBOX_CONNECTIONS
    elif system == Systems.DYNAMICS365:
        return DYNAMICS365_CONNECTIONS
    elif system == Systems.GITLAB:
        return GITLAB_CONNECTIONS
    elif system == Systems.GOOGLE:
        return GOOGLE_CONNECTIONS
    elif system == Systems.HUBSPOT:
        return HUBSPOT_CONNECTIONS
    elif system == Systems.IBM_COS:
        return IBM_COS_CONNECTIONS
    elif system == Systems.IBM_TARGETPROCESS:
        return IBM_TARGETPROCESS_CONNECTIONS
    elif system == Systems.RED_HAT_ANSIBLE:
        return RED_HAT_ANSIBLE_CONNECTIONS
    elif system == Systems.TWILIO:
        return TWILIO_CONNECTIONS
    elif system == Systems.JIRA:
        return JIRA_CONNECTIONS
    elif system == Systems.JENKINS:
        return JENKINS_CONNECTIONS
    elif system == Systems.MICROSOFT:
        return MICROSOFT_CONNECTIONS
    elif system == Systems.ORACLE_HCM:
        return ORACLE_HCM_CONNECTIONS
    elif system == Systems.ORACLE_FUSION:
        return ORACLE_FUSION_CONNECTIONS
    elif system == Systems.SALESFORCE:
        return SALESFORCE_CONNECTIONS
    elif system == Systems.SALESLOFT:
        return SALESLOFT_CONNECTIONS
    elif system == Systems.SAP_SUCCESSFACTORS:
        return SAP_SUCCESSFACTORS_CONNECTIONS
    elif system == Systems.SAP_S4_HANA:
        return SAP_S4_HANA_CONNECTIONS
    elif system == Systems.SEISMIC:
        return SEISMIC_CONNECTIONS
    elif system == Systems.SERVICENOW:
        return SERVICENOW_CONNECTIONS
    elif system == Systems.SLACK:
        return SLACK_CONNECTIONS
    elif system == Systems.IBM_SIP:
        return IBM_SIP_CONNECTIONS
    elif system == Systems.STERLING_OMS:
        return STERLING_OMS_CONNECTIONS
    elif system == Systems.WORKDAY:
        if sub_category not in AccessLevel:
            raise InvalidConnectionSubCategoryError(system, sub_category, AccessLevel)
        elif sub_category == AccessLevel.EMPLOYEE:
            return WORKDAY_EMPLOYEE_CONNECTIONS
        elif sub_category == AccessLevel.MANAGER:
            return WORKDAY_MANAGER_CONNECTIONS
        raise UnsupportedConnectionSubCategoryError(system, sub_category)
    elif system == Systems.ZENDESK:
        return ZENDESK_CONNECTIONS
    elif system == Systems.ZOOMINFO:
        return ZOOMINFO_CONNECTIONS
    elif system == Systems.IBM_PLANNING_ANALYTICS:
        return IBM_PA_CONNECTIONS
    return None
