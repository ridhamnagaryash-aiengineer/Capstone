from unittest.mock import patch
from types import SimpleNamespace

def test_upload_document(client):

    fake_file = ("test.pdf", b"hello world", "application/pdf")

    with patch("src.services.document_service.DocumentService._upload_to_s3") as s3_mock, \
         patch("src.services.document_service.DocumentService._create_document_record") as db_mock:

        s3_mock.return_value = ("documents/123.pdf", 1000)

        db_mock.return_value = SimpleNamespace(
            id=1,
            file_id="123",
            filename="test.pdf",
            original_filename="test.pdf",
            s3_url="https://fake-s3.com/123.pdf",
            s3_key="documents/123.pdf",
            file_size=1000,
            content_type="application/pdf",
            vector_count=0,
            uploaded_by_id=1,
            uploaded_at="2025-01-01T00:00:00Z",
            processing_status="pending",
            error_message=None
        )

        response = client.post(
            "/admin/documents",
            files={"file": fake_file}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["filename"] == "test.pdf"
