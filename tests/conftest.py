"""Pytest configuration and shared fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from ksef import KsefClient
from ksef.models import KsefEnvironment, TokenResponse


@pytest.fixture
def test_nip():
    """Sample test NIP number."""
    return "1234567890"


@pytest.fixture
def test_ksef_number():
    """Sample KSeF number for testing."""
    return "KSEF:2025:PL/1234567890/ABC123"


@pytest.fixture
def sample_xml_invoice():
    """Sample invoice XML content."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="http://ksef.mf.gov.pl/schema/gtw/svc/types/2021/10/01/0001">
    <InvoiceHeader>
        <InvoiceNumber>FA/001/2025</InvoiceNumber>
        <IssueDate>2025-01-01</IssueDate>
        <Seller>
            <TaxId>1234567890</TaxId>
            <Name>Test Company</Name>
        </Seller>
        <Buyer>
            <TaxId>9876543210</TaxId>
            <Name>Test Buyer</Name>
        </Buyer>
    </InvoiceHeader>
    <InvoiceBody>
        <TotalAmount>123.45</TotalAmount>
        <Currency>PLN</Currency>
    </InvoiceBody>
</Invoice>"""


@pytest.fixture
def mock_token_response():
    """Mock token response."""
    return TokenResponse(
        token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.token",
        expires_at=datetime.now() + timedelta(hours=1),
        session_token="session_123",
    )


@pytest.fixture
def ksef_client(test_nip):
    """KSeF client instance for testing."""
    return KsefClient(
        nip=test_nip,
        env=KsefEnvironment.TEST,
    )


@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient."""
    client = AsyncMock()
    
    # Mock successful token response
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "token": "test.jwt.token",
        "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        "session_token": "session_123",
    }
    client.post.return_value = mock_response
    client.get.return_value = mock_response
    
    return client


@pytest.fixture(autouse=True)
def mock_httpx_clients(monkeypatch, mock_httpx_client):
    """Automatically mock httpx clients for all tests."""
    def mock_async_client_property(self):
        return mock_httpx_client
        
    def mock_sync_client_property(self):
        return MagicMock()
    
    monkeypatch.setattr(KsefClient, "async_client", property(mock_async_client_property))
    monkeypatch.setattr(KsefClient, "sync_client", property(mock_sync_client_property)) 