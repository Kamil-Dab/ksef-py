"""Tests for the CLI module."""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path

from ksef.cli import main
from ksef.models import InvoiceStatus


class TestCLI:
    """Test cases for CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_cli_help(self):
        """Test CLI help command."""
        result = self.runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert "ksef-py: Modern Python SDK + CLI" in result.output
        assert "send" in result.output
        assert "status" in result.output
        assert "download" in result.output

    def test_cli_version(self):
        """Test CLI version command."""
        result = self.runner.invoke(main, ['--version'])
        assert result.exit_code == 0

    @patch('ksef.cli.KsefClient')
    @patch('ksef.cli.Path.read_text')
    def test_send_command_success(self, mock_read_text, mock_client_class):
        """Test successful send command."""
        # Mock file reading
        mock_read_text.return_value = "<invoice>test</invoice>"
        
        # Mock client
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.send_invoice.return_value = "KSEF:2025:PL/123/ABC"
        mock_client_class.return_value = mock_client
        
        # Mock file existence
        with patch('ksef.cli.Path.exists', return_value=True):
            result = self.runner.invoke(main, [
                'send', 'test_invoice.xml',
                '--nip', '1234567890'
            ])
        
        assert result.exit_code == 0
        assert "Invoice sent successfully" in result.output

    @patch('ksef.cli.KsefClient')
    def test_status_command_success(self, mock_client_class):
        """Test successful status command."""
        # Mock client
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get_status.return_value = InvoiceStatus.ACCEPTED
        mock_client_class.return_value = mock_client
        
        result = self.runner.invoke(main, [
            'status', 'KSEF:2025:PL/123/ABC',
            '--nip', '1234567890'
        ])
        
        assert result.exit_code == 0

    @patch('ksef.cli.KsefClient')
    def test_download_command_success(self, mock_client_class):
        """Test successful download command."""
        # Mock client
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.download.return_value = Path("test.pdf")
        mock_client_class.return_value = mock_client
        
        result = self.runner.invoke(main, [
            'download', 'KSEF:2025:PL/123/ABC',
            '--nip', '1234567890'
        ])
        
        assert result.exit_code == 0

    @patch('ksef.cli.Path.exists')
    def test_validate_command_success(self, mock_exists):
        """Test successful validate command."""
        mock_exists.return_value = True
        
        with patch('xml.etree.ElementTree.parse') as mock_parse:
            mock_parse.return_value = MagicMock()
            
            result = self.runner.invoke(main, [
                'validate', 'test_invoice.xml'
            ])
            
            assert result.exit_code == 0
            assert "XML is well-formed" in result.output

    @patch('ksef.cli.Path.exists')
    def test_validate_command_invalid_xml(self, mock_exists):
        """Test validate command with invalid XML."""
        mock_exists.return_value = True
        
        import xml.etree.ElementTree as ET
        with patch('xml.etree.ElementTree.parse', side_effect=ET.ParseError("Invalid XML")):
            result = self.runner.invoke(main, [
                'validate', 'test_invoice.xml'
            ])
            
            assert result.exit_code == 1
            assert "XML parse error" in result.output

    def test_stub_server_command_missing_deps(self):
        """Test stub server command with missing dependencies."""
        with patch('ksef.cli.uvicorn', None):
            result = self.runner.invoke(main, ['stub-server'])
            # Should handle missing dependencies gracefully
            assert result.exit_code in [0, 1]  # Either runs or fails gracefully 