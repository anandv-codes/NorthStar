from .supabase import get_note_item, update_note_item
from .bedrock import call_bedrock_api
import re
import json

#TODO SHIFT TO LAMBDA

def process_note_job(user_id: str, note_id: str):
    print(f"[NOTE_PROCESSOR] Processing note_id={note_id} for user_id={user_id}")
    note = get_note_item(user_id=user_id, note_id=note_id)
    if not note:
        print(f"[NOTE_PROCESSOR] Note not found: {note_id}")
        return

    print(f"[NOTE_PROCESSOR] Extracting summary and action items")
    parsed = parse_note_text(note["raw_text"])
    prompt = generate_bedrock_prompt(parsed)
    response = call_bedrock_api(prompt)

def parse_note_text(raw_text: str) -> dict:
    action_items = []
    questions = []
    strippedLines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    normalized_text = "\n".join(strippedLines)
   
    for line in strippedLines:
        lower = line.lower()
        if re.search(r"\b(todo|action item|follow up|next step)\b", lower):
            action_items.append(line)
        if line.strip().endswith("?"):
            questions.append(line)
    return {
        "normalized_text": normalized_text,
        "action_items": action_items,
        "questions": questions,
    }

def generate_bedrock_prompt(parsed_text: dict) -> str:
    return f"""
    You are an assistant that processes daily journal notes and extracts key information.

    Raw notes:
    {parsed_text['normalized_text']}

    Action items identified:
        {json.dumps(parsed_text['action_items'], indent=2)}

    Questions identified:
        {json.dumps(parsed_text['questions'], indent=2)}

    
    Please provide the following:
    1. A concise summary of the notes (max 250 characters).
    2. Expand on the list of action items mentioned in the notes (the provided action items are not foolproof).
    3. Answer the questions that arise from the notes.
    4. Any insights or observations (max 2) that can be drawn from the notes.
    
    Format your response as JSON with the following structure:
    {{
        "summary": "Concise summary here",
        "action_items": ["Action item 1", "Action item 2"],
        "questions": ["Question 1?", "Question 2?"]
        "insights": ["Insight 1", "Insight 2"]
    }}
    """



