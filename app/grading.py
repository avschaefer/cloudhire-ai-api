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
    api_key = os.environ["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(GEMINI_MODEL)
    per_q: List[Dict[str, Any]] = []
    total = 0.0

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
        resp = model.generate_content(
            [{"role":"user","parts":[{"text": prompt}]}],
            generation_config={"temperature": 0.2, "max_output_tokens": 200},
            safety_settings=None
        )
        try:
            js = json.loads(resp.text or "{}")
        except Exception:
            js = {}
        score = float(js.get("score", 0))
        rationale = str(js.get("rationale", ""))

        per_q.append({
            "question_type": a["question_type"],
            "question_id": a["question_id"],
            "score": score,
            "rationale": rationale,
            "tags": []
        })
        total += score

    overall_score = total / max(1, len(answers))
    overall = {"score": overall_score, "band": "Pass" if overall_score >= 0.7 else "Fail", "notes": "Gemini auto‑grade"}
    # Token/cost usage not exposed directly in this simple call; keep placeholders
    cost = {"input_tokens": 0, "output_tokens": 0, "usd": 0.0}
    return per_q, overall, cost

def grade(answers: List[Dict[str, Any]], rubric: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, float]]:
    if GRADER_MODE == "gemini":
        return _gemini_grade(answers, rubric or {})
    return _dummy_grade(answers, rubric or {})
