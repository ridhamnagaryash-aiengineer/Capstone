from unittest.mock import patch

@patch("src.vector_db.milvus_client.MilvusClient.search_similar", side_effect=Exception("Milvus down"))
def test_chat_milvus_error(search_mock, client):

    response = client.post("/employee/chat", json={"message": "leave policy"})

    assert response.status_code == 200

    data = response.json()

    # Expect fallback behaviour — NOT an "error" key
    assert "response" in data
    assert isinstance(data["response"], str)

    # Since Milvus crashed, retriever returns [] → sources MUST be empty
    assert data.get("sources", []) == []
