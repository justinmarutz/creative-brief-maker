import io
import logging
import os
import zipfile
from pathlib import Path

import requests as http
from flask import Flask, jsonify, render_template, request, send_file

from brief_generator import build_filename, generate_docx_bytes, generate_pdf_bytes
from brief_parser import extract_text_from_docx, parse_submission

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB
MAX_CONCEPTS = 30  # sanity cap

BRIEFS_DIR = Path(__file__).parent / "briefs"
BRIEFS_DIR.mkdir(exist_ok=True)

# ── Asana config ──────────────────────────────────────────────────────────────
ASANA_TOKEN       = os.environ.get("ASANA_TOKEN", "")
ASANA_PROJECT_GID = "1202102819438073"
ASANA_SECTION_GID = "1205115877210117"
ASANA_API         = "https://app.asana.com/api/1.0"


def _asana_headers():
    return {"Authorization": f"Bearer {ASANA_TOKEN}", "Accept": "application/json"}


def _build_task_notes(concept):
    """Structured plain-text description for the Asana task."""
    lines = []
    for label, key in [
        ("Platform",       "platform"),
        ("Duration",       "duration"),
        ("Setting",        "setting"),
        ("Talent",         "talent"),
        ("Concept / Vibe", "format_vibe"),
        ("Inspiration",    "inspiration"),
        ("Reference link", "reference_link"),
    ]:
        if concept.get(key):
            lines.append(f"{label}: {concept[key]}")
    if concept.get("script"):
        lines.append(f"\n{'─'*40}\nSCRIPT\n{'─'*40}\n{concept['script']}")
    return "\n".join(lines)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/parse", methods=["POST"])
def parse():
    try:
        text = ""
        if "file" in request.files and request.files["file"].filename:
            f = request.files["file"]
            name = f.filename.lower()
            raw = f.read()
            if name.endswith(".docx"):
                text = extract_text_from_docx(raw)
            else:
                text = raw.decode("utf-8", errors="replace")
        else:
            text = (request.form.get("text") or "").strip()

        if not text:
            return jsonify({"error": "No content provided"}), 400

        concepts = parse_submission(text)
        if not concepts:
            return jsonify({"error": "No concepts found in submission"}), 400
        if len(concepts) > MAX_CONCEPTS:
            return jsonify({"error": f"Too many concepts ({len(concepts)}). Max is {MAX_CONCEPTS}."}), 400

        return jsonify({"concepts": concepts})
    except Exception as e:
        log.exception("Parse failed")
        return jsonify({"error": "Parse failed — check the server log for details."}), 500


@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json(silent=True)
        if not data or not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON body"}), 400
        concepts = data.get("concepts") or []
        if not concepts:
            return jsonify({"error": "No concepts provided"}), 400
        if len(concepts) > MAX_CONCEPTS:
            return jsonify({"error": f"Too many concepts ({len(concepts)}). Max is {MAX_CONCEPTS}."}), 400

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for concept in concepts:
                pdf_name = build_filename(concept, "pdf")
                docx_name = build_filename(concept, "docx")

                pdf_bytes = generate_pdf_bytes(concept)
                docx_bytes = generate_docx_bytes(concept)

                zf.writestr(pdf_name, pdf_bytes)
                zf.writestr(docx_name, docx_bytes)

                # Save locally too
                (BRIEFS_DIR / pdf_name).write_bytes(pdf_bytes)
                (BRIEFS_DIR / docx_name).write_bytes(docx_bytes)

        zip_buf.seek(0)
        log.info("Generated %d brief(s)", len(concepts))
        return send_file(
            zip_buf,
            mimetype="application/zip",
            as_attachment=True,
            download_name="creator_briefs.zip",
        )
    except Exception:
        log.exception("Generation failed")
        return jsonify({"error": "Generation failed — check the server log for details."}), 500


@app.route("/asana-status")
def asana_status():
    return jsonify({"configured": bool(ASANA_TOKEN)})


@app.route("/create-asana-tasks", methods=["POST"])
def create_asana_tasks():
    if not ASANA_TOKEN:
        return jsonify({"error": "ASANA_TOKEN environment variable is not set on the server."}), 500

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400
    concepts = data.get("concepts") or []
    if not concepts:
        return jsonify({"error": "No concepts provided"}), 400
    if len(concepts) > MAX_CONCEPTS:
        return jsonify({"error": f"Too many concepts ({len(concepts)})."}), 400

    results = []
    for concept in concepts:
        entry = {"title": concept.get("title", "Brief"), "ok": False}
        try:
            brand      = concept.get("brand", "SelfFinder")
            title      = concept.get("title", "Brief")
            task_name  = f"{title} — {brand} UGC Brief"

            # Create task in the Videos & GIFs board
            # Note: use memberships only (not projects) — sending both causes a 400
            resp = http.post(
                f"{ASANA_API}/tasks",
                headers={**_asana_headers(), "Content-Type": "application/json"},
                json={"data": {
                    "name": task_name,
                    "notes": _build_task_notes(concept),
                    "memberships": [{"project": ASANA_PROJECT_GID, "section": ASANA_SECTION_GID}],
                }},
                timeout=15,
            )
            resp.raise_for_status()
            task_gid = resp.json()["data"]["gid"]
            entry["task_url"] = f"https://app.asana.com/0/{ASANA_PROJECT_GID}/{task_gid}"
            entry["task_gid"] = task_gid

            # Generate files for attachment
            pdf_bytes  = generate_pdf_bytes(concept)
            docx_bytes = generate_docx_bytes(concept)
            pdf_name   = build_filename(concept, "pdf")
            docx_name  = build_filename(concept, "docx")

            # Attach PDF
            http.post(
                f"{ASANA_API}/attachments",
                headers=_asana_headers(),
                data={"parent": task_gid},
                files={"file": (pdf_name, pdf_bytes, "application/pdf")},
                timeout=30,
            )

            # Attach DOCX
            http.post(
                f"{ASANA_API}/attachments",
                headers=_asana_headers(),
                data={"parent": task_gid},
                files={"file": (
                    docx_name, docx_bytes,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )},
                timeout=30,
            )

            entry["ok"] = True
            log.info("Asana task created: %s → %s", task_name, entry["task_url"])

        except http.exceptions.HTTPError as exc:
            body = ""
            try:
                body = exc.response.json()
            except Exception:
                body = exc.response.text if exc.response else ""
            log.error("Asana HTTP error for %s: %s — %s", concept.get("title"), exc, body)
            entry["error"] = f"Asana API error {exc.response.status_code if exc.response else '?'}: {body}"
        except Exception as exc:
            log.exception("Asana task creation failed for: %s", concept.get("title"))
            entry["error"] = f"Task creation failed: {exc}"

        results.append(entry)

    return jsonify({"tasks": results})


if __name__ == "__main__":
    app.run(debug=True, port=5001)
