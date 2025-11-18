import pytest
from src.retriever.hr_retriever import HRRetriever

@pytest.mark.asyncio
async def test_retrieval():
    retriever = HRRetriever()
    results = await retriever.retrieve("leave policy", "hr_policy")
    assert isinstance(results, list)
