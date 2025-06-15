#!/usr/bin/env python3
"""
Script to update KSeF XSD schemas from the official Ministry of Finance sources.

This script downloads the latest XSD schemas and generates Pydantic models
from them for use in the ksef-py SDK.
"""

import asyncio
import hashlib
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress, TaskID

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()

# Official KSeF schema sources
SCHEMA_URLS = {
    "test": {
        "base_url": "https://ksef-test.mf.gov.pl",
        "schema_paths": [
            "/static/schemas/KSeF_v1.0.xsd",
            "/static/schemas/FA_v1-0E.xsd",
        ],
    },
    "prod": {
        "base_url": "https://ksef.mf.gov.pl",
        "schema_paths": [
            "/static/schemas/KSeF_v1.0.xsd",
            "/static/schemas/FA_v1-0E.xsd",
        ],
    },
}

# Output directories
PROJECT_ROOT = Path(__file__).parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "ksef" / "xsd"
GENERATED_MODELS_DIR = PROJECT_ROOT / "ksef" / "generated"


async def download_schema(
    session: httpx.AsyncClient,
    base_url: str,
    schema_path: str,
    progress: Progress,
    task_id: TaskID,
) -> tuple[str, bytes] | None:
    """Download a single schema file."""
    url = f"{base_url}{schema_path}"
    filename = Path(schema_path).name

    try:
        progress.update(task_id, description=f"Downloading {filename}...")
        response = await session.get(url)
        response.raise_for_status()

        content = response.content
        progress.update(task_id, advance=1, description=f"Downloaded {filename}")

        return filename, content

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"Schema not found (404): {url}")
            progress.update(task_id, advance=1, description=f"Not found: {filename}")
            return None
        else:
            logger.error(f"HTTP error downloading {url}: {e}")
            raise
    except httpx.RequestError as e:
        logger.error(f"Failed to download {url}: {e}")
        raise


async def download_all_schemas(env: str = "test") -> dict[str, bytes]:
    """Download all schemas for a given environment."""
    config = SCHEMA_URLS[env]
    schemas = {}

    async with httpx.AsyncClient(timeout=30.0) as session:
        with Progress() as progress:
            tasks = []

            for schema_path in config["schema_paths"]:
                task_id = progress.add_task(
                    f"Downloading {Path(schema_path).name}", total=1
                )
                tasks.append((schema_path, task_id))

            # Download all schemas concurrently
            download_tasks = [
                download_schema(
                    session, config["base_url"], schema_path, progress, task_id
                )
                for schema_path, task_id in tasks
            ]

            results = await asyncio.gather(*download_tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Download failed: {result}")
                    continue
                elif result is not None:
                    filename, content = result
                    schemas[filename] = content

    return schemas


def validate_schema(content: bytes) -> bool:
    """Validate that the downloaded content is valid XML/XSD."""
    try:
        ET.fromstring(content)
        return True
    except ET.ParseError as e:
        logger.error(f"Invalid XML schema: {e}")
        return False


def calculate_checksum(content: bytes) -> str:
    """Calculate SHA256 checksum of content."""
    return hashlib.sha256(content).hexdigest()


def save_schemas(schemas: dict[str, bytes], env: str) -> None:
    """Save schemas to the appropriate directories."""
    env_dir = SCHEMAS_DIR / env
    env_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "environment": env,
        "updated_at": "2025-01-01T00:00:00Z",  # Would use actual timestamp
        "schemas": {},
    }

    for filename, content in schemas.items():
        if not validate_schema(content):
            logger.error(f"Skipping invalid schema: {filename}")
            continue

        # Save schema file
        schema_path = env_dir / filename
        schema_path.write_bytes(content)

        # Add to manifest
        manifest["schemas"][filename] = {
            "path": str(schema_path.relative_to(PROJECT_ROOT)),
            "checksum": calculate_checksum(content),
            "size": len(content),
        }

        console.print(f"✅ Saved {filename} ({len(content):,} bytes)")

    # Save manifest
    manifest_path = env_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    console.print(f"📄 Saved manifest: {manifest_path}")


def generate_pydantic_models(schemas: dict[str, bytes]) -> None:
    """Generate Pydantic models from XSD schemas."""
    # This is a placeholder for XSD -> Pydantic model generation
    # In a real implementation, you'd use a library like xsdata or write
    # custom XSD parsing logic

    GENERATED_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Create a simple generated models file for now
    generated_content = '''"""
Generated Pydantic models from KSeF XSD schemas.

This file is automatically generated by scripts/update_schemas.py
Do not edit manually.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class GeneratedKsefModels:
    """Placeholder for generated models from XSD schemas."""

    # TODO: Implement XSD -> Pydantic model generation
    # This would include models for:
    # - Invoice structures
    # - Response formats
    # - Error codes
    # - Reference data types
    pass


# Auto-generated model classes would be defined here
class InvoiceHeaderGenerated(BaseModel):
    """Generated from XSD schema - Invoice header structure."""

    invoice_number: str = Field(..., description="Invoice number")
    issue_date: datetime = Field(..., description="Issue date")
    # ... more fields from XSD


class SellerInfoGenerated(BaseModel):
    """Generated from XSD schema - Seller information."""

    tax_id: str = Field(..., description="Tax identification number")
    name: str = Field(..., description="Company name")
    # ... more fields from XSD
'''

    models_file = GENERATED_MODELS_DIR / "__init__.py"
    models_file.write_text(generated_content)

    console.print(f"🔧 Generated models placeholder: {models_file}")
    console.print("⚠️  Full XSD -> Pydantic generation not yet implemented")


async def main():
    """Main script entry point."""
    console.print("🔄 Updating KSeF schemas from official sources...")

    try:
        # Download schemas for both environments
        downloaded_any = False
        
        for env in ["test", "prod"]:
            console.print(f"\n📥 Downloading {env.upper()} environment schemas...")

            schemas = await download_all_schemas(env)

            if not schemas:
                console.print(f"⚠️  No schemas available for {env} environment", style="yellow")
                console.print("   This may be due to:")
                console.print("   - URLs have changed")
                console.print("   - Schemas not publicly available")
                console.print("   - Network issues")
                
                # Create placeholder schemas for development
                create_placeholder_schemas(env)
                continue

            console.print(f"✅ Downloaded {len(schemas)} schemas for {env}")
            downloaded_any = True

            # Save schemas
            save_schemas(schemas, env)

            # Generate models (only once, using test schemas)
            if env == "test":
                console.print("\n🏗️  Generating Pydantic models...")
                generate_pydantic_models(schemas)

        if not downloaded_any:
            console.print("\n📝 Created placeholder schemas for development")
            console.print("   You can manually add real schemas to ksef/xsd/ when available")

        console.print("\n🎉 Schema update process completed!")
        console.print("📝 Next steps:")
        console.print("  1. Review schemas in ksef/xsd/")
        console.print("  2. Add real KSeF schemas when URLs are available")
        console.print("  3. Implement full XSD -> Pydantic generation")
        console.print("  4. Run tests to ensure compatibility")

    except Exception as e:
        console.print(f"💥 Schema update failed: {e}", style="red")
        # Don't re-raise the exception, just log it
        logger.exception("Schema update failed")
        console.print("⚠️  Continuing with existing/placeholder schemas")


def create_placeholder_schemas(env: str) -> None:
    """Create placeholder schemas for development when real ones aren't available."""
    env_dir = SCHEMAS_DIR / env
    env_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a basic placeholder XSD
    placeholder_xsd = '''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="http://ksef.mf.gov.pl/"
           elementFormDefault="qualified">
    
    <!-- Placeholder KSeF Schema -->
    <!-- This is a development placeholder until real schemas are available -->
    
    <xs:element name="Invoice">
        <xs:complexType>
            <xs:sequence>
                <xs:element name="InvoiceNumber" type="xs:string"/>
                <xs:element name="IssueDate" type="xs:date"/>
                <xs:element name="Seller" type="SellerType"/>
                <xs:element name="Buyer" type="BuyerType"/>
            </xs:sequence>
        </xs:complexType>
    </xs:element>
    
    <xs:complexType name="SellerType">
        <xs:sequence>
            <xs:element name="TaxID" type="xs:string"/>
            <xs:element name="Name" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    
    <xs:complexType name="BuyerType">
        <xs:sequence>
            <xs:element name="TaxID" type="xs:string"/>
            <xs:element name="Name" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    
</xs:schema>'''

    # Save placeholder schemas
    for schema_name in ["KSeF_v1.0.xsd", "FA_v1-0E.xsd"]:
        schema_path = env_dir / schema_name
        schema_path.write_text(placeholder_xsd)
        console.print(f"📝 Created placeholder: {schema_path}")
    
    # Create manifest
    manifest = {
        "environment": env,
        "updated_at": "2025-01-01T00:00:00Z",
        "schemas": {
            schema_name: {
                "path": str((env_dir / schema_name).relative_to(PROJECT_ROOT)),
                "checksum": calculate_checksum(placeholder_xsd.encode()),
                "size": len(placeholder_xsd.encode()),
                "type": "placeholder"
            }
            for schema_name in ["KSeF_v1.0.xsd", "FA_v1-0E.xsd"]
        },
        "note": "These are placeholder schemas for development. Replace with real KSeF schemas when available."
    }
    
    manifest_path = env_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    console.print(f"📄 Created manifest: {manifest_path}")


if __name__ == "__main__":
    asyncio.run(main())
