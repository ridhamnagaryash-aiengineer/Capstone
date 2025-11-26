from unittest.mock import patch

@patch("src.vector_db.milvus_client.MilvusClient.search_similar", return_value=[])
@patch("src.llm.lite_client.lite_client.chat_completion", return_value="fallback answer")
@patch("src.llm.lite_client.lite_client.create_embedding", return_value=[0.1, 0.2, 0.3])
def test_chat_no_docs(embed_mock, chat_mock, search_mock, client):

    response = client.post("/employee/chat", json={"message": "random"})

    assert response.status_code == 200
    assert response.json()["response"] == "fallback answer"
