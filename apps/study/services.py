import json
import os
import re
from django.conf import settings
from groq import Groq

COLOR_PALETTE = ['indigo', 'emerald', 'rose', 'amber', 'sky', 'violet', 'orange', 'teal']


def safe_str(val):
    if val is None:
        return ""
    return str(val).strip()


def prefilter_syllabus_text(raw_text):
    """
    Three-pass distiller optimized for detailed unit extraction.
    """
    lines = raw_text.splitlines()
    relevant_lines = []
    seen_lines = set()

    def add_line(text):
        clean = safe_str(text)
        if clean and clean not in seen_lines and len(clean) >= 2:
            seen_lines.add(clean)
            relevant_lines.append(clean)

    # Very broad pattern to capture ALL numbered headings and sub-headings
    content_pattern = re.compile(
        r'(^\s*\d+[\.\)]|^\s*\d+\.\d+|'
        r'unit\s*\d|chapter\s*\d|module\s*\d|'
        r'course\s*(code|title|name)|credit|semester|hour|'
        r'\bBCE\d{3,4}\b|\bCS\d{3,4}\b|\bIT\d{3,4}\b|\bEC\d{3,4}\b|'
        r'elective|option|'
        r'automata|computation|turing|pushdown|finite|'
        r'foundation|formal|set\s*theory|proof|'
        r'network|protocol|routing|subnet|'
        r'machine\s*learning|data\s*mining|multimedia|warehousing|'
        r'operating|process|deadlock|semaphore|'
        r'database|normalization|sql|'
        r'software|agile|compiler|grammar|parsing|'
        r'complexity|decidability|recursive|'
        r'regular|context.free|pumping|closure|'
        r'ambiguity|derivation|parse\s*tree|'
        r'church|undecid|tractable|intractable|'
        r'NP.complete|NP.hard)',
        re.IGNORECASE
    )

    for line in lines:
        cleaned = safe_str(line)
        if not cleaned or len(cleaned) < 2:
            continue
        # Skip pure hour markers like "(8 hrs)"
        if re.match(r'^\(\d+\s*hrs?\)$', cleaned):
            continue
        # Skip reference/book lines
        if re.match(r'^(references|isbn|edition|prentice|academic\s*press)', cleaned, re.IGNORECASE):
            continue
        if content_pattern.search(cleaned):
            add_line(cleaned)

    # Pass 2: Force-capture elective blocks
    elective_started = False
    elective_gap = 0

    for line in lines:
        cleaned = safe_str(line)
        if not cleaned or len(cleaned) < 2:
            if elective_started:
                elective_gap += 1
                if elective_gap > 3:
                    elective_started = False
            continue

        if re.search(r'elective[\s\-]*[IVX\d]', cleaned, re.IGNORECASE):
            elective_started = True
            elective_gap = 0
            add_line(cleaned)
            continue

        if elective_started:
            add_line(cleaned)
            elective_gap = 0
            if re.search(r'^(unit\s*1|chapter\s*1|course\s*code)', cleaned, re.IGNORECASE):
                elective_started = False

    if len(relevant_lines) < 20:
        compact = re.sub(r'\s+', ' ', raw_text).strip()
        return compact[:15000]

    return "\n".join(relevant_lines)[:15000]


def extract_unit_number(title):
    title_clean = safe_str(title)
    match = re.search(r'(?:unit|chapter)\s*(\d+)', title_clean, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.match(r'^(\d+)[\.\)]\s', title_clean)
    if match:
        return int(match.group(1))
    return None


def core_title(title):
    t = safe_str(title).lower()
    t = re.sub(r'^(unit|chapter)\s*\d+[:\.\s]*', '', t)
    t = re.sub(r'\s*[–\-]\s*.*$', '', t)
    t = re.sub(r'^\d+[\.\)]\s*', '', t)
    return t.strip()


def titles_are_similar(title1, title2):
    c1 = core_title(title1)
    c2 = core_title(title2)
    if not c1 or not c2:
        return False
    if c1 == c2:
        return True
    shorter = min(len(c1), len(c2))
    if shorter >= 5 and (c1 in c2 or c2 in c1):
        return True
    words1 = set(c1.split())
    words2 = set(c2.split())
    if words1 and words2:
        overlap = len(words1 & words2)
        if overlap / min(len(words1), len(words2)) >= 0.5:
            return True
    return False


def deduplicate_topics(raw_topics):
    if not raw_topics:
        return []

    normalized = []
    for t in raw_topics:
        if isinstance(t, str):
            clean_t = safe_str(t)
            if clean_t:
                normalized.append({"title": clean_t, "chapter_number": 0, "difficulty": "medium"})
        elif isinstance(t, dict):
            title = safe_str(t.get('title') or t.get('name'))
            if title:
                diff = safe_str(t.get('difficulty')) or 'medium'
                normalized.append({
                    "title": title,
                    "chapter_number": t.get('chapter_number', 0),
                    "difficulty": diff if diff in ['easy', 'medium', 'hard'] else 'medium'
                })

    unit_groups = {}
    no_unit = []

    for t in normalized:
        unit_num = extract_unit_number(t['title'])
        if unit_num is not None:
            if unit_num not in unit_groups:
                unit_groups[unit_num] = []
            unit_groups[unit_num].append(t)
        else:
            no_unit.append(t)

    final_with_units = []
    for unit_num in sorted(unit_groups.keys()):
        group = unit_groups[unit_num]
        if len(group) == 1:
            final_with_units.append(group[0])
        else:
            clusters = []
            for t in group:
                placed = False
                for cluster in clusters:
                    if titles_are_similar(t['title'], cluster[0]['title']):
                        cluster.append(t)
                        placed = True
                        break
                if not placed:
                    clusters.append([t])
            for cluster in clusters:
                best = max(cluster, key=lambda x: len(x['title']))
                final_with_units.append(best)

    seen_cores = set()
    unique_no_unit = []
    for t in no_unit:
        ct = core_title(t['title'])
        if not ct or len(ct) < 3:
            continue
        is_dup = False
        for sc in seen_cores:
            if ct == sc or (len(ct) > 5 and (ct in sc or sc in ct)):
                is_dup = True
                break
        if not is_dup:
            seen_cores.add(ct)
            unique_no_unit.append(t)

    final_topics = final_with_units + unique_no_unit
    for idx, t in enumerate(final_topics):
        t['chapter_number'] = idx + 1

    return final_topics


def extract_syllabus_with_ai(syllabus_text):
    api_key = getattr(settings, 'GROQ_API_KEY', '') or os.getenv('GROQ_API_KEY', '')
    if not api_key:
        raise Exception("GROQ_API_KEY is not configured.")

    client = Groq(api_key=api_key)
    compressed_text = prefilter_syllabus_text(syllabus_text)

    system_prompt = (
        "You are a university syllabus parser. Your ONLY job is to extract subjects and their EXACT unit headings. "
        "CRITICAL RULES: "
        "1. List EVERY numbered unit heading EXACTLY as it appears. Do NOT merge, combine, or summarize units. "
        "2. A subject may have 4, 5, 6, 7, 8, or more units. List ALL of them. "
        "3. Include sub-topic details after a dash. Example: 'Unit 1: Finite Automata – DFA, NFA, regular expressions, Arden theorem'. "
        "4. Do NOT skip any unit. If the syllabus lists 8 units, your output must have 8 topics. "
        "5. Elective options must each be a separate subject with is_elective=true. "
        "6. Output ONLY valid JSON."
    )

    user_prompt = f"""Extract ALL subjects and their COMPLETE unit lists from this syllabus.

ABSOLUTE RULES:
- Count the numbered headings in the text. If you see headings 1 through 8, output 8 topics.
- Do NOT merge "Properties of Regular Sets" into "Finite Automata". They are SEPARATE units.
- Do NOT merge "Pushdown Automata" into "Context Free Grammars". They are SEPARATE units.
- Do NOT merge "Undecidability" into "Turing Machines". They are SEPARATE units.
- Include sub-topic keywords after a dash for each unit.

Example output for a subject with 8 units:
{{
    "subjects": [
        {{
            "name": "Theory of Computation",
            "code": "BCE604",
            "is_elective": false,
            "elective_group": null,
            "topics": [
                "Unit 1: Finite Automata and Regular Expressions – set theory, DFA, NFA, epsilon-NFA, minimization, Arden theorem",
                "Unit 2: Properties of Regular Sets – pumping lemma, closure properties, decision algorithms",
                "Unit 3: Context Free Grammars – derivation, parse trees, ambiguity, simplification, normal forms",
                "Unit 4: Pushdown Automata – PDA definition, PDA and CFG relationship",
                "Unit 5: Properties of CFLs – pumping lemma for CFLs, closure, decision algorithms",
                "Unit 6: Turing Machines – computable languages, Church hypothesis",
                "Unit 7: Undecidability – recursive languages, universal TM, undecidable problems, recursive function theory",
                "Unit 8: Computational Complexity – tractable vs intractable, P, NP, NP-Hard, NP-Complete, time and space complexity"
            ]
        }}
    ]
}}

Syllabus:
---
{compressed_text}
---"""

    candidate_models = []
    try:
        models_data = client.models.list().data
        candidate_models = [
            m.id for m in models_data
            if not any(x in m.id.lower() for x in ['whisper', 'embed', 'guard', 'vision', 'preview'])
        ]
        candidate_models.sort(
            key=lambda n: (0 if '3.3-70b' in n else 1 if '70b' in n else 2 if '8b' in n else 3)
        )
    except Exception:
        candidate_models = ["llama-3.3-70b-versatile"]

    last_err = None

    for model_name in candidate_models:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=3500,
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content.strip()

            if "```" in raw:
                m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
                if m:
                    raw = m.group(1)

            parsed = json.loads(raw)
            normalized_subjects = []

            for subj in (parsed.get('subjects') or parsed.get('s') or []):
                if not isinstance(subj, dict):
                    continue

                name = safe_str(subj.get('name') or subj.get('n'))
                if not name:
                    continue

                code = safe_str(subj.get('code') or subj.get('c')) or None
                is_elective = bool(subj.get('is_elective', False))
                elective_group = safe_str(subj.get('elective_group') or subj.get('eg')) or None
                raw_topics = subj.get('topics') or subj.get('t') or []

                clean_topics = deduplicate_topics(raw_topics)

                normalized_subjects.append({
                    "name": name,
                    "code": code,
                    "description": f"Curriculum for {name}",
                    "is_elective": is_elective,
                    "elective_group": elective_group,
                    "topics": clean_topics
                })

            if normalized_subjects:
                total_topics = sum(len(s['topics']) for s in normalized_subjects)
                print(f"✅ [Syllabus]: {len(normalized_subjects)} subjects, {total_topics} unique topics ({model_name})")
                return {"semester": 7, "subjects": normalized_subjects}

        except Exception as e:
            last_err = e
            print(f"[Parser '{model_name}' failed]: {e}")
            continue

    raise Exception(f"Syllabus extraction failed: {str(last_err)}")