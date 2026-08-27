import json
import os
import re
from django.conf import settings
from groq import Groq

COLOR_PALETTE = ['indigo', 'emerald', 'rose', 'amber', 'sky', 'violet', 'orange', 'teal']


def prefilter_syllabus_text(raw_text):
    """
    Smart multi-pass curriculum distiller:
    Pass 1: Capture all lines with course/subject/unit/elective markers.
    Pass 2: If elective blocks detected, ensure ALL option lines are captured.
    Pass 3: Fallback to condensed raw text if too few lines matched.
    """
    lines = raw_text.splitlines()
    relevant_lines = []

    # Broad pattern matching curriculum content + electives
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

    # Elective-specific pattern to catch option blocks
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

        # Detect start of elective block
        if is_elective_line and 'elective' in cleaned.lower():
            in_elective_block = True
            elective_buffer = [cleaned]
            continue

        # Inside elective block: capture all option lines
        if in_elective_block:
            elective_buffer.append(cleaned)
            # End of elective block when we hit a new major heading or empty gap
            if is_course_line and 'elective' not in cleaned.lower() and len(elective_buffer) > 3:
                relevant_lines.extend(elective_buffer)
                in_elective_block = False
                elective_buffer = []
                if is_course_line:
                    relevant_lines.append(cleaned)
            continue

        if is_course_line:
            relevant_lines.append(cleaned)

    # Flush any remaining elective buffer
    if elective_buffer:
        relevant_lines.extend(elective_buffer)

    # Fallback if filter was too aggressive
    if len(relevant_lines) < 25:
        compact_text = re.sub(r'\s+', ' ', raw_text).strip()
        return compact_text[:12000]

    filtered_text = "\n".join(relevant_lines)
    # 12,000 chars is approximately 2,800 tokens (still well under 8,000 TPM with 2,200 max output)
    return filtered_text[:12000]


def extract_syllabus_with_ai(syllabus_text):
    """
    Extracts ALL semester subjects including electives and their options.
    Handles incomplete subjects by requesting comprehensive extraction.
    """
    api_key = getattr(settings, 'GROQ_API_KEY', '') or os.getenv('GROQ_API_KEY', '')
    if not api_key:
        raise Exception("GROQ_API_KEY is not configured in settings or .env file.")

    client = Groq(api_key=api_key)

    # 1. Distill curriculum text
    compressed_text = prefilter_syllabus_text(syllabus_text)

    # 2. Comprehensive prompt with elective handling
    system_prompt = (
        "You are an expert university syllabus parser. "
        "Extract EVERY subject from the syllabus including ALL elective options. "
        "A 7th semester engineering syllabus typically has 4-6 core subjects plus 1-3 elective groups. "
        "For electives: list EACH option as a separate subject with is_elective=true and the elective_group name. "
        "For core subjects: ensure ALL units are captured, not just the first few. "
        "Output ONLY valid JSON matching the schema."
    )

    user_prompt = f"""Extract ALL subjects (core + electives) and their complete unit topics.

JSON Schema:
{{
    "subjects": [
        {{
            "name": "Theory of Computation",
            "code": "BCE604",
            "is_elective": false,
            "elective_group": null,
            "topics": [
                "Unit 1: Finite Automata and Regular Languages",
                "Unit 2: Context-Free Grammars and Pushdown Automata",
                "Unit 3: Turing Machines and Decidability",
                "Unit 4: Complexity Theory"
            ]
        }},
        {{
            "name": "Machine Learning",
            "code": "BCE6804",
            "is_elective": true,
            "elective_group": "Elective-I",
            "topics": [
                "Unit 1: Introduction to ML and Supervised Learning",
                "Unit 2: Unsupervised Learning and Clustering",
                "Unit 3: Neural Networks and Deep Learning"
            ]
        }},
        {{
            "name": "Data Mining and Data Warehousing",
            "code": "BCE6800",
            "is_elective": true,
            "elective_group": "Elective-I",
            "topics": [
                "Unit 1: Data Preprocessing and Exploration",
                "Unit 2: Association Rule Mining",
                "Unit 3: Data Warehouse Architecture"
            ]
        }}
    ]
}}

IMPORTANT:
- Include ALL core subjects with ALL their units (do not truncate)
- Include ALL elective options as separate subjects
- Each elective option gets its own entry with the same elective_group name
- If a subject has 4-5 units, list ALL of them

Syllabus Text:
---
{compressed_text}
---"""

    # 3. Discover active models
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

            # Strip markdown wrappers
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
                is_elective = subj.get('is_elective', False)
                elective_group = subj.get('elective_group') or subj.get('eg') or None
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
                        "is_elective": bool(is_elective),
                        "elective_group": elective_group.strip() if elective_group else None,
                        "topics": topics_list
                    })

            if normalized_subjects:
                core_count = sum(1 for s in normalized_subjects if not s['is_elective'])
                elective_count = sum(1 for s in normalized_subjects if s['is_elective'])
                print(f"✅ [Syllabus Success]: Extracted {core_count} core + {elective_count} elective subjects with model '{model_name}'")
                return {"semester": 7, "subjects": normalized_subjects}

        except Exception as e:
            last_err = e
            print(f"[Syllabus Parser: '{model_name}' failed]: {e}")
            continue

    raise Exception(f"Syllabus extraction failed: {str(last_err)}")