"""Main KSeF client implementation."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Union

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ksef.exceptions import (
    KsefAuthenticationError,
    KsefError,
    KsefNetworkError,
    KsefServerError,
    KsefTimeoutError,
    KsefValidationError,
)
from ksef.models import (
    KSEF_CONFIGS,
    InvoiceFormat,
    InvoiceSendRequest,
    InvoiceStatus,
    KsefConfiguration,
    KsefCredentials,
    KsefEnvironment,
    SessionInfo,
    TokenResponse,
)

logger = logging.getLogger(__name__)


class KsefClient:
    """
    Modern async-first client for Poland's National e-Invoice System (KSeF).

    Supports both REST and SOAP endpoints with automatic token management,
    retry logic, and comprehensive error handling.

    Example:
        >>> client = KsefClient(nip="1234567890", env="test")
        >>> ksef_nr = await client.send_invoice(xml_content)
        >>> status = await client.get_status(ksef_nr)
        >>> pdf_path = await client.download(ksef_nr, format="pdf")
    """

    def __init__(
        self,
        nip: str,
        env: Union[str, KsefEnvironment] = KsefEnvironment.TEST,
        token_path: Optional[Union[str, Path]] = None,
        private_key_path: Optional[Union[str, Path]] = None,
        certificate_path: Optional[Union[str, Path]] = None,
        config: Optional[KsefConfiguration] = None,
    ) -> None:
        """
        Initialize KSeF client.

        Args:
            nip: Company NIP number (10 digits)
            env: Environment ("test" or "prod")
            token_path: Path to JWT token file for token-based auth
            private_key_path: Path to private key for challenge-file auth
            certificate_path: Path to certificate for challenge-file auth
            config: Custom configuration (optional)
        """
        self.credentials = KsefCredentials(
            nip=nip,
            environment=KsefEnvironment(env) if isinstance(env, str) else env,
            token_path=str(token_path) if token_path else None,
            private_key_path=str(private_key_path) if private_key_path else None,
            certificate_path=str(certificate_path) if certificate_path else None,
        )

        self.config = config or KSEF_CONFIGS[self.credentials.environment]
        self.session_info = SessionInfo(
            environment=self.credentials.environment,
            nip=self.credentials.nip,
        )

        # HTTP clients (will be initialized on first use)
        self._async_client: Optional[httpx.AsyncClient] = None
        self._sync_client: Optional[httpx.Client] = None

        # Token management
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

        logger.info(
            f"Initialized KSeF client for NIP {self.credentials.nip} "
            f"in {self.credentials.environment.value} environment"
        )

    @property
    def async_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                headers={
                    "User-Agent": self.config.user_agent,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._async_client

    @property
    def sync_client(self) -> httpx.Client:
        """Get or create sync HTTP client."""
        if self._sync_client is None:
            self._sync_client = httpx.Client(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                headers={
                    "User-Agent": self.config.user_agent,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._sync_client

    def _load_token_from_file(self) -> Optional[str]:
        """Load token from file if token_path is configured."""
        if not self.credentials.token_path:
            return None

        token_path = Path(self.credentials.token_path)
        if not token_path.exists():
            logger.warning(f"Token file not found: {token_path}")
            return None

        try:
            token_data = json.loads(token_path.read_text())
            expires_at = datetime.fromisoformat(token_data["expires_at"])

            # Check if token is still valid (with 5 minute buffer)
            if expires_at > datetime.now() + timedelta(minutes=5):
                self._token = token_data["token"]
                self._token_expires_at = expires_at
                logger.info("Loaded valid token from file")
                return self._token
            else:
                logger.info("Token in file has expired")

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to load token from file: {e}")

        return None

    def _save_token_to_file(self, token: str, expires_at: datetime) -> None:
        """Save token to file if token_path is configured."""
        if not self.credentials.token_path:
            return

        token_path = Path(self.credentials.token_path)
        token_path.parent.mkdir(parents=True, exist_ok=True)

        token_data = {
            "token": token,
            "expires_at": expires_at.isoformat(),
            "nip": self.credentials.nip,
            "environment": self.credentials.environment.value,
        }

        token_path.write_text(json.dumps(token_data, indent=2))
        logger.info(f"Saved token to file: {token_path}")

    async def _ensure_token(self) -> str:
        """Ensure we have a valid authentication token."""
        # Try to load existing token
        if not self._token:
            self._load_token_from_file()

        # Check if current token is still valid
        if (
            self._token
            and self._token_expires_at
            and self._token_expires_at > datetime.now() + timedelta(minutes=5)
        ):
            return self._token

        # Generate new token
        logger.info("Generating new authentication token")
        token_response = await self.generate_token()

        self._token = token_response.token
        self._token_expires_at = token_response.expires_at

        # Save to file if configured
        self._save_token_to_file(self._token, self._token_expires_at)

        return self._token

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def generate_token(self) -> TokenResponse:
        """
        Generate authentication token from KSeF API.

        Returns:
            TokenResponse with token and expiration info

        Raises:
            KsefAuthenticationError: If authentication fails
            KsefNetworkError: If network request fails
        """
        try:
            response = await self.async_client.post(
                "/v1/auth/token",
                json={
                    "nip": self.credentials.nip,
                    "environment": self.credentials.environment.value,
                },
            )

            if response.status_code == 200:
                data = response.json()
                return TokenResponse(
                    token=data["token"],
                    expires_at=datetime.fromisoformat(data["expires_at"]),
                    session_token=data.get("session_token"),
                )
            elif response.status_code == 401:
                raise KsefAuthenticationError(
                    "Authentication failed - invalid credentials",
                    details=response.json() if response.content else {},
                )
            else:
                raise KsefServerError(
                    f"Token generation failed with status {response.status_code}",
                    details=response.json() if response.content else {},
                )

        except httpx.TimeoutException as e:
            raise KsefTimeoutError(f"Token generation timed out: {e}") from e
        except httpx.RequestError as e:
            raise KsefNetworkError(f"Network error during token generation: {e}") from e

    async def send_invoice(
        self, xml_content: str, filename: Optional[str] = None
    ) -> str:
        """
        Send invoice to KSeF system.

        Args:
            xml_content: Invoice XML content
            filename: Original filename (optional)

        Returns:
            KSeF number assigned to the invoice

        Raises:
            KsefValidationError: If XML validation fails
            KsefAuthenticationError: If authentication fails
            KsefNetworkError: If network request fails
        """
        token = await self._ensure_token()

        request_data = InvoiceSendRequest(
            xml_content=xml_content,
            filename=filename,
        )

        try:
            response = await self.async_client.post(
                "/v1/invoices/send",
                json=request_data.model_dump(),
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code == 201:
                data = response.json()
                ksef_number: str = data["ksef_number"]
                logger.info(f"Invoice sent successfully: {ksef_number}")
                return ksef_number
            elif response.status_code == 400:
                raise KsefValidationError(
                    "Invoice validation failed",
                    details=response.json() if response.content else {},
                )
            elif response.status_code == 401:
                raise KsefAuthenticationError(
                    "Authentication failed - token may be invalid",
                )
            else:
                raise KsefServerError(
                    f"Invoice send failed with status {response.status_code}",
                    details=response.json() if response.content else {},
                )

        except httpx.TimeoutException as e:
            raise KsefTimeoutError(f"Invoice send timed out: {e}") from e
        except httpx.RequestError as e:
            raise KsefNetworkError(f"Network error during invoice send: {e}") from e

    async def get_status(self, ksef_number: str) -> InvoiceStatus:
        """
        Get status of an invoice by KSeF number.

        Args:
            ksef_number: KSeF number to check

        Returns:
            Current status of the invoice

        Raises:
            KsefAuthenticationError: If authentication fails
            KsefNetworkError: If network request fails
        """
        token = await self._ensure_token()

        try:
            response = await self.async_client.get(
                f"/v1/invoices/{ksef_number}/status",
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code == 200:
                data = response.json()
                status = InvoiceStatus(data["status"])
                logger.info(f"Status for {ksef_number}: {status.value}")
                return status
            elif response.status_code == 404:
                raise KsefError(f"Invoice not found: {ksef_number}")
            elif response.status_code == 401:
                raise KsefAuthenticationError("Authentication failed")
            else:
                raise KsefServerError(
                    f"Status check failed with status {response.status_code}",
                    details=response.json() if response.content else {},
                )

        except httpx.TimeoutException as e:
            raise KsefTimeoutError(f"Status check timed out: {e}") from e
        except httpx.RequestError as e:
            raise KsefNetworkError(f"Network error during status check: {e}") from e

    async def download(
        self,
        ksef_number: str,
        format: Union[str, InvoiceFormat] = InvoiceFormat.PDF,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """
        Download invoice from KSeF system.

        Args:
            ksef_number: KSeF number to download
            format: Download format ("pdf" or "xml")
            output_path: Where to save the file (optional)

        Returns:
            Path to the downloaded file

        Raises:
            KsefAuthenticationError: If authentication fails
            KsefNetworkError: If network request fails
        """
        token = await self._ensure_token()
        invoice_format = InvoiceFormat(format) if isinstance(format, str) else format

        try:
            response = await self.async_client.get(
                f"/v1/invoices/{ksef_number}/download",
                params={"format": invoice_format.value},
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code == 200:
                # Determine output path
                if output_path is None:
                    extension = "pdf" if invoice_format == InvoiceFormat.PDF else "xml"
                    output_path = Path(f"{ksef_number}.{extension}")
                else:
                    output_path = Path(output_path)

                # Save file
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(response.content)

                logger.info(f"Downloaded {ksef_number} to {output_path}")
                return output_path

            elif response.status_code == 404:
                raise KsefError(f"Invoice not found: {ksef_number}")
            elif response.status_code == 401:
                raise KsefAuthenticationError("Authentication failed")
            else:
                raise KsefServerError(
                    f"Download failed with status {response.status_code}",
                    details=response.json() if response.content else {},
                )

        except httpx.TimeoutException as e:
            raise KsefTimeoutError(f"Download timed out: {e}") from e
        except httpx.RequestError as e:
            raise KsefNetworkError(f"Network error during download: {e}") from e

    # Sync wrapper methods
    def send_invoice_sync(
        self, xml_content: str, filename: Optional[str] = None
    ) -> str:
        """Synchronous version of send_invoice."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            return asyncio.run(self.send_invoice(xml_content, filename))
        else:
            # Event loop is running, need to run in thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, self.send_invoice(xml_content, filename)
                )
                return future.result()

    def get_status_sync(self, ksef_number: str) -> InvoiceStatus:
        """Synchronous version of get_status."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            return asyncio.run(self.get_status(ksef_number))
        else:
            # Event loop is running, need to run in thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.get_status(ksef_number))
                return future.result()

    def download_sync(
        self,
        ksef_number: str,
        format: Union[str, InvoiceFormat] = InvoiceFormat.PDF,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Synchronous version of download."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            return asyncio.run(self.download(ksef_number, format, output_path))
        else:
            # Event loop is running, need to run in thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, self.download(ksef_number, format, output_path)
                )
                return future.result()

    async def close(self) -> None:
        """Close HTTP clients and clean up resources."""
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None

        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None

        logger.info("KSeF client closed")

    def __enter__(self) -> "KsefClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        if self._sync_client:
            self._sync_client.close()

    async def __aenter__(self) -> "KsefClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
