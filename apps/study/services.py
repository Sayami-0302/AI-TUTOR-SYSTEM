import json
import os
import re
from django.conf import settings
from groq import Groq

COLOR_PALETTE = ['indigo', 'emerald', 'rose', 'amber', 'sky', 'violet', 'orange', 'teal']


def prefilter_syllabus_text(raw_text):
    """
    Python-only heuristic filter (0 API tokens):
    Filters out administrative boilerplate and keeps only lines
    containing course titles, unit headers, and topic keywords.
    """
    lines = raw_text.splitlines()
    relevant_lines = []
    
    # Keywords indicating curriculum content
    keywords = re.compile(
        r'(unit|chapter|module|course|code|credit|semester|hours|part|topic|introduction|'
        r'algorithm|system|management|network|data|software|engineering|design|theory|'
        r'programming|analysis|architecture|\b[I|V|X]+\b|\d+\.\d+)', 
        re.IGNORECASE
    )

    for line in lines:
        cleaned = line.strip()
        # Drop very short noise or pure numbers
        if len(cleaned) < 3 or cleaned.isdigit():
            continue
        # Keep lines that match syllabus markers
        if keywords.search(cleaned):
            relevant_lines.append(cleaned)

    # If filter was too aggressive, fallback to compact raw text
    if len(relevant_lines) < 10:
        compact_text = re.sub(r'\s+', ' ', raw_text).strip()
        return compact_text[:4000]

    filtered_text = "\n".join(relevant_lines)
    # Hard cap at 4,500 chars (~1,000 tokens)
    return filtered_text[:4500]


def extract_syllabus_with_ai(syllabus_text):
    """
    Ultra-token-efficient syllabus parser.
    Uses ultra-terse prompts and compact JSON schemas to minimize TPM footprint.
    """
    api_key = getattr(settings, 'GROQ_API_KEY', '') or os.getenv('GROQ_API_KEY', '')
    if not api_key:
        raise Exception("GROQ_API_KEY is not configured in settings or .env file.")

    client = Groq(api_key=api_key)

    # 1. Local Python Token Compression
    compressed_text = prefilter_syllabus_text(syllabus_text)

    # 2. Minimalist, dense prompt (< 150 tokens)
    system_prompt = "University syllabus parser. Return ONLY compact JSON. No conversational text."
    
    user_prompt = f"""Extract subjects and unit topics from this text.
Schema:
{{"s": [{{"n": "Subject Name", "c": "CS401", "t": ["Unit 1: Topic", "Unit 2: Topic"]}}]}}

Text:
{compressed_text}"""

    # Primary high-speed, high-allowance model
    candidate_models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant"
    ]

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
                max_tokens=900,  # Strict cap to prevent runaway token usage
                response_format={"type": "json_object"}
            )
            raw_content = response.choices[0].message.content.strip()

            # Clean markdown wrappers if any
            if "```" in raw_content:
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_content, re.DOTALL)
                if match:
                    raw_content = match.group(1)

            parsed = json.loads(raw_content)
            
            # Normalize compact keys ('s', 'n', 'c', 't') back into standard keys
            normalized_subjects = []
            raw_subjects = parsed.get('s') or parsed.get('subjects') or []

            for subj in raw_subjects:
                name = subj.get('n') or subj.get('name') or ''
                code = subj.get('c') or subj.get('code') or ''
                raw_topics = subj.get('t') or subj.get('topics') or []

                topics_list = []
                for idx, t in enumerate(raw_topics):
                    if isinstance(t, str):
                        topics_list.append({"title": t, "chapter_number": idx + 1, "difficulty": "medium"})
                    elif isinstance(t, dict):
                        topics_list.append({
                            "title": t.get('title') or t.get('name') or f"Topic {idx+1}",
                            "chapter_number": t.get('chapter_number', idx + 1),
                            "difficulty": t.get('difficulty', 'medium')
                        })

                if name:
                    normalized_subjects.append({
                        "name": name,
                        "code": code,
                        "description": f"Syllabus curriculum for {name}",
                        "topics": topics_list
                    })

            if normalized_subjects:
                print(f"✅ [Token Success]: Parsed {len(normalized_subjects)} subjects with model {model_name}")
                return {"semester": 7, "subjects": normalized_subjects}

        except Exception as e:
            last_err = e
            print(f"[Token Parser Retry on {model_name}]: {e}")
            continue

    raise Exception(f"Syllabus extraction failed: {str(last_err)}")