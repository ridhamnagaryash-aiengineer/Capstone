from unittest.mock import patch

@patch("src.vector_db.milvus_client.MilvusClient.search_similar")
@patch("src.llm.lite_client.lite_client.chat_completion")
@patch("src.llm.lite_client.lite_client.create_embedding")
def test_chat_query(embed_mock, chat_mock, search_mock, client):

    embed_mock.return_value = [0.1, 0.2, 0.3]

    search_mock.return_value = [
        {"filename": "policy.pdf", "content": "test content"}
    ]

    chat_mock.return_value = "This is the HR answer"

    response = client.post("/employee/chat", json={"message": "leave policy"})

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "This is the HR answer"
