from src.agents.document_classifier_agent import document_classifier_agent

def test_classifier():
    result = document_classifier_agent.classify("salary bonus increment rules")
    assert result["category"] in ["payroll", "hr_policy", "it_support", "facilities", "uncategorized"]
