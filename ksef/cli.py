"""Command-line interface for ksef-py."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from ksef import KsefClient, __version__
from ksef.exceptions import KsefError
from ksef.models import InvoiceFormat, KsefEnvironment

console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    import logging

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """ksef-py: Modern Python SDK + CLI for Poland's National e-Invoice System (KSeF)"""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@main.command()
@click.argument("xml_file", type=click.Path(exists=True, path_type=Path))
@click.option("--nip", required=True, help="Company NIP number")
@click.option(
    "--env",
    type=click.Choice(["test", "prod"]),
    default="test",
    help="KSeF environment",
)
@click.option(
    "--token-path", type=click.Path(path_type=Path), help="Path to JWT token file"
)
@click.option("--output", "-o", help="Output format (default: show KSeF number)")
@click.pass_context
def send(
    ctx: click.Context,
    xml_file: Path,
    nip: str,
    env: str,
    token_path: Optional[Path],
    output: Optional[str],
) -> None:
    """Send an invoice XML file to KSeF."""

    async def _send_invoice() -> None:
        try:
            # Read XML file
            console.print(f"📄 Reading invoice: {xml_file}")
            xml_content = xml_file.read_text(encoding="utf-8")

            # Initialize client
            client = KsefClient(
                nip=nip,
                env=KsefEnvironment(env),
                token_path=token_path,
            )

            # Send invoice with progress indicator
            with Progress() as progress:
                task = progress.add_task("Sending invoice...", total=None)

                async with client:
                    ksef_number = await client.send_invoice(
                        xml_content, filename=xml_file.name
                    )

                progress.update(task, completed=True)

            # Display result
            console.print("✅ Invoice sent successfully!")
            console.print(f"🆔 KSeF Number: [bold green]{ksef_number}[/bold green]")

            # Output to file if requested
            if output:
                Path(output).write_text(ksef_number)
                console.print(f"💾 KSeF number saved to: {output}")

        except KsefError as e:
            console.print(f"❌ KSeF Error: {e}", style="red")
            if ctx.obj.get("verbose") and e.details:
                console.print(f"Details: {e.details}")
            sys.exit(1)
        except Exception as e:
            console.print(f"💥 Unexpected error: {e}", style="red")
            if ctx.obj.get("verbose"):
                import traceback

                console.print(traceback.format_exc())
            sys.exit(1)

    asyncio.run(_send_invoice())


@main.command()
@click.argument("ksef_number")
@click.option("--nip", required=True, help="Company NIP number")
@click.option(
    "--env",
    type=click.Choice(["test", "prod"]),
    default="test",
    help="KSeF environment",
)
@click.option(
    "--token-path", type=click.Path(path_type=Path), help="Path to JWT token file"
)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def status(
    ctx: click.Context,
    ksef_number: str,
    nip: str,
    env: str,
    token_path: Optional[Path],
    output_json: bool,
) -> None:
    """Check the status of an invoice by KSeF number."""

    async def _check_status() -> None:
        try:
            client = KsefClient(
                nip=nip,
                env=KsefEnvironment(env),
                token_path=token_path,
            )

            async with client:
                invoice_status = await client.get_status(ksef_number)

            if output_json:
                import json

                result = {
                    "ksef_number": ksef_number,
                    "status": invoice_status.value,
                    "timestamp": "2025-01-01T00:00:00Z",  # Would be from actual response
                }
                console.print(json.dumps(result, indent=2))
            else:
                # Create a nice table
                table = Table(title="Invoice Status")
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="green")

                table.add_row("KSeF Number", ksef_number)
                table.add_row("Status", invoice_status.value)

                console.print(table)

        except KsefError as e:
            console.print(f"❌ KSeF Error: {e}", style="red")
            if ctx.obj.get("verbose") and e.details:
                console.print(f"Details: {e.details}")
            sys.exit(1)
        except Exception as e:
            console.print(f"💥 Unexpected error: {e}", style="red")
            if ctx.obj.get("verbose"):
                import traceback

                console.print(traceback.format_exc())
            sys.exit(1)

    asyncio.run(_check_status())


@main.command()
@click.argument("ksef_number")
@click.option("--nip", required=True, help="Company NIP number")
@click.option(
    "--env",
    type=click.Choice(["test", "prod"]),
    default="test",
    help="KSeF environment",
)
@click.option(
    "--token-path", type=click.Path(path_type=Path), help="Path to JWT token file"
)
@click.option(
    "--format",
    "download_format",
    type=click.Choice(["pdf", "xml"]),
    default="pdf",
    help="Download format",
)
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), help="Output file path"
)
@click.pass_context
def download(
    ctx: click.Context,
    ksef_number: str,
    nip: str,
    env: str,
    token_path: Optional[Path],
    download_format: str,
    output: Optional[Path],
) -> None:
    """Download an invoice by KSeF number."""

    async def _download_invoice() -> None:
        try:
            client = KsefClient(
                nip=nip,
                env=KsefEnvironment(env),
                token_path=token_path,
            )

            with Progress() as progress:
                task = progress.add_task("Downloading invoice...", total=None)

                async with client:
                    file_path = await client.download(
                        ksef_number,
                        format=InvoiceFormat(download_format),
                        output_path=output,
                    )

                progress.update(task, completed=True)

            console.print("✅ Invoice downloaded successfully!")
            console.print(f"📁 File saved to: [bold green]{file_path}[/bold green]")
            console.print(f"📊 Size: {file_path.stat().st_size:,} bytes")

        except KsefError as e:
            console.print(f"❌ KSeF Error: {e}", style="red")
            if ctx.obj.get("verbose") and e.details:
                console.print(f"Details: {e.details}")
            sys.exit(1)
        except Exception as e:
            console.print(f"💥 Unexpected error: {e}", style="red")
            if ctx.obj.get("verbose"):
                import traceback

                console.print(traceback.format_exc())
            sys.exit(1)

    asyncio.run(_download_invoice())


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
@click.pass_context
def stub_server(ctx: click.Context, host: str, port: int) -> None:
    """Start a local stub server for testing."""
    try:
        # Import here to avoid dependency issues if not using stub server
        import uvicorn

        from ksef.stub_server import create_app

        console.print(f"🚀 Starting KSeF stub server on {host}:{port}")
        console.print("📚 Available endpoints:")
        console.print("  POST /v1/auth/token - Generate test token")
        console.print("  POST /v1/invoices/send - Send invoice (mock)")
        console.print("  GET /v1/invoices/{id}/status - Check status (mock)")
        console.print("  GET /v1/invoices/{id}/download - Download invoice (mock)")
        console.print("\n🛑 Press Ctrl+C to stop")

        app = create_app()
        uvicorn.run(app, host=host, port=port, log_level="info")

    except ImportError:
        console.print("❌ Stub server dependencies not installed", style="red")
        console.print("Run: pip install 'ksef-py[dev]' to enable stub server")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n👋 Stub server stopped")


@main.command()
@click.argument("xml_file", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def validate(ctx: click.Context, xml_file: Path) -> None:
    """Validate an invoice XML file against KSeF schema."""
    try:
        # This would validate against the official XSD schema
        console.print(f"🔍 Validating: {xml_file}")

        # For now, just check if it's valid XML
        import xml.etree.ElementTree as ET

        try:
            ET.parse(xml_file)
            console.print("✅ XML is well-formed")
        except ET.ParseError as e:
            console.print(f"❌ XML parse error: {e}", style="red")
            sys.exit(1)

        # TODO: Add proper XSD validation
        console.print("⚠️  Full XSD validation not yet implemented")
        console.print("🔧 Coming in next version!")

    except Exception as e:
        console.print(f"💥 Validation error: {e}", style="red")
        if ctx.obj.get("verbose"):
            import traceback

            console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
