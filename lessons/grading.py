"""Schema, validation, answer-parsing and auto-grading for lesson content.

A lesson's ``content`` is a JSON list of blocks. Each block is a dict with a
``type`` field:

Non-graded:
  {"type": "heading", "text": "..."}
  {"type": "text",    "text": "..."}            # plain paragraph
  {"type": "html",    "html": "<...>"}          # raw HTML (for images/animations)
  {"type": "image",   "url": "https://..."}

Graded (optional "points", default 1; optional "explanation"):
  {"type": "single_choice",   "question": "...", "options": ["a","b"], "answer": 0}
  {"type": "multiple_choice", "question": "...", "options": ["a","b"], "answers": [0,1]}
  {"type": "true_false",      "question": "...", "answer": true}
  {"type": "short_text",      "question": "...", "answers": ["Paris"]}   # or "answer": "Paris"
  {"type": "ordering",        "question": "...", "items": ["1st","2nd","3rd"]}  # correct order
  {"type": "matching",        "question": "...", "pairs": [{"left":"H2O","right":"Wasser"}]}
"""

import random

GRADABLE_TYPES = {
    "single_choice",
    "multiple_choice",
    "true_false",
    "short_text",
    "ordering",
    "matching",
}
CONTENT_TYPES = {"heading", "text", "html", "image"} | GRADABLE_TYPES


def _points(block):
    try:
        return max(0, int(block.get("points", 1)))
    except (TypeError, ValueError):
        return 1


def content_max_points(content):
    total = 0
    for b in content or []:
        if isinstance(b, dict) and b.get("type") in GRADABLE_TYPES:
            total += _points(b)
    return total


def _accepted_short(block):
    answers = block.get("answers")
    if answers is None and block.get("answer") is not None:
        answers = [block["answer"]]
    return [str(a) for a in (answers or [])]


def validate_content(content):
    """Return a list of human-readable error strings (empty = valid)."""
    errors = []
    if not isinstance(content, list):
        return ["Der Inhalt muss eine Liste von Blöcken sein (JSON-Array)."]
    if not content:
        return ["Der Inhalt ist leer – bitte mindestens einen Block angeben."]

    for i, b in enumerate(content, 1):
        if not isinstance(b, dict) or "type" not in b:
            errors.append(f"Block {i}: fehlt das Feld 'type'.")
            continue
        t = b["type"]
        if t not in CONTENT_TYPES:
            errors.append(f"Block {i}: unbekannter Typ '{t}'.")
            continue
        if t in ("heading", "text") and not str(b.get("text", "")).strip():
            errors.append(f"Block {i} ({t}): braucht 'text'.")
        elif t == "html" and not str(b.get("html", "")).strip():
            errors.append(f"Block {i} (html): braucht 'html'.")
        elif t == "image" and not str(b.get("url", "")).strip():
            errors.append(f"Block {i} (image): braucht 'url'.")
        elif t in ("single_choice", "multiple_choice"):
            opts = b.get("options")
            if not isinstance(opts, list) or len(opts) < 2:
                errors.append(f"Block {i} ({t}): braucht 'options' (mindestens 2).")
                continue
            if t == "single_choice":
                if not isinstance(b.get("answer"), int) or not (0 <= b["answer"] < len(opts)):
                    errors.append(f"Block {i} (single_choice): 'answer' muss ein gültiger Options-Index sein.")
            else:
                ans = b.get("answers")
                if not isinstance(ans, list) or not ans or not all(
                    isinstance(x, int) and 0 <= x < len(opts) for x in ans
                ):
                    errors.append(f"Block {i} (multiple_choice): 'answers' muss eine Liste gültiger Indizes sein.")
        elif t == "true_false":
            if not isinstance(b.get("answer"), bool):
                errors.append(f"Block {i} (true_false): 'answer' muss true oder false sein.")
        elif t == "short_text":
            if not _accepted_short(b):
                errors.append(f"Block {i} (short_text): braucht 'answers' (oder 'answer').")
        elif t == "ordering":
            items = b.get("items")
            if not isinstance(items, list) or len(items) < 2:
                errors.append(f"Block {i} (ordering): braucht 'items' (mindestens 2, in korrekter Reihenfolge).")
        elif t == "matching":
            pairs = b.get("pairs")
            if not isinstance(pairs, list) or len(pairs) < 2 or not all(
                isinstance(p, dict) and "left" in p and "right" in p for p in pairs
            ):
                errors.append(f"Block {i} (matching): braucht 'pairs' mit je 'left' und 'right' (mindestens 2).")
    return errors


# --------------------------------------------------------------------------
# Parsing submitted answers from a POST QueryDict
# --------------------------------------------------------------------------

def parse_answers(content, post):
    answers = {}
    for i, b in enumerate(content):
        if not isinstance(b, dict) or b.get("type") not in GRADABLE_TYPES:
            continue
        t = b["type"]
        key = f"b{i}"
        if t == "single_choice":
            raw = post.get(key)
            answers[str(i)] = int(raw) if raw not in (None, "") and raw.isdigit() else None
        elif t == "multiple_choice":
            answers[str(i)] = [int(x) for x in post.getlist(key) if x.isdigit()]
        elif t == "true_false":
            raw = post.get(key)
            answers[str(i)] = True if raw == "true" else (False if raw == "false" else None)
        elif t == "short_text":
            answers[str(i)] = post.get(key, "")
        elif t == "ordering":
            n = len(b.get("items", []))
            positions = {}
            for oi in range(n):
                raw = post.get(f"{key}_pos_{oi}")
                positions[str(oi)] = int(raw) if raw not in (None, "") and raw.isdigit() else None
            answers[str(i)] = positions
        elif t == "matching":
            n = len(b.get("pairs", []))
            matches = {}
            for li in range(n):
                raw = post.get(f"{key}_match_{li}")
                matches[str(li)] = int(raw) if raw not in (None, "") and raw.isdigit() else None
            answers[str(i)] = matches
    return answers


# --------------------------------------------------------------------------
# Grading
# --------------------------------------------------------------------------

def _norm(s):
    return str(s).strip().lower()


def _is_correct(block, ans):
    t = block["type"]
    if t == "single_choice":
        return ans == block.get("answer")
    if t == "multiple_choice":
        return set(ans or []) == set(block.get("answers", []))
    if t == "true_false":
        return ans == bool(block.get("answer"))
    if t == "short_text":
        if ans is None:
            return False
        return _norm(ans) in [_norm(a) for a in _accepted_short(block)]
    if t == "ordering":
        n = len(block.get("items", []))
        if not isinstance(ans, dict):
            return False
        return all(ans.get(str(oi)) == oi + 1 for oi in range(n))
    if t == "matching":
        n = len(block.get("pairs", []))
        if not isinstance(ans, dict):
            return False
        return all(ans.get(str(li)) == li for li in range(n))
    return False


def grade(content, answers):
    results = {}
    score = 0
    max_score = 0
    for i, b in enumerate(content):
        if not isinstance(b, dict) or b.get("type") not in GRADABLE_TYPES:
            continue
        pts = _points(b)
        max_score += pts
        correct = _is_correct(b, answers.get(str(i)))
        if correct:
            score += pts
        results[str(i)] = {"correct": correct, "points": pts if correct else 0, "max": pts}
    return {"results": results, "score": score, "max_score": max_score}


# --------------------------------------------------------------------------
# View helpers (prepare blocks for interactive display / result display)
# --------------------------------------------------------------------------

def build_view_blocks(content, shuffle=True, rng=None):
    """Augment blocks with display helpers (indexed options, shuffled ordering
    items and matching options) for the interactive student template."""
    rng = rng or random
    view = []
    for i, b in enumerate(content):
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        vb = dict(b)
        vb["index"] = i
        vb["is_question"] = t in GRADABLE_TYPES
        if t in ("single_choice", "multiple_choice"):
            vb["opts"] = [{"i": j, "text": o} for j, o in enumerate(b.get("options", []))]
        elif t == "ordering":
            items = [{"i": j, "text": o} for j, o in enumerate(b.get("items", []))]
            display = items[:]
            if shuffle:
                rng.shuffle(display)
            vb["display_items"] = display
            vb["positions"] = list(range(1, len(items) + 1))
        elif t == "matching":
            pairs = b.get("pairs", [])
            vb["lefts"] = [{"i": j, "text": p.get("left", "")} for j, p in enumerate(pairs)]
            rights = [{"i": j, "text": p.get("right", "")} for j, p in enumerate(pairs)]
            if shuffle:
                rng.shuffle(rights)
            vb["rights"] = rights
        view.append(vb)
    return view


def correct_answer_text(block):
    """Human-readable correct answer for result display."""
    t = block.get("type")
    if t == "single_choice":
        opts = block.get("options", [])
        a = block.get("answer")
        return opts[a] if isinstance(a, int) and 0 <= a < len(opts) else ""
    if t == "multiple_choice":
        opts = block.get("options", [])
        return ", ".join(opts[a] for a in block.get("answers", []) if 0 <= a < len(opts))
    if t == "true_false":
        return "Wahr" if block.get("answer") else "Falsch"
    if t == "short_text":
        return " / ".join(_accepted_short(block))
    if t == "ordering":
        return " → ".join(str(x) for x in block.get("items", []))
    if t == "matching":
        return "; ".join(f"{p.get('left')} → {p.get('right')}" for p in block.get("pairs", []))
    return ""
