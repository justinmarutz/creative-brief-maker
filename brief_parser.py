import datetime
import io
import re
from datetime import date


LABEL_MAP = [
    (r"^script\s*$", "script"),
    (r"^duration\s*$", "duration"),
    (r"^format\s*/\s*vibe\s*$|^format\s*$", "format_vibe"),
    (r"^inspiration\s*$", "inspiration"),
    (r"^setting\s*$", "setting"),
    (r"^talent\s*$", "talent"),
    (r"^angle\s*$", "angle"),
    (r"^on.?screen text.*$", "on_screen_text"),
    (r"^primary text.*$|^ad copy.*$", "ad_copy"),
    (r"^brand\s*$", "brand"),
    (r"^platform\s*$", "platform"),
    (r"^submission date\s*$", "submission_date"),
    (r"^campaign goal\s*$", "campaign_goal"),
]


def extract_text_from_docx(file_bytes):
    from docx import Document
    doc = Document(io.BytesIO(file_bytes))
    lines = []
    for para in doc.paragraphs:
        lines.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            lines.append("\t".join(c.text for c in row.cells))
    return "\n".join(lines)


def _match_label(line):
    clean = line.strip().rstrip(":").strip().lower()
    for pattern, key in LABEL_MAP:
        if re.match(pattern, clean, re.IGNORECASE):
            return key
    return None


def _parse_concept_block(block, index):
    today = date.today().strftime("%m%d%y")
    concept = {
        "index": index,
        "title": "",
        "brand": "SelfFinder",
        "platform": "Meta",
        "duration": "",
        "setting": "",
        "talent": "",
        "inspiration": "",
        "reference_link": "",
        "script": "",
        "format_vibe": "",
        "submission_date": today,
        "missing": [],
    }

    lines = block.strip().splitlines()
    if not lines:
        return None

    # Extract title from first line
    first = lines[0].strip()
    quoted = re.search(r'[“”„"](.*?)[“”„"]', first)
    if quoted:
        concept["title"] = quoted.group(1).strip()
    elif ":" in first:
        concept["title"] = first.split(":", 1)[1].strip().strip('"').strip("“”")
    else:
        concept["title"] = first.strip()

    # Scan lines for label→value blocks
    current_key = None
    current_lines = []

    def flush(key, val_lines):
        if not key:
            return
        # Ensure stage directions on the same line as dialogue get a line break
        joined = []
        for l in val_lines:
            if l.strip():
                # Insert newline when a closing ] is immediately followed by a quote
                l = re.sub(r'(\])\s*(["""])', r'\1\n\2', l)
                joined.append(l)
        value = "\n".join(joined).strip()
        # Only set if not already set by a more specific field
        if key in concept and concept[key]:
            return
        if key in concept:
            concept[key] = value
        elif key == "angle":
            if not concept.get("setting"):
                concept["setting"] = value
        elif key == "format_vibe":
            concept["format_vibe"] = value

    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            if current_key:
                current_lines.append("")
            continue

        matched = _match_label(stripped)
        if matched:
            flush(current_key, current_lines)
            current_key = matched
            current_lines = []
            # Inline value after colon on same line
            if ":" in stripped:
                inline = stripped.split(":", 1)[1].strip()
                if inline:
                    current_lines.append(inline)
        else:
            if current_key:
                current_lines.append(stripped)

    flush(current_key, current_lines)

    # Split inspiration into description + reference_link when both are present
    # Handles formats like: "myIQ 'are you smarter...' — https://..."
    if concept["inspiration"] and not concept["reference_link"]:
        url_match = re.search(r'(https?://\S+)', concept["inspiration"])
        if url_match:
            url = url_match.group(1).rstrip(")")  # strip trailing parens
            desc = concept["inspiration"][:url_match.start()].rstrip(" —–-").strip()
            concept["reference_link"] = url
            if desc:
                concept["inspiration"] = desc

    # Normalize duration em-dash
    if concept["duration"]:
        concept["duration"] = concept["duration"].replace("-", "–")

    # Mark missing fields
    for f in ["duration", "setting", "inspiration"]:
        if not concept.get(f):
            concept["missing"].append(f)

    return concept


ANGLE_TALENT = {
    "partner": "Woman, 28–42. Looks like she's been in a relationship — relatable, not a lifestyle influencer.",
    "self":    "Flexible — any creator who can deliver with genuine self-awareness energy.",
    "general": "Flexible — any creator who reads as credible and grounded.",
}

ANGLE_SETTING = {
    "partner": "Realistic living room on couch, or in car — anywhere casual.",
    "self":    "At home — bedroom, kitchen, or couch. Natural light.",
    "general": "At home or in car. Natural light, phone-grade.",
}


def _extract_trailing_metadata(text):
    """
    Parse the trailing tab-separated table that has per-script triplets:
      Angle\t<value>
      Duration\t<value>
      Format/Vibe\t<value>
    Returns a list of dicts in script order.
    """
    groups = []
    current = {}
    for line in text.splitlines():
        if "\t" not in line:
            continue
        key, _, val = line.partition("\t")
        key = key.strip().lower().rstrip(":")
        val = val.strip()
        if not val:
            continue
        if key == "angle":
            if current:
                groups.append(current)
            current = {"angle": val.lower()}
        elif key == "duration" and current:
            current["duration"] = val.replace("-", "–")
        elif re.match(r"format\s*/\s*vibe|format$", key) and current:
            current["format_vibe"] = val
    if current:
        groups.append(current)
    return groups


def _extract_global_metadata(text):
    """Pull submission-level fields that apply to all concepts."""
    global_data = {}
    for line in text.splitlines():
        if "\t" in line:
            key, _, val = line.partition("\t")
            key = key.strip().lower().rstrip(":")
            val = val.strip()
            if key == "product" and val:
                global_data["brand_note"] = val
            elif key == "platform" and val:
                global_data["platform"] = val
    # Detect submission date from header (e.g. "April 8, 2026")
    date_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})", text)
    if date_match:
        try:
            dt = datetime.datetime.strptime(date_match.group(0).replace(",", ""), "%B %d %Y")
            global_data["submission_date"] = dt.strftime("%m%d%y")
        except ValueError:
            pass
    return global_data


def parse_submission(text):
    # ── Split into concept blocks ────────────────────────────
    pattern = r"(?m)^(?:Script|Concept)\s+\d+\s*[:\.]"
    parts = re.split(pattern, text)
    headers = re.findall(pattern, text)

    concepts = []
    if len(parts) > 1:
        for i, (header, block) in enumerate(zip(headers, parts[1:])):
            c = _parse_concept_block(header + block, i + 1)
            if c:
                concepts.append(c)
    else:
        md_pattern = r"(?m)^##\s+(?:Concept|Script)\s+\d+"
        md_parts = re.split(md_pattern, text)
        md_headers = re.findall(md_pattern, text)
        if len(md_parts) > 1:
            for i, (header, block) in enumerate(zip(md_headers, md_parts[1:])):
                c = _parse_concept_block(header + block, i + 1)
                if c:
                    concepts.append(c)
        else:
            c = _parse_concept_block(text, 1)
            if c:
                concepts.append(c)

    # ── Apply trailing per-script metadata table ─────────────
    trailing = _extract_trailing_metadata(text)
    for i, meta in enumerate(trailing):
        if i >= len(concepts):
            break
        c = concepts[i]
        angle = meta.get("angle", "")
        if not c.get("duration") and meta.get("duration"):
            c["duration"] = meta["duration"]
        if not c.get("format_vibe") and meta.get("format_vibe"):
            c["format_vibe"] = meta["format_vibe"]
        # Derive setting and talent from angle if still missing
        if not c.get("setting"):
            c["setting"] = ANGLE_SETTING.get(angle, "")
        if not c.get("talent"):
            c["talent"] = ANGLE_TALENT.get(angle, "")

    # ── Apply global submission metadata ─────────────────────
    global_meta = _extract_global_metadata(text)
    if global_meta.get("submission_date"):
        for c in concepts:
            c["submission_date"] = global_meta["submission_date"]

    # ── Recompute missing flags after enrichment ─────────────
    for c in concepts:
        c["missing"] = [f for f in ["duration", "setting", "inspiration"] if not c.get(f)]

    return concepts
