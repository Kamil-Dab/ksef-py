"""Tests for Pydantic models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from ksef.models import (
    InvoiceFormat,
    InvoiceSendRequest,
    InvoiceStatus,
    KsefConfiguration,
    KsefCredentials,
    KsefEnvironment,
    TokenResponse,
)


class TestKsefCredentials:
    """Test cases for KsefCredentials model."""

    def test_valid_nip(self):
        """Test validation of valid NIP numbers."""
        creds = KsefCredentials(nip="1234567890")
        assert creds.nip == "1234567890"

    def test_nip_with_formatting(self):
        """Test NIP validation with formatting characters."""
        creds = KsefCredentials(nip="123-456-78-90")
        assert creds.nip == "1234567890"

        creds = KsefCredentials(nip="123 456 78 90")
        assert creds.nip == "1234567890"

    def test_invalid_nip_length(self):
        """Test validation error for invalid NIP length."""
        with pytest.raises(ValidationError, match="NIP must contain exactly 10 digits"):
            KsefCredentials(nip="123456789")  # Too short

        with pytest.raises(ValidationError, match="NIP must contain exactly 10 digits"):
            KsefCredentials(nip="12345678901")  # Too long

    def test_default_environment(self):
        """Test default environment is TEST."""
        creds = KsefCredentials(nip="1234567890")
        assert creds.environment == KsefEnvironment.TEST


class TestEnums:
    """Test cases for enum models."""

    def test_ksef_environment_values(self):
        """Test KsefEnvironment enum values."""
        assert KsefEnvironment.TEST.value == "test"
        assert KsefEnvironment.PROD.value == "prod"

    def test_invoice_status_values(self):
        """Test InvoiceStatus enum values."""
        assert InvoiceStatus.ACCEPTED.value == "Accepted"
        assert InvoiceStatus.REJECTED.value == "Rejected"
        assert InvoiceStatus.PENDING.value == "Pending"
        assert InvoiceStatus.ERROR.value == "Error"

    def test_invoice_format_values(self):
        """Test InvoiceFormat enum values."""
        assert InvoiceFormat.XML.value == "xml"
        assert InvoiceFormat.PDF.value == "pdf"


class TestTokenResponse:
    """Test cases for TokenResponse model."""

    def test_valid_token_response(self):
        """Test valid token response creation."""
        expires_at = datetime.now()
        response = TokenResponse(
            token="test.jwt.token",
            expires_at=expires_at,
        )

        assert response.token == "test.jwt.token"
        assert response.expires_at == expires_at
        assert response.session_token is None

    def test_token_response_with_session(self):
        """Test token response with session token."""
        expires_at = datetime.now()
        response = TokenResponse(
            token="test.jwt.token",
            expires_at=expires_at,
            session_token="session_123",
        )

        assert response.session_token == "session_123"


class TestInvoiceSendRequest:
    """Test cases for InvoiceSendRequest model."""

    def test_valid_request(self):
        """Test valid invoice send request."""
        xml_content = "<invoice>test</invoice>"
        request = InvoiceSendRequest(xml_content=xml_content)

        assert request.xml_content == xml_content
        assert request.filename is None
        assert request.encoding == "UTF-8"

    def test_request_with_filename(self):
        """Test request with filename."""
        xml_content = "<invoice>test</invoice>"
        request = InvoiceSendRequest(
            xml_content=xml_content, filename="test_invoice.xml"
        )

        assert request.filename == "test_invoice.xml"


class TestKsefConfiguration:
    """Test cases for KsefConfiguration model."""

    def test_valid_configuration(self):
        """Test valid configuration creation."""
        config = KsefConfiguration(
            base_url="https://ksef-test.mf.gov.pl/api",
            soap_url="https://ksef-test.mf.gov.pl/services",
        )

        assert config.base_url == "https://ksef-test.mf.gov.pl/api"
        assert config.soap_url == "https://ksef-test.mf.gov.pl/services"
        assert config.timeout == 30  # default
        assert config.max_retries == 3  # default

    def test_url_validation(self):
        """Test URL validation."""
        with pytest.raises(
            ValidationError, match="URLs must start with http:// or https://"
        ):
            KsefConfiguration(
                base_url="invalid-url",
                soap_url="https://ksef-test.mf.gov.pl/services",
            )

    def test_url_trailing_slash_removal(self):
        """Test that trailing slashes are removed from URLs."""
        config = KsefConfiguration(
            base_url="https://ksef-test.mf.gov.pl/api/",
            soap_url="https://ksef-test.mf.gov.pl/services/",
        )

        assert config.base_url == "https://ksef-test.mf.gov.pl/api"
        assert config.soap_url == "https://ksef-test.mf.gov.pl/services"
