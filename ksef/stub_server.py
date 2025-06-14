"""FastAPI-based stub server for KSeF API testing."""

import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

# Module-level storage that persists across requests
_invoices_store: dict[str, dict[str, Any]] = {}


def clear_storage() -> None:
    """Clear the invoice storage. Useful for testing."""
    global _invoices_store
    _invoices_store.clear()


class TokenRequest(BaseModel):
    """Token generation request."""

    nip: str
    environment: str


class InvoiceRequest(BaseModel):
    """Invoice send request."""

    xml_content: str
    filename: Optional[str] = None
    encoding: str = "UTF-8"


def create_app() -> FastAPI:
    """Create and configure FastAPI app."""
    app = FastAPI(
        title="KSeF Stub Server",
        description="Mock implementation of KSeF API for testing",
        version="1.0.0",
    )

    @app.get("/")
    async def root() -> dict[str, Any]:
        """Root endpoint with API information."""
        return {
            "name": "KSeF Stub Server",
            "version": "1.0.0",
            "description": "Mock KSeF API for testing ksef-py",
            "endpoints": {
                "auth": "/v1/auth/token",
                "send": "/v1/invoices/send",
                "status": "/v1/invoices/{ksef_number}/status",
                "download": "/v1/invoices/{ksef_number}/download",
            },
        }

    @app.post("/v1/auth/token")
    async def generate_token(request: TokenRequest) -> dict[str, str]:
        """Mock token generation endpoint."""
        if len(request.nip) != 10 or not request.nip.isdigit():
            raise HTTPException(status_code=400, detail="Invalid NIP format")

        if request.environment not in ["test", "prod"]:
            raise HTTPException(status_code=400, detail="Invalid environment")

        # Generate mock JWT token
        token = f"mock.jwt.token.{uuid.uuid4().hex[:16]}"
        expires_at = datetime.now() + timedelta(hours=1)

        return {
            "token": token,
            "expires_at": expires_at.isoformat(),
            "session_token": f"session_{uuid.uuid4().hex[:8]}",
        }

    @app.post("/v1/invoices/send")
    async def send_invoice(
        invoice_request: InvoiceRequest,
        authorization: str = Header(...),
    ) -> dict[str, str]:
        """Mock invoice send endpoint."""
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")

        token = authorization.replace("Bearer ", "")
        if not token.startswith("mock.jwt.token"):
            raise HTTPException(status_code=401, detail="Invalid token")

        # Validate basic XML structure
        if not invoice_request.xml_content.strip().startswith("<?xml"):
            raise HTTPException(status_code=400, detail="Invalid XML format")

        # Generate mock KSeF number
        ksef_number = f"KSEF:2025:PL/{uuid.uuid4().hex[:10].upper()}"

        # Store invoice data in module-level storage
        _invoices_store[ksef_number] = {
            "xml_content": invoice_request.xml_content,
            "filename": invoice_request.filename,
            "status": "Accepted",
            "timestamp": datetime.now().isoformat(),
            "processing_code": "200",
            "processing_description": "Invoice processed successfully",
        }

        return {
            "ksef_number": ksef_number,
            "timestamp": datetime.now().isoformat(),
            "processing_code": "200",
            "processing_description": "Invoice submitted successfully",
        }

    @app.get("/v1/invoices/{ksef_number:path}/status")
    async def get_invoice_status(
        ksef_number: str,
        authorization: str = Header(...),
    ) -> dict[str, Any]:
        """Mock invoice status endpoint."""
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")

        if ksef_number not in _invoices_store:
            raise HTTPException(status_code=404, detail="Invoice not found")

        invoice_data = _invoices_store[ksef_number]

        return {
            "ksef_number": ksef_number,
            "status": invoice_data["status"],
            "timestamp": invoice_data["timestamp"],
            "processing_code": invoice_data.get("processing_code"),
            "processing_description": invoice_data.get("processing_description"),
            "acquisition_timestamp": invoice_data["timestamp"],
            "download_url": f"/v1/invoices/{ksef_number}/download",
        }

    @app.get("/v1/invoices/{ksef_number:path}/download")
    async def download_invoice(
        ksef_number: str,
        format: str = "pdf",
        authorization: str = Header(...),
    ) -> Response:
        """Mock invoice download endpoint."""
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")

        if ksef_number not in _invoices_store:
            raise HTTPException(status_code=404, detail="Invoice not found")

        if format not in ["pdf", "xml"]:
            raise HTTPException(status_code=400, detail="Invalid format")

        invoice_data = _invoices_store[ksef_number]

        if format == "xml":
            content = invoice_data["xml_content"].encode("utf-8")
            media_type = "application/xml"
            filename = f"{ksef_number}.xml"
        else:
            # Mock PDF content
            content = (
                b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
            )
            content += f"Mock PDF content for {ksef_number}".encode()
            media_type = "application/pdf"
            filename = f"{ksef_number}.pdf"

        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(content)),
            },
        )

    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "invoices_count": len(_invoices_store),
        }

    return app


if __name__ == "__main__":
    import uvicorn

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
