"""
ksef-py: Modern Python SDK + CLI for Poland's National e-Invoice System (KSeF)

A modern, async-first Python SDK and CLI tool for integrating with Poland's
National e-Invoice System (KSeF). Supports both REST and SOAP endpoints with
strong typing and comprehensive error handling.

Basic usage:
    >>> from ksef import KsefClient
    >>> client = KsefClient(nip="1234567890", env="test")
    >>> ksef_nr = client.send_invoice(xml_content)
"""

from ksef.client import KsefClient
from ksef.exceptions import (
    KsefAuthenticationError,
    KsefError,
    KsefNetworkError,
    KsefValidationError,
)
from ksef.models import InvoiceStatus, KsefEnvironment

__version__ = "0.0.1a1"
__all__ = [
    "KsefClient",
    "KsefEnvironment",
    "InvoiceStatus",
    "KsefError",
    "KsefAuthenticationError",
    "KsefValidationError",
    "KsefNetworkError",
]
