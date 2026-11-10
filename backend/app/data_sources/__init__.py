from app.data_sources.api_adapter import AuthorizedAPIAdapter
from app.data_sources.base import (
    BaseDataSourceAdapter,
    build_normalized_professional_document,
    check_candidate_eligibility,
    is_restricted_social_url,
    normalize_org_name,
    normalize_person_name,
    normalize_whitespace,
    parse_list_field,
)
from app.data_sources.crm_adapter import CRMAdapter
from app.data_sources.csv_adapter import CSVAdapter
from app.data_sources.directory_adapter import PublicDirectoryAdapter
from app.data_sources.manual_adapter import ManualProfileAdapter
from app.data_sources.website_adapter import OrganizationWebsiteAdapter

ADAPTER_REGISTRY: dict[str, type[BaseDataSourceAdapter]] = {
    "csv": CSVAdapter,
    "manual": ManualProfileAdapter,
    "licensed_api": AuthorizedAPIAdapter,
    "public_directory": PublicDirectoryAdapter,
    "organization_website": OrganizationWebsiteAdapter,
    "crm": CRMAdapter,
}

__all__ = [
    "ADAPTER_REGISTRY",
    "AuthorizedAPIAdapter",
    "BaseDataSourceAdapter",
    "CRMAdapter",
    "CSVAdapter",
    "ManualProfileAdapter",
    "OrganizationWebsiteAdapter",
    "PublicDirectoryAdapter",
    "build_normalized_professional_document",
    "check_candidate_eligibility",
    "is_restricted_social_url",
    "normalize_org_name",
    "normalize_person_name",
    "normalize_whitespace",
    "parse_list_field",
]
