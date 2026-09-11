from datetime import date
from enum import StrEnum
from typing import Any, Dict, Final, List, Optional

from ibm_watsonx_orchestrate.agent_builder.agents import AgentSpec
from ibm_watsonx_orchestrate.agent_builder.tools import ToolSpec
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_extra_types.language_code import LanguageName  # pants: no-infer-dep
from pydantic_extra_types.semantic_version import SemanticVersion  # pants: no-infer-dep

MISSING_VALUE_SENTINEL: Final = "<missing_value>"

DEFAULT_LANGUAGES_SUPPORTED: Final = ["English"]
DEFAULT_DELETE_BY_DATE: Final = date.fromisoformat("2999-01-01")


# TODO: split types.py into tool_types.py, agent_types.py, offering_types.py and common_types.py
class DomainName(StrEnum):
    """Enum class for valid domain names for offering config data."""

    HR = "HR"
    PROCUREMENT = "Procurement"
    SALES = "Sales"
    PRODUCTIVITY = "Productivity"
    IT = "IT"
    SUPPLY_CHAIN = "Supply Chain"
    FINANCE = "Finance"


class CategoryName(StrEnum):
    """Enum class for valid category names for agent and tool config data."""

    AGENT = "agent"
    TOOL = "tool"


class AgentRoleName(StrEnum):
    """Enum class for valid agent role names for agent config data."""

    MANAGER = "manager"
    COLLABORATOR = "collaborator"


class PublisherName(StrEnum):
    """Enum class for valid publisher names for offering config data."""

    IBM = "IBM"


class BundleFormatVersion(StrEnum):
    """Enum class for valid tool zip bundle format versions."""

    V1_0_0 = "1.0.0"
    V2_0_0 = "2.0.0"


class PricingType(StrEnum):
    """Enum class for valid pricing values."""

    FREE = "free"
    PAID = "paid"


class PricingFrequencyType(StrEnum):
    """Enum class for valid pricing frequency values."""

    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    ANNUAL = "annual"
    SEMIANNUAL = "semiannual"


class PartNumberSpec(BaseModel):
    """Schema for offering config data's 'part_number' field."""

    # TODO: add validation for part number format (use regex)
    model_config = ConfigDict(str_min_length=1)

    aws: Optional[str] = None
    ibm_cloud: Optional[str] = None
    cp4d: Optional[str] = None


class FormFactorSpec(BaseModel):
    """Schema for scope data's 'form_factor'."""

    aws: PricingType
    ibm_cloud: PricingType
    cp4d: PricingType


class TenantTypeSpec(BaseModel):
    """Schema for scope data's 'tenant_type'."""

    trial: PricingType


class ScopeSpec(BaseModel):
    """Schema for offering config data's 'scope' field."""

    form_factor: FormFactorSpec
    tenant_type: TenantTypeSpec


class PricingSpec(BaseModel):
    """Schema for offering config data's 'pricing' field."""

    model_config = ConfigDict(str_min_length=1)

    currency: str
    amount: str
    frequency: PricingFrequencyType


class AssetsSpec(BaseModel):
    """Schema for offering config data's 'assets' field."""

    agents: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)


class OfferingConfigSpec(BaseModel):
    """Schema for offering config data."""

    model_config = ConfigDict(str_min_length=1)

    name: str
    display_name: str = Field(
        default=MISSING_VALUE_SENTINEL, description="The offering catalog display name."
    )
    domain: DomainName
    publisher: PublisherName = PublisherName.IBM
    version: SemanticVersion
    description: str = Field(
        default=MISSING_VALUE_SENTINEL, description="The offering catalog description."
    )
    assets: Dict[PublisherName, AssetsSpec]
    part_number: PartNumberSpec
    scope: ScopeSpec
    pricing: Optional[PricingSpec] = None
    delete_by: date


class AgentConfigSpec(AgentSpec):
    """Schema for agent config data."""

    model_config = ConfigDict(str_min_length=1)

    category: CategoryName
    agent_role: AgentRoleName
    publisher: PublisherName
    supported_apps: List[str]
    glossary: List[str]
    tags: List[DomainName]
    language_support: List[LanguageName]
    delete_by: date

    @model_validator(mode="before")
    @classmethod
    def validate_agent_fields(cls, values: Any) -> Any:
        """
        Args:
            values: the agent field values to validate
        Returns:
            the validated agent field values
        """
        # NOTE: this overrides BaseAgentSpec.validate_agent_fields(), which strips out
        # catalog-only fields in non-external-partner Agent specs. Since we do require
        # these fields, we don't want them to be stripped out.
        #
        # TODO: discuss a more sustainable solution without the requirement to override
        # this function with ADK team.
        return values


class ApplicationsSpec(BaseModel):
    """Schema for tool config data's 'applications' field."""

    app_id: str
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None


class ToolConfigSpec(ToolSpec):
    """Schema for tool config data."""

    publisher: PublisherName
    category: CategoryName
    tags: List[DomainName]
    applications: List[ApplicationsSpec]
    language_support: List[LanguageName]
    delete_by: date


class ApplicationsConfigSpec(BaseModel):
    """Schema for applications config data."""

    model_config = ConfigDict(str_min_length=1)

    name: str = Field(default="applications_file")
    version: SemanticVersion
    description: Optional[str] = None  # TODO: EPIC 32490 - assess if description field is needed
    applications: List[ApplicationsSpec]
