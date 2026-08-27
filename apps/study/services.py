import json
import os
import re
from django.conf import settings
from groq import Groq

COLOR_PALETTE = ['indigo', 'emerald', 'rose', 'amber', 'sky', 'violet', 'orange', 'teal']


def prefilter_syllabus_text(raw_text):
    """
    Python-only smart curriculum distiller:
    Scans the entire PDF (all pages) and extracts lines containing
    course codes, subject names, and unit headers across all courses.
    """
    lines = raw_text.splitlines()
    relevant_lines = []

    # Patterns matching course titles, codes, units, and curriculum markers
    course_pattern = re.compile(
        r'(\b(course|subject|code|credit|unit|chapter|module|part)\b|'
        r'^[A-Z]{2,4}\s*\d{3}|'
        r'\b(I|II|III|IV|V|VI|VII|VIII|IX|X)\.\s|'
        r'^\d+\.\s+[A-Z]|'
        r'(operating|database|network|software|cloud|security|compiler|web|intelligence|system|theory|graphics|algorithm))',
        re.IGNORECASE
    )

    for line in lines:
        cleaned = line.strip()
        if len(cleaned) < 3 or cleaned.isdigit():
            continue
        if course_pattern.search(cleaned):
            relevant_lines.append(cleaned)

    # If the filter was too aggressive, fallback to condensed raw text
    if len(relevant_lines) < 20:
        compact_text = re.sub(r'\s+', ' ', raw_text).strip()
        return compact_text[:8000]

    filtered_text = "\n".join(relevant_lines)
    # 8,000 characters is ~1,800 tokens (plenty of room for 6-8 subjects within 8k TPM limit)
    return filtered_text[:8500]


def extract_syllabus_with_ai(syllabus_text):
    """
    Extracts ALL semester subjects and topics from syllabus text.
    Strictly outputs compact JSON containing the complete multi-subject curriculum.
    """
    api_key = getattr(settings, 'GROQ_API_KEY', '') or os.getenv('GROQ_API_KEY', '')
    if not api_key:
        raise Exception("GROQ_API_KEY is not configured in settings or .env file.")

    client = Groq(api_key=api_key)

    # 1. Distill curriculum text from all pages
    compressed_text = prefilter_syllabus_text(syllabus_text)

    # 2. Dense instruction emphasizing ALL subjects
    system_prompt = (
        "You are an academic university curriculum parser. "
        "Your job is to extract EVERY SINGLE subject and its units from the provided syllabus text. "
        "A college engineering semester typically has 4 to 8 subjects. You must include ALL of them. "
        "Output ONLY a raw, valid JSON object following the schema. No conversation."
    )

    user_prompt = f"""Extract ALL subjects and their respective unit topics from this university syllabus.

JSON Schema:
{{
    "subjects": [
        {{
            "name": "Operating Systems",
            "code": "CS401",
            "topics": ["Unit 1: Process Management", "Unit 2: CPU Scheduling", "Unit 3: Deadlocks", "Unit 4: Memory Management"]
        }},
        {{
            "name": "Database Management Systems",
            "code": "CS402",
            "topics": ["Unit 1: ER Model", "Unit 2: Relational Algebra", "Unit 3: SQL & Normalization", "Unit 4: Transaction Management"]
        }}
    ]
}}

Syllabus Content:
---
{compressed_text}
---"""

    # 3. Discover active model dynamically
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
                max_tokens=2200,  # Room for 6-8 subjects and 40+ topics
                response_format={"type": "json_object"}
            )
            raw_content = response.choices[0].message.content.strip()

            # Strip markdown wrappers if present
            if "```" in raw_content:
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_content, re.DOTALL)
                if match:
                    raw_content = match.group(1)

            parsed = json.loads(raw_content)

            # Normalize parsed structure
            normalized_subjects = []
            raw_subjects = parsed.get('subjects') or parsed.get('s') or []

            for subj in raw_subjects:
                name = subj.get('name') or subj.get('n') or ''
                code = subj.get('code') or subj.get('c') or ''
                raw_topics = subj.get('topics') or subj.get('t') or []

                topics_list = []
                for idx, t in enumerate(raw_topics):
                    if isinstance(t, str):
                        topics_list.append({
                            "title": t.strip(),
                            "chapter_number": idx + 1,
                            "difficulty": "medium"
                        })
                    elif isinstance(t, dict):
                        topics_list.append({
                            "title": (t.get('title') or t.get('name') or f"Unit {idx+1}").strip(),
                            "chapter_number": t.get('chapter_number', idx + 1),
                            "difficulty": t.get('difficulty', 'medium')
                        })

                if name.strip():
                    normalized_subjects.append({
                        "name": name.strip(),
                        "code": code.strip() if code else None,
                        "description": f"Curriculum for {name.strip()}",
                        "topics": topics_list
                    })

            if normalized_subjects:
                print(f"✅ [Syllabus Success]: Extracted {len(normalized_subjects)} complete subjects with model '{model_name}'")
                return {"semester": 7, "subjects": normalized_subjects}

        except Exception as e:
            last_err = e
            print(f"[Syllabus Parser: '{model_name}' failed]: {e}")
            continue

    raise Exception(f"Syllabus extraction failed: {str(last_err)}")