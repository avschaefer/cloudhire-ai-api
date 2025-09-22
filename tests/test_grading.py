import pytest
import json
from unittest.mock import patch, MagicMock
from app.grading import grade, _dummy_grade, GRADER_MODE

# Check if google.generativeai is available
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class TestDummyGrading:
    """Test the dummy grading fallback"""

    def test_dummy_grading_basic(self, sample_answers, sample_rubric):
        """Test basic dummy grading functionality"""
        per_q, overall, cost = _dummy_grade(sample_answers, sample_rubric)

        assert len(per_q) == len(sample_answers)
        assert isinstance(overall, dict)
        assert "score" in overall
        assert "band" in overall
        assert "notes" in overall

        # Check cost is zero for dummy
        assert cost["input_tokens"] == 0
        assert cost["output_tokens"] == 0
        assert cost["usd"] == 0.0

    def test_dummy_grading_scores(self, sample_answers):
        """Test that dummy grading returns reasonable scores"""
        per_q, overall, cost = _dummy_grade(sample_answers, {})

        for result in per_q:
            assert 0.0 <= result["score"] <= 1.0
            assert "rationale" in result
            assert isinstance(result["tags"], list)

        assert 0.0 <= overall["score"] <= 1.0
        assert overall["band"] in ["Pass", "Fail"]


class TestGeminiGrading:
    """Test Gemini AI grading (mocked)"""

    @pytest.mark.skipif(not GENAI_AVAILABLE, reason="google.generativeai not available")
    @patch('google.generativeai')
    def test_gemini_grading_success(self, mock_genai, sample_answers, sample_rubric, mock_gemini_response):
        """Test successful Gemini grading"""
        # Setup mock
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_gemini_response
        mock_genai.GenerativeModel.return_value = mock_model

        # Temporarily set to gemini mode
        import app.grading
        original_mode = app.grading.GRADER_MODE
        app.grading.GRADER_MODE = "gemini"

        try:
            per_q, overall, cost = grade(sample_answers, sample_rubric)

            assert len(per_q) == len(sample_answers)
            assert cost["input_tokens"] == 150 * len(sample_answers)  # 150 tokens per question
            assert cost["output_tokens"] == 50 * len(sample_answers)  # 50 tokens per question
            assert cost["usd"] > 0  # Should have calculated cost
        finally:
            app.grading.GRADER_MODE = original_mode

    @pytest.mark.skipif(not GENAI_AVAILABLE, reason="google.generativeai not available")
    @patch('google.generativeai')
    def test_gemini_grading_api_error(self, mock_genai, sample_answers, sample_rubric):
        """Test Gemini grading with API error"""
        # Setup mock to raise exception
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API Error")
        mock_genai.GenerativeModel.return_value = mock_model

        # Temporarily set to gemini mode
        import app.grading
        original_mode = app.grading.GRADER_MODE
        app.grading.GRADER_MODE = "gemini"

        try:
            per_q, overall, cost = grade(sample_answers, sample_rubric)

            # Should still return results (fallback scoring)
            assert len(per_q) == len(sample_answers)
            # Should have some failed questions marked
            failed_count = sum(1 for r in per_q if "api_error" in r.get("tags", []))
            assert failed_count > 0
        finally:
            app.grading.GRADER_MODE = original_mode

    def test_grader_mode_fallback(self, sample_answers, sample_rubric):
        """Test that invalid grader mode falls back to dummy"""
        import app.grading
        original_mode = app.grading.GRADER_MODE
        app.grading.GRADER_MODE = "invalid_mode"

        try:
            per_q, overall, cost = grade(sample_answers, sample_rubric)
            # Should use dummy grading
            assert cost["usd"] == 0.0
        finally:
            app.grading.GRADER_MODE = original_mode


class TestCostCalculation:
    """Test cost calculation logic"""

    def test_cost_calculation_zero_tokens(self):
        """Test cost calculation with zero tokens"""
        # Test the cost formula manually (logic from _gemini_grade)
        input_tokens = 0
        output_tokens = 0

        input_cost = (input_tokens / 1_000_000) * 0.15
        output_cost = (output_tokens / 1_000_000) * 0.60
        total_cost = input_cost + output_cost

        assert total_cost == 0.0

    def test_cost_calculation_realistic_tokens(self):
        """Test cost calculation with realistic token counts"""
        input_tokens = 1000
        output_tokens = 500

        input_cost = (input_tokens / 1_000_000) * 0.15
        output_cost = (output_tokens / 1_000_000) * 0.60
        total_cost = input_cost + output_cost

        expected_cost = 0.00015 + 0.0003  # 0.00045
        assert abs(total_cost - expected_cost) < 0.000001


class TestJSONParsing:
    """Test robust JSON parsing logic (from grading.py)"""

    def test_json_parsing_various_formats(self):
        """Test parsing different JSON response formats (logic from _gemini_grade)"""
        import re

        # Test cases for JSON parsing (same logic as in grading.py)
        test_cases = [
            ('{"score": 0.8, "rationale": "Good"}', 0.8, "Good"),
            ('{"grade": 0.9, "explanation": "Excellent"}', 0.9, "Excellent"),
            ('Not JSON at all', 0.0, "Grading failed - unable to parse AI response"),
            ('Some text {"score": 0.7} more text', 0.7, "Grading failed - unable to parse AI response"),
        ]

        for raw_text, expected_score, expected_rationale in test_cases:
            # Test the parsing logic from _gemini_grade
            js = {}
            raw_text_clean = raw_text or ""

            # Try direct JSON parsing first
            try:
                js = json.loads(raw_text_clean)
            except json.JSONDecodeError:
                # Try to extract JSON from text that might contain extra content
                json_match = re.search(r'\{.*\}', raw_text_clean, re.DOTALL)
                if json_match:
                    try:
                        js = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass

            # Validate and extract score/rationale
            score = 0.0
            rationale = "Grading failed - unable to parse AI response"

            if isinstance(js, dict):
                # Try different possible keys for score
                score_value = js.get("score") or js.get("grade") or js.get("rating")
                if score_value is not None:
                    try:
                        score = float(score_value)
                        # Clamp to 0-1 range
                        score = max(0.0, min(1.0, score))
                    except (ValueError, TypeError):
                        pass

                rationale_value = js.get("rationale") or js.get("explanation") or js.get("feedback") or js.get("comment")
                if rationale_value:
                    rationale = str(rationale_value)[:500]  # Limit length

            assert score == expected_score
            assert rationale == expected_rationale
