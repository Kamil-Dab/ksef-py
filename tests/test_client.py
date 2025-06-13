"""Tests for KsefClient."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta

from ksef import KsefClient
from ksef.exceptions import KsefAuthenticationError, KsefValidationError
from ksef.models import KsefEnvironment, InvoiceStatus


class TestKsefClient:
    """Test cases for KsefClient."""

    def test_client_initialization(self, test_nip):
        """Test client initialization with default parameters."""
        client = KsefClient(nip=test_nip)
        
        assert client.credentials.nip == test_nip
        assert client.credentials.environment == KsefEnvironment.TEST
        assert client.config is not None

    def test_client_initialization_with_env(self, test_nip):
        """Test client initialization with specific environment."""
        client = KsefClient(nip=test_nip, env="prod")
        
        assert client.credentials.environment == KsefEnvironment.PROD

    def test_nip_validation(self):
        """Test NIP validation in credentials."""
        # Valid NIP
        client = KsefClient(nip="1234567890")
        assert client.credentials.nip == "1234567890"
        
        # NIP with formatting (should be cleaned)
        client = KsefClient(nip="123-456-78-90")
        assert client.credentials.nip == "1234567890"
        
        # Invalid NIP length
        with pytest.raises(ValueError, match="NIP must contain exactly 10 digits"):
            KsefClient(nip="123456789")

    @pytest.mark.asyncio
    async def test_generate_token_success(self, ksef_client, mock_httpx_client):
        """Test successful token generation."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: {
            "token": "test.jwt.token",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }
        mock_httpx_client.post.return_value = mock_response
        
        token_response = await ksef_client.generate_token()
        
        assert token_response.token == "test.jwt.token"
        assert token_response.expires_at > datetime.now()
        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_token_auth_error(self, ksef_client, mock_httpx_client):
        """Test token generation with authentication error."""
        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid credentials"}
        mock_response.content = b'{"error": "Invalid credentials"}'
        mock_httpx_client.post.return_value = mock_response
        
        with pytest.raises(KsefAuthenticationError):
            await ksef_client.generate_token()

    @pytest.mark.asyncio
    async def test_send_invoice_success(self, ksef_client, mock_httpx_client, sample_xml_invoice):
        """Test successful invoice sending."""
        # Mock token generation
        token_response = AsyncMock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "token": "test.jwt.token", 
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }
        
        # Mock invoice send
        send_response = AsyncMock()
        send_response.status_code = 201
        send_response.json.return_value = {
            "ksef_number": "KSEF:2025:PL/1234567890/ABC123"
        }
        
        mock_httpx_client.post.side_effect = [token_response, send_response]
        
        ksef_number = await ksef_client.send_invoice(sample_xml_invoice)
        
        assert ksef_number == "KSEF:2025:PL/1234567890/ABC123"
        assert mock_httpx_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_invoice_validation_error(self, ksef_client, mock_httpx_client):
        """Test invoice sending with validation error."""
        # Mock token generation (successful)
        token_response = AsyncMock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "token": "test.jwt.token",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }
        
        # Mock invoice send (validation error)
        send_response = AsyncMock()
        send_response.status_code = 400
        send_response.json.return_value = {"error": "Invalid XML"}
        send_response.content = b'{"error": "Invalid XML"}'
        
        mock_httpx_client.post.side_effect = [token_response, send_response]
        
        with pytest.raises(KsefValidationError):
            await ksef_client.send_invoice("<invalid>xml</invalid>")

    @pytest.mark.asyncio
    async def test_get_status_success(self, ksef_client, mock_httpx_client, test_ksef_number):
        """Test successful status check."""
        # Mock token generation
        token_response = AsyncMock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "token": "test.jwt.token",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }
        mock_httpx_client.post.return_value = token_response
        
        # Mock status check
        status_response = AsyncMock()
        status_response.status_code = 200
        status_response.json.return_value = {
            "status": "Accepted",
            "timestamp": datetime.now().isoformat(),
        }
        mock_httpx_client.get.return_value = status_response
        
        status = await ksef_client.get_status(test_ksef_number)
        
        assert status == InvoiceStatus.ACCEPTED
        mock_httpx_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_success(self, ksef_client, mock_httpx_client, test_ksef_number, tmp_path):
        """Test successful invoice download."""
        # Mock token generation
        token_response = AsyncMock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "token": "test.jwt.token",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }
        mock_httpx_client.post.return_value = token_response
        
        # Mock download
        download_response = AsyncMock()
        download_response.status_code = 200
        download_response.content = b"PDF content here"
        mock_httpx_client.get.return_value = download_response
        
        # Use tmp_path for output
        output_path = tmp_path / "test_invoice.pdf"
        
        with patch('pathlib.Path.write_bytes') as mock_write:
            result_path = await ksef_client.download(test_ksef_number, output_path=output_path)
            
            mock_write.assert_called_once_with(b"PDF content here")
            assert result_path == output_path

    @pytest.mark.asyncio
    async def test_context_manager(self, ksef_client):
        """Test async context manager functionality."""
        async with ksef_client as client:
            assert client is ksef_client
            
        # Client should be closed after context
        assert ksef_client._async_client is None

    def test_sync_wrapper_methods(self, ksef_client, sample_xml_invoice):
        """Test synchronous wrapper methods."""
        with patch.object(ksef_client, 'send_invoice') as mock_send:
            mock_send.return_value = "KSEF:2025:PL/1234567890/ABC123"
            
            # This would normally call asyncio.run, but we're mocking the async method
            with patch('asyncio.run') as mock_run:
                mock_run.return_value = "KSEF:2025:PL/1234567890/ABC123"
                
                result = ksef_client.send_invoice_sync(sample_xml_invoice)
                assert result == "KSEF:2025:PL/1234567890/ABC123"
                mock_run.assert_called_once() 