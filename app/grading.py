# Grading using Gemini (default) or a dummy fallback.
# Set GRADER_MODE=gemini (recommended) and provide GEMINI_API_KEY and GEMINI_MODEL
# Default model can be overridden by env; you can set GEMINI_MODEL=gemini-2.5-flash if available.

from typing import Any, Dict, List, Tuple
import os, json

GRADER_MODE = os.getenv("GRADER_MODE", "gemini")  # 'gemini' | 'dummy'
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

def _dummy_grade(answers: List[Dict[str, Any]], rubric: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, float]]:
    out = []
    for a in answers:
        out.append({
            "question_type": a["question_type"],
            "question_id": a["question_id"],
            "score": 0.8,
            "rationale": "Meets most criteria.",
            "tags": []
        })
    overall = {"score": sum(x["score"] for x in out)/max(1,len(out)), "band":"Pass", "notes":"Auto‑graded (dummy)."}
    cost = {"input_tokens": 0, "output_tokens": 0, "usd": 0.0}
    return out, overall, cost

def _gemini_grade(answers: List[Dict[str, Any]], rubric: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, float]]:
    import google.generativeai as genai
    import logging

    logger = logging.getLogger(__name__)

    try:
        api_key = os.environ["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
    except KeyError:
        logger.error("GEMINI_API_KEY environment variable not set")
        return _fallback_grade(answers, rubric, "API key not configured")

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
    except Exception as e:
        logger.error(f"Failed to initialize Gemini model: {e}")
        return _fallback_grade(answers, rubric, f"Model initialization failed: {e}")

    per_q: List[Dict[str, Any]] = []
    total = 0.0
    total_input_tokens = 0
    total_output_tokens = 0
    failed_questions = 0

    for a in answers:
        prompt = f"""
You are a strict grader. Rubric (JSON): {json.dumps(rubric or {})}
Question identifier: {a['question_type']}:{a['question_id']}
Student answer:
{a['answer_text']}

Return a JSON object with:
- "score": a float from 0 to 1
- "rationale": a short sentence explaining the score
"""

        try:
            resp = model.generate_content(
                [{"role":"user","parts":[{"text": prompt}]}],
                generation_config={"temperature": 0.2, "max_output_tokens": 200},
                safety_settings=None
            )
        except Exception as e:
            logger.warning(f"Gemini API call failed for question {a['question_id']}: {e}")
            failed_questions += 1
            # Use fallback scoring for this question
            score = 0.5  # Neutral fallback score
            rationale = f"Grading failed due to API error: {str(e)[:100]}"
            per_q.append({
                "question_type": a["question_type"],
                "question_id": a["question_id"],
                "score": score,
                "rationale": rationale,
                "tags": ["api_error"]
            })
            total += score
            continue

        # Capture usage metadata
        usage = getattr(resp, 'usage_metadata', None)
        if usage:
            total_input_tokens += getattr(usage, 'prompt_token_count', 0)
            total_output_tokens += getattr(usage, 'candidates_token_count', 0)

        # Robust JSON parsing with fallbacks
        js = {}
        raw_text = resp.text or ""

        # Try direct JSON parsing first
        try:
            js = json.loads(raw_text)
        except json.JSONDecodeError:
            # Try to extract JSON from text that might contain extra content
            import re
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
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

        per_q.append({
            "question_type": a["question_type"],
            "question_id": a["question_id"],
            "score": score,
            "rationale": rationale,
            "tags": []
        })
        total += score

    # Log summary of grading results
    success_rate = (len(answers) - failed_questions) / max(1, len(answers))
    if failed_questions > 0:
        logger.warning(f"Grading completed with {failed_questions} failures out of {len(answers)} questions ({success_rate:.1%} success rate)")

    overall_score = total / max(1, len(answers))
    grading_notes = "Gemini auto‑grade"
    if failed_questions > 0:
        grading_notes += f" ({failed_questions} questions failed - used fallback scoring)"

    overall = {
        "score": overall_score,
        "band": "Pass" if overall_score >= 0.7 else "Fail",
        "notes": grading_notes
    }

    # Calculate approximate cost (Gemini 2.0 Flash pricing: $0.15/1M input tokens, $0.60/1M output tokens)
    input_cost = (total_input_tokens / 1_000_000) * 0.15
    output_cost = (total_output_tokens / 1_000_000) * 0.60
    total_cost_usd = input_cost + output_cost

    cost = {
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "usd": round(total_cost_usd, 6)
    }
    return per_q, overall, cost


def _fallback_grade(answers: List[Dict[str, Any]], rubric: Dict[str, Any], error_reason: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, float]]:
    """Fallback grading when Gemini API is completely unavailable"""
    import logging
    logger = logging.getLogger(__name__)

    logger.error(f"Using fallback grading due to: {error_reason}")

    # Use dummy grading as fallback
    return _dummy_grade(answers, rubric)

def grade(answers: List[Dict[str, Any]], rubric: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, float]]:
    if GRADER_MODE == "gemini":
        return _gemini_grade(answers, rubric or {})
    return _dummy_grade(answers, rubric or {})
