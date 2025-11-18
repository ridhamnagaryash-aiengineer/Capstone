from src.llm.lite_client import lite_client

def test_embedding():
    emb = lite_client.create_embedding("hello world")
    assert isinstance(emb, list)
    assert len(emb) > 100
