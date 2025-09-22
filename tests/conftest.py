import pytest
import os
from unittest.mock import MagicMock

@pytest.fixture
def sample_answers():
    """Sample exam answers for testing"""
    return [
        {
            "question_type": "multiple_choice",
            "question_id": 101,
            "answer_text": "The correct answer is option A because..."
        },
        {
            "question_type": "essay",
            "question_id": 102,
            "answer_text": "This is a well-structured essay that demonstrates clear understanding of the topic. The candidate shows excellent knowledge and provides relevant examples."
        },
        {
            "question_type": "coding",
            "question_id": 103,
            "answer_text": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)"
        }
    ]

@pytest.fixture
def sample_rubric():
    """Sample grading rubric for testing"""
    return {
        "multiple_choice": {
            "weight": 1.0,
            "criteria": ["Correctness", "Explanation quality"]
        },
        "essay": {
            "weight": 2.0,
            "criteria": ["Content knowledge", "Structure", "Clarity", "Examples"]
        },
        "coding": {
            "weight": 3.0,
            "criteria": ["Correctness", "Efficiency", "Code style", "Edge cases"]
        }
    }

@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response"""
    mock_response = MagicMock()
    mock_response.text = '{"score": 0.85, "rationale": "Good answer with solid reasoning"}'

    # Mock usage metadata
    usage_mock = MagicMock()
    usage_mock.prompt_token_count = 150
    usage_mock.candidates_token_count = 50
    mock_response.usage_metadata = usage_mock

    return mock_response

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Set up test environment variables"""
    test_env = {
        "GEMINI_API_KEY": "test-key",
        "GRADER_MODE": "dummy",  # Use dummy mode for tests by default
        "GEMINI_MODEL": "gemini-2.0-flash"
    }

    # Save original values
    originals = {}
    for key in test_env:
        originals[key] = os.environ.get(key)

    # Set test values
    for key, value in test_env.items():
        os.environ[key] = value

    yield

    # Restore originals
    for key, value in originals.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
