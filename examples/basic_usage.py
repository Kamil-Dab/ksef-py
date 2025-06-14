#!/usr/bin/env python3
"""
Basic usage example for ksef-py SDK.

This example demonstrates the core functionality of the KSeF Python SDK.
"""

import asyncio
from pathlib import Path

from ksef import KsefClient
from ksef.exceptions import KsefError
from ksef.models import InvoiceFormat, KsefEnvironment

# Sample invoice XML (minimal structure for testing)
SAMPLE_INVOICE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="http://ksef.mf.gov.pl/schema/gtw/svc/types/2021/10/01/0001">
    <InvoiceHeader>
        <InvoiceNumber>FA/001/2025</InvoiceNumber>
        <IssueDate>2025-01-01</IssueDate>
        <Seller>
            <TaxId>1234567890</TaxId>
            <Name>Example Company Sp. z o.o.</Name>
            <Address>
                <Street>ul. Przykładowa 123</Street>
                <City>Warszawa</City>
                <PostalCode>00-001</PostalCode>
                <Country>PL</Country>
            </Address>
        </Seller>
        <Buyer>
            <TaxId>9876543210</TaxId>
            <Name>Customer Company Sp. z o.o.</Name>
            <Address>
                <Street>ul. Kliencka 456</Street>
                <City>Kraków</City>
                <PostalCode>30-001</PostalCode>
                <Country>PL</Country>
            </Address>
        </Buyer>
    </InvoiceHeader>
    <InvoiceBody>
        <Lines>
            <Line>
                <Description>Software License</Description>
                <Quantity>1</Quantity>
                <UnitPrice>1000.00</UnitPrice>
                <VATRate>23</VATRate>
                <VATAmount>230.00</VATAmount>
                <GrossAmount>1230.00</GrossAmount>
            </Line>
        </Lines>
        <Summary>
            <NetAmount>1000.00</NetAmount>
            <VATAmount>230.00</VATAmount>
            <GrossAmount>1230.00</GrossAmount>
            <Currency>PLN</Currency>
        </Summary>
    </InvoiceBody>
</Invoice>"""


async def basic_example():
    """Basic example of sending, checking status, and downloading an invoice."""
    print("🚀 KSeF-py Basic Usage Example")
    print("=" * 50)

    # Initialize the client
    print("\n1. Initializing KSeF client...")
    client = KsefClient(
        nip="1234567890",  # Your company's NIP
        env=KsefEnvironment.TEST,  # Use test environment
        token_path="~/.ksef/test_token.jwt",  # Optional: path to save JWT token
    )

    try:
        async with client:
            # Step 1: Send an invoice
            print("\n2. Sending invoice to KSeF...")
            ksef_number = await client.send_invoice(
                xml_content=SAMPLE_INVOICE_XML, filename="example_invoice.xml"
            )
            print("✅ Invoice sent successfully!")
            print(f"   KSeF Number: {ksef_number}")

            # Step 2: Check invoice status
            print("\n3. Checking invoice status...")
            status = await client.get_status(ksef_number)
            print(f"📊 Invoice Status: {status.value}")

            # Step 3: Download invoice as PDF
            print("\n4. Downloading invoice as PDF...")
            pdf_path = await client.download(
                ksef_number=ksef_number,
                format=InvoiceFormat.PDF,
                output_path=f"downloads/{ksef_number}.pdf",
            )
            print(f"💾 PDF saved to: {pdf_path}")

            # Step 4: Download invoice as XML
            print("\n5. Downloading invoice as XML...")
            xml_path = await client.download(
                ksef_number=ksef_number,
                format=InvoiceFormat.XML,
                output_path=f"downloads/{ksef_number}.xml",
            )
            print(f"💾 XML saved to: {xml_path}")

    except KsefError as e:
        print(f"❌ KSeF Error: {e}")
        if hasattr(e, "details") and e.details:
            print(f"   Details: {e.details}")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")

    print("\n✨ Example completed!")


async def synchronous_example():
    """Example using synchronous methods."""
    print("\n🔄 Synchronous API Example")
    print("=" * 50)

    client = KsefClient(nip="1234567890", env="test")

    try:
        # Using sync methods (these will run asyncio.run internally)
        print("\n1. Sending invoice (sync)...")
        ksef_number = client.send_invoice_sync(SAMPLE_INVOICE_XML)
        print(f"✅ KSeF Number: {ksef_number}")

        print("\n2. Checking status (sync)...")
        status = client.get_status_sync(ksef_number)
        print(f"📊 Status: {status.value}")

        print("\n3. Downloading PDF (sync)...")
        pdf_path = client.download_sync(ksef_number, format="pdf")
        print(f"💾 PDF saved to: {pdf_path}")

    except KsefError as e:
        print(f"❌ Error: {e}")


async def file_based_example():
    """Example reading invoice from a file."""
    print("\n📁 File-based Example")
    print("=" * 50)

    # Create a sample invoice file
    invoice_file = Path("sample_invoice.xml")
    invoice_file.write_text(SAMPLE_INVOICE_XML, encoding="utf-8")
    print(f"📝 Created sample invoice: {invoice_file}")

    # Read and send the invoice
    client = KsefClient(nip="1234567890", env="test")

    try:
        async with client:
            print("\n1. Reading invoice from file...")
            xml_content = invoice_file.read_text(encoding="utf-8")

            print("2. Sending invoice...")
            ksef_number = await client.send_invoice(
                xml_content=xml_content, filename=invoice_file.name
            )
            print(f"✅ Sent: {ksef_number}")

            print("3. Checking status...")
            status = await client.get_status(ksef_number)
            print(f"📊 Status: {status.value}")

    except KsefError as e:
        print(f"❌ Error: {e}")
    finally:
        # Clean up
        if invoice_file.exists():
            invoice_file.unlink()
            print(f"🗑️  Cleaned up: {invoice_file}")


async def error_handling_example():
    """Example demonstrating error handling."""
    print("\n⚠️  Error Handling Example")
    print("=" * 50)

    client = KsefClient(nip="1234567890", env="test")

    try:
        async with client:
            # Try to send invalid XML
            print("\n1. Sending invalid XML...")
            await client.send_invoice("<invalid>xml</invalid>")

    except KsefError as e:
        print(f"✅ Caught expected error: {e}")
        print(f"   Error type: {type(e).__name__}")
        if hasattr(e, "error_code") and e.error_code:
            print(f"   Error code: {e.error_code}")

    try:
        async with client:
            # Try to check status of non-existent invoice
            print("\n2. Checking status of non-existent invoice...")
            await client.get_status("KSEF:2025:PL/NONEXISTENT")

    except KsefError as e:
        print(f"✅ Caught expected error: {e}")


async def main():
    """Main example runner."""
    print("🇵🇱 KSeF-py SDK Examples")
    print("========================")
    print("This example demonstrates the core functionality of ksef-py.")
    print("Note: This uses mock data and the test environment.")

    # Create downloads directory
    Path("downloads").mkdir(exist_ok=True)

    # Run examples
    await basic_example()
    await synchronous_example()
    await file_based_example()
    await error_handling_example()

    print("\n🎉 All examples completed!")
    print("\nNext steps:")
    print("1. Get your real NIP and configure authentication")
    print("2. Switch to production environment when ready")
    print("3. Integrate into your business application")
    print("4. Check out the CLI tools: `ksef --help`")


if __name__ == "__main__":
    asyncio.run(main())
