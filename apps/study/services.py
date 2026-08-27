import json
import os
import re
from django.conf import settings
from groq import Groq

COLOR_PALETTE = ['indigo', 'emerald', 'rose', 'amber', 'sky', 'violet', 'orange', 'teal']


def prefilter_syllabus_text(raw_text):
    """
    Smart multi-pass curriculum distiller.
    Captures course titles, unit headers, elective blocks across all pages.
    """
    lines = raw_text.splitlines()
    relevant_lines = []

    course_pattern = re.compile(
        r'(unit|chapter|module|course|code|credit|semester|hours|part|topic|'
        r'elective|option|choice|specialization|'
        r'algorithm|system|management|network|data|software|engineering|design|theory|'
        r'programming|analysis|architecture|computation|automata|mining|machine|'
        r'multimedia|warehousing|learning|computing|'
        r'\bBCE\d{3,4}\b|\bCS\d{3,4}\b|\bIT\d{3,4}\b|\bEC\d{3,4}\b|'
        r'\b[I|V|X]+\.\s|^\d+\.\s+[A-Z])',
        re.IGNORECASE
    )

    elective_pattern = re.compile(
        r'(elective|option|BCE\d{3,4}|choose|any one|any two)',
        re.IGNORECASE
    )

    in_elective_block = False
    elective_buffer = []

    for line in lines:
        cleaned = line.strip()
        if len(cleaned) < 2 or cleaned.isdigit():
            continue

        is_course_line = bool(course_pattern.search(cleaned))
        is_elective_line = bool(elective_pattern.search(cleaned))

        if is_elective_line and 'elective' in cleaned.lower():
            in_elective_block = True
            elective_buffer = [cleaned]
            continue

        if in_elective_block:
            elective_buffer.append(cleaned)
            if is_course_line and 'elective' not in cleaned.lower() and len(elective_buffer) > 3:
                relevant_lines.extend(elective_buffer)
                in_elective_block = False
                elective_buffer = []
                if is_course_line:
                    relevant_lines.append(cleaned)
            continue

        if is_course_line:
            relevant_lines.append(cleaned)

    if elective_buffer:
        relevant_lines.extend(elective_buffer)

    if len(relevant_lines) < 25:
        compact_text = re.sub(r'\s+', ' ', raw_text).strip()
        return compact_text[:12000]

    filtered_text = "\n".join(relevant_lines)
    return filtered_text[:12000]


def normalize_topic_title(title):
    """
    Strips 'Unit X:', chapter numbers, and detailed descriptions
    to produce a clean core title for deduplication comparison.
    Example: 'Unit 1: Introduction to OS – definition, types' -> 'introduction to os'
    """
    t = title.strip().lower()
    # Remove "Unit X:" or "Chapter X:" prefix
    t = re.sub(r'^(unit|chapter)\s*\d+[:\.\s]*', '', t)
    # Remove everything after " – " or " - " (detailed descriptions)
    t = re.sub(r'\s*[–\-]\s*.*$', '', t)
    # Remove leading numbers like "1." or "1)"
    t = re.sub(r'^\d+[\.\)]\s*', '', t)
    return t.strip()


def deduplicate_topics(raw_topics):
    """
    Removes duplicate topics from AI response.
    Keeps the LONGEST (most detailed) version of each unique topic.
    """
    seen_cores = {}

    for t in raw_topics:
        if isinstance(t, str):
            title = t.strip()
        elif isinstance(t, dict):
            title = (t.get('title') or t.get('name') or '').strip()
        else:
            continue

        if not title:
            continue

        core = normalize_topic_title(title)
        if not core:
            continue

        # Keep the longest (most detailed) version
        if core not in seen_cores or len(title) > len(seen_cores[core]):
            seen_cores[core] = title

    # Rebuild clean list
    clean_topics = []
    for idx, title in enumerate(seen_cores.values()):
        clean_topics.append({
            "title": title,
            "chapter_number": idx + 1,
            "difficulty": "medium"
        })

    return clean_topics


def extract_syllabus_with_ai(syllabus_text):
    """
    Extracts ALL semester subjects including electives.
    Deduplicates topics within each subject to prevent triple-listing.
    """
    api_key = getattr(settings, 'GROQ_API_KEY', '') or os.getenv('GROQ_API_KEY', '')
    if not api_key:
        raise Exception("GROQ_API_KEY is not configured in settings or .env file.")

    client = Groq(api_key=api_key)

    compressed_text = prefilter_syllabus_text(syllabus_text)

    system_prompt = (
        "You are an expert university syllabus parser. "
        "Extract EVERY subject from the syllabus including ALL elective options. "
        "A 7th semester engineering syllabus typically has 4-6 core subjects plus 1-3 elective groups. "
        "For electives: list EACH option as a separate subject with is_elective=true. "
        "CRITICAL RULES: "
        "1. Each topic must appear ONLY ONCE per subject. "
        "2. Use the format 'Unit X: Topic Name – brief description' for each topic. "
        "3. Do NOT list the same topic in multiple formats. "
        "4. Do NOT include both short and long versions of the same topic. "
        "Output ONLY valid JSON."
    )

    user_prompt = f"""Extract ALL subjects (core + electives) with their complete unit topics.

CRITICAL: Each topic must appear EXACTLY ONCE. Use format "Unit X: Name – description".
Do NOT repeat topics in different formats.

JSON Schema:
{{
    "subjects": [
        {{
            "name": "Computer Networks",
            "code": "BCE603",
            "is_elective": false,
            "elective_group": null,
            "topics": [
                "Unit 1: Introduction to Computer Network – definition, models, devices",
                "Unit 2: Physical Layer – capacity, delay, bandwidth",
                "Unit 3: Data Link Layer – error detection, CRC, HDLC"
            ]
        }},
        {{
            "name": "Machine Learning",
            "code": "BCE6804",
            "is_elective": true,
            "elective_group": "Elective-I",
            "topics": [
                "Unit 1: Introduction to ML – supervised learning basics",
                "Unit 2: Unsupervised Learning – clustering algorithms"
            ]
        }}
    ]
}}

Syllabus Text:
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
            key=lambda name: (
                0 if '3.3-70b' in name else
                1 if '70b' in name else
                2 if '8b' in name else
                3
            )
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
                max_tokens=3000,
                response_format={"type": "json_object"}
            )
            raw_content = response.choices[0].message.content.strip()

            if "```" in raw_content:
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_content, re.DOTALL)
                if match:
                    raw_content = match.group(1)

            parsed = json.loads(raw_content)

            normalized_subjects = []
            raw_subjects = parsed.get('subjects') or parsed.get('s') or []

            for subj in raw_subjects:
                name = subj.get('name') or subj.get('n') or ''
                code = subj.get('code') or subj.get('c') or ''
                is_elective = subj.get('is_elective', False)
                elective_group = subj.get('elective_group') or subj.get('eg') or None
                raw_topics = subj.get('topics') or subj.get('t') or []

                # DEDUPLICATE topics within this subject
                clean_topics = deduplicate_topics(raw_topics)

                if name.strip():
                    normalized_subjects.append({
                        "name": name.strip(),
                        "code": code.strip() if code else None,
                        "description": f"Curriculum for {name.strip()}",
                        "is_elective": bool(is_elective),
                        "elective_group": elective_group.strip() if elective_group else None,
                        "topics": clean_topics
                    })

            if normalized_subjects:
                core_count = sum(1 for s in normalized_subjects if not s['is_elective'])
                elective_count = sum(1 for s in normalized_subjects if s['is_elective'])
                total_topics = sum(len(s['topics']) for s in normalized_subjects)
                print(f"✅ [Syllabus]: {core_count} core + {elective_count} elective subjects, {total_topics} unique topics (model: {model_name})")
                return {"semester": 7, "subjects": normalized_subjects}

        except Exception as e:
            last_err = e
            print(f"[Syllabus Parser '{model_name}' failed]: {e}")
            continue

    raise Exception(f"Syllabus extraction failed: {str(last_err)}")