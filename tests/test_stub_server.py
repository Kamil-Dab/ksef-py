"""Tests for the stub server module."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from ksef.stub_server import create_app, clear_storage


class TestStubServer:
    """Test cases for the stub server."""

    def setup_method(self):
        """Set up test fixtures."""
        # Clear storage before each test to ensure isolation
        clear_storage()
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_root_endpoint(self):
        """Test root endpoint returns API info."""
        response = self.client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "KSeF Stub Server"
        assert "endpoints" in data

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_generate_token_success(self):
        """Test successful token generation."""
        request_data = {
            "nip": "1234567890",
            "environment": "test"
        }
        
        response = self.client.post("/v1/auth/token", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "token" in data
        assert data["token"].startswith("mock.jwt.token")
        assert "expires_at" in data
        assert "session_token" in data

    def test_generate_token_invalid_nip(self):
        """Test token generation with invalid NIP."""
        request_data = {
            "nip": "123",  # Too short
            "environment": "test"
        }
        
        response = self.client.post("/v1/auth/token", json=request_data)
        assert response.status_code == 400

    def test_generate_token_invalid_environment(self):
        """Test token generation with invalid environment."""
        request_data = {
            "nip": "1234567890",
            "environment": "invalid"
        }
        
        response = self.client.post("/v1/auth/token", json=request_data)
        assert response.status_code == 400

    def test_send_invoice_success(self):
        """Test successful invoice sending."""
        # First get a token
        token_response = self.client.post("/v1/auth/token", json={
            "nip": "1234567890",
            "environment": "test"
        })
        token = token_response.json()["token"]
        
        # Send invoice
        invoice_data = {
            "xml_content": "<?xml version='1.0'?><invoice>test</invoice>",
            "filename": "test.xml"
        }
        
        response = self.client.post(
            "/v1/invoices/send",
            json=invoice_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "ksef_number" in data
        assert data["ksef_number"].startswith("KSEF:2025:PL/")

    def test_send_invoice_no_auth(self):
        """Test invoice sending without authorization."""
        invoice_data = {
            "xml_content": "<?xml version='1.0'?><invoice>test</invoice>",
            "filename": "test.xml"
        }
        
        response = self.client.post("/v1/invoices/send", json=invoice_data)
        assert response.status_code == 422  # Missing header

    def test_send_invoice_invalid_token(self):
        """Test invoice sending with invalid token."""
        invoice_data = {
            "xml_content": "<?xml version='1.0'?><invoice>test</invoice>",
            "filename": "test.xml"
        }
        
        response = self.client.post(
            "/v1/invoices/send",
            json=invoice_data,
            headers={"Authorization": "Bearer invalid.token"}
        )
        
        assert response.status_code == 401

    def test_send_invoice_invalid_xml(self):
        """Test invoice sending with invalid XML."""
        # Get token first
        token_response = self.client.post("/v1/auth/token", json={
            "nip": "1234567890",
            "environment": "test"
        })
        token = token_response.json()["token"]
        
        invoice_data = {
            "xml_content": "not xml content",
            "filename": "test.xml"
        }
        
        response = self.client.post(
            "/v1/invoices/send",
            json=invoice_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 400

    def test_get_invoice_status_success(self):
        """Test getting invoice status."""
        # First send an invoice to create it
        token_response = self.client.post("/v1/auth/token", json={
            "nip": "1234567890",
            "environment": "test"
        })
        token = token_response.json()["token"]
        
        # Send invoice
        invoice_response = self.client.post(
            "/v1/invoices/send",
            json={"xml_content": "<?xml version='1.0'?><invoice>test</invoice>"},
            headers={"Authorization": f"Bearer {token}"}
        )
        ksef_number = invoice_response.json()["ksef_number"]
        
        # Get status
        status_response = self.client.get(
            f"/v1/invoices/{ksef_number}/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert status_response.status_code == 200
        data = status_response.json()
        assert data["ksef_number"] == ksef_number
        assert data["status"] == "Accepted"

    def test_get_invoice_status_not_found(self):
        """Test getting status for non-existent invoice."""
        token_response = self.client.post("/v1/auth/token", json={
            "nip": "1234567890",
            "environment": "test"
        })
        token = token_response.json()["token"]
        
        response = self.client.get(
            "/v1/invoices/NONEXISTENT/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 404

    def test_download_invoice_pdf(self):
        """Test downloading invoice as PDF."""
        # First send an invoice
        token_response = self.client.post("/v1/auth/token", json={
            "nip": "1234567890",
            "environment": "test"
        })
        token = token_response.json()["token"]
        
        invoice_response = self.client.post(
            "/v1/invoices/send",
            json={"xml_content": "<?xml version='1.0'?><invoice>test</invoice>"},
            headers={"Authorization": f"Bearer {token}"}
        )
        ksef_number = invoice_response.json()["ksef_number"]
        
        # Download as PDF
        download_response = self.client.get(
            f"/v1/invoices/{ksef_number}/download?format=pdf",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert download_response.status_code == 200
        assert download_response.headers["content-type"] == "application/pdf"

    def test_download_invoice_xml(self):
        """Test downloading invoice as XML."""
        # First send an invoice
        token_response = self.client.post("/v1/auth/token", json={
            "nip": "1234567890",
            "environment": "test"
        })
        token = token_response.json()["token"]
        
        original_xml = "<?xml version='1.0'?><invoice>test</invoice>"
        invoice_response = self.client.post(
            "/v1/invoices/send",
            json={"xml_content": original_xml},
            headers={"Authorization": f"Bearer {token}"}
        )
        ksef_number = invoice_response.json()["ksef_number"]
        
        # Download as XML
        download_response = self.client.get(
            f"/v1/invoices/{ksef_number}/download?format=xml",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert download_response.status_code == 200
        assert download_response.headers["content-type"] == "application/xml"
        assert original_xml in download_response.text

    def test_download_invoice_invalid_format(self):
        """Test downloading invoice with invalid format."""
        token_response = self.client.post("/v1/auth/token", json={
            "nip": "1234567890",
            "environment": "test"
        })
        token = token_response.json()["token"]
        
        invoice_response = self.client.post(
            "/v1/invoices/send",
            json={"xml_content": "<?xml version='1.0'?><invoice>test</invoice>"},
            headers={"Authorization": f"Bearer {token}"}
        )
        ksef_number = invoice_response.json()["ksef_number"]
        
        # Try invalid format
        download_response = self.client.get(
            f"/v1/invoices/{ksef_number}/download?format=invalid",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert download_response.status_code == 400 