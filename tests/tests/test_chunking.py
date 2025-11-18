from src.agents.document_classifier_agent import document_classifier_agent

def test_chunking():
    text = "A long text " * 500
    result = document_classifier_agent.chunk_text(text)
    assert len(result) > 1
