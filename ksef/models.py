"""Pydantic models for KSeF API data structures."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class KsefEnvironment(str, Enum):
    """KSeF environment types."""

    TEST = "test"
    PROD = "prod"


class InvoiceStatus(str, Enum):
    """KSeF invoice status types."""

    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    PENDING = "Pending"
    ERROR = "Error"


class AuthMethod(str, Enum):
    """Authentication methods supported by KSeF."""

    TOKEN = "token"
    CHALLENGE_FILE = "challenge_file"


class InvoiceFormat(str, Enum):
    """Supported invoice download formats."""

    XML = "xml"
    PDF = "pdf"


class KsefCredentials(BaseModel):
    """KSeF authentication credentials."""

    nip: str = Field(..., description="Company NIP number")
    environment: KsefEnvironment = Field(default=KsefEnvironment.TEST)
    token_path: Optional[str] = Field(None, description="Path to JWT token file")
    private_key_path: Optional[str] = Field(
        None, description="Path to private key for signing"
    )
    certificate_path: Optional[str] = Field(None, description="Path to certificate")

    @field_validator("nip")
    @classmethod
    def validate_nip(cls, v: str) -> str:
        """Validate NIP format."""
        # Remove any non-digits
        nip_digits = "".join(filter(str.isdigit, v))
        if len(nip_digits) != 10:
            raise ValueError("NIP must contain exactly 10 digits")
        return nip_digits


class TokenResponse(BaseModel):
    """Response from token generation endpoint."""

    token: str
    expires_at: datetime
    session_token: Optional[str] = None


class InvoiceSendRequest(BaseModel):
    """Request for sending an invoice."""

    xml_content: str = Field(..., description="Invoice XML content")
    filename: Optional[str] = Field(None, description="Original filename")
    encoding: str = Field(default="UTF-8")


class InvoiceSendResponse(BaseModel):
    """Response from sending an invoice."""

    ksef_number: str = Field(..., description="Assigned KSeF number")
    timestamp: datetime
    processing_code: Optional[str] = None
    processing_description: Optional[str] = None


class InvoiceStatusRequest(BaseModel):
    """Request for checking invoice status."""

    ksef_number: str = Field(..., description="KSeF number to check")


class InvoiceStatusResponse(BaseModel):
    """Response from invoice status check."""

    ksef_number: str
    status: InvoiceStatus
    timestamp: datetime
    processing_code: Optional[str] = None
    processing_description: Optional[str] = None
    acquisition_timestamp: Optional[datetime] = None
    download_url: Optional[str] = None


class InvoiceDownloadRequest(BaseModel):
    """Request for downloading an invoice."""

    ksef_number: str = Field(..., description="KSeF number to download")
    format: InvoiceFormat = Field(default=InvoiceFormat.PDF)


class InvoiceDownloadResponse(BaseModel):
    """Response from invoice download."""

    content: bytes
    filename: str
    content_type: str
    size: int


class KsefApiError(BaseModel):
    """Standard KSeF API error response."""

    error_code: str
    error_message: str
    details: Optional[dict[str, Any]] = None
    timestamp: Optional[datetime] = None


class SessionInfo(BaseModel):
    """Information about current KSeF session."""

    session_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    environment: KsefEnvironment
    nip: str
    authenticated: bool = False


class ReferenceDataEntry(BaseModel):
    """Entry in KSeF reference data cache."""

    nip: str
    name: str
    bank_accounts: list[str] = Field(default_factory=list)
    last_updated: datetime
    active: bool = True


class KsefConfiguration(BaseModel):
    """KSeF client configuration."""

    base_url: str
    soap_url: str
    timeout: int = Field(default=30)
    max_retries: int = Field(default=3)
    retry_delay: float = Field(default=1.0)
    verify_ssl: bool = Field(default=True)
    user_agent: str = Field(default="ksef-py/0.0.1a1")

    @field_validator("base_url", "soap_url")
    @classmethod
    def validate_urls(cls, v: str) -> str:
        """Ensure URLs are properly formatted."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URLs must start with http:// or https://")
        return v.rstrip("/")


# Default configurations for different environments
KSEF_CONFIGS = {
    KsefEnvironment.TEST: KsefConfiguration(
        base_url="https://ksef-test.mf.gov.pl/api",
        soap_url="https://ksef-test.mf.gov.pl/services",
    ),
    KsefEnvironment.PROD: KsefConfiguration(
        base_url="https://ksef.mf.gov.pl/api",
        soap_url="https://ksef.mf.gov.pl/services",
    ),
}
