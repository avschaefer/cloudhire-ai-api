from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML
from datetime import datetime
import io, os

_env = Environment(
    loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates")),
    autoescape=select_autoescape()
)

def render_report_pdf(attempt_id: str, results, overall) -> bytes:
    # Group by section label (None sections go last)
    sorted_results = sorted(
        results,
        key=lambda r: (str(r.get("section") or "ZZZ"), str(r["question_type"]), int(r["question_id"]))
    )
    html = _env.get_template("report.html").render(
        attempt_id=attempt_id,
        results=sorted_results,
        overall=overall,
        generated_at=datetime.utcnow().isoformat()
    )
    buf = io.BytesIO()
    HTML(string=html).write_pdf(buf)
    return buf.getvalue()
