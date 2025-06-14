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
    def test_send_command_success(self, mock_client_class):
        """Test successful send command."""
        # Mock client
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.send_invoice.return_value = "KSEF:2025:PL/123/ABC"
        mock_client_class.return_value = mock_client
        
        # Create a real temporary file for Click to validate
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as tmp:
            tmp.write("<invoice>test</invoice>")
            tmp_path = tmp.name
        
        try:
            result = self.runner.invoke(main, [
                'send', tmp_path,
                '--nip', '1234567890'
            ])
        finally:
            # Clean up temp file
            import os
            os.unlink(tmp_path)
        
        # Should complete successfully
        assert result.exit_code == 0

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
        
        # Create a mock Path object with stat() method
        mock_path = MagicMock(spec=Path)
        mock_stat = MagicMock()
        mock_stat.st_size = 1024  # Mock file size
        mock_path.stat.return_value = mock_stat
        mock_path.__str__.return_value = "test.pdf"
        
        mock_client.download.return_value = mock_path
        mock_client_class.return_value = mock_client
        
        result = self.runner.invoke(main, [
            'download', 'KSEF:2025:PL/123/ABC',
            '--nip', '1234567890'
        ])
        
        assert result.exit_code == 0

    def test_validate_command_success(self):
        """Test successful validate command."""
        with patch('xml.etree.ElementTree.parse') as mock_parse:
            mock_parse.return_value = MagicMock()
            
            # Create a real temporary file for Click to validate
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as tmp:
                tmp.write("<invoice>test</invoice>")
                tmp_path = tmp.name
            
            try:
                result = self.runner.invoke(main, [
                    'validate', tmp_path
                ])
            finally:
                # Clean up temp file
                import os
                os.unlink(tmp_path)
            
            assert result.exit_code == 0
            assert "XML is well-formed" in result.output

    def test_validate_command_invalid_xml(self):
        """Test validate command with invalid XML."""
        import xml.etree.ElementTree as ET
        with patch('xml.etree.ElementTree.parse', side_effect=ET.ParseError("Invalid XML")):
            
            # Create a real temporary file for Click to validate
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as tmp:
                tmp.write("<invalid>xml")  # Invalid XML
                tmp_path = tmp.name
            
            try:
                result = self.runner.invoke(main, [
                    'validate', tmp_path
                ])
            finally:
                # Clean up temp file
                import os
                os.unlink(tmp_path)
            
            assert result.exit_code == 1
            assert "XML parse error" in result.output

    def test_stub_server_command_help(self):
        """Test stub server command shows in help."""
        result = self.runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert "stub-server" in result.output 