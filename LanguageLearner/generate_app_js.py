import json
import re

with open('transcript_en.json', 'r', encoding='utf-8') as f:
    en_data = json.load(f)[0]
    
with open('transcript.json', 'r', encoding='utf-8') as f:
    ko_data = json.load(f)[0]

def find_closest_ko(start_time):
    closest = None
    min_diff = 9999
    for item in ko_data:
        diff = abs(item['start'] - start_time)
        if diff < min_diff:
            min_diff = diff
            closest = item
    return closest['text'] if closest and min_diff < 5 else ""

mock_transcript = []
for i, item in enumerate(en_data[:100]): # Limit to first 100 lines for performance in UI
    text = item['text'].replace('\n', ' ')
    start = item['start']
    duration = item['duration']
    
    # Find closest Korean translation
    ko_text = find_closest_ko(start).replace('\n', ' ')
    
    # Let's extract some words to act as "important expressions"
    words = text.split()
    word_objs = []
    
    # To keep it simple, we just make the whole sentence hoverable, 
    # or just highlight words longer than 5 letters as "expressions"
    
    for w in words:
        clean_w = re.sub(r'[^\w\s]', '', w)
        if len(clean_w) >= 6:
            # Highlight this as an expression
            word_objs.append({
                "text": w,
                "mean": f"표현: {clean_w} (문장 뜻: {ko_text})",
                "pron": ""
            })
        else:
            word_objs.append({
                "text": w,
                "mean": "",
                "pron": ""
            })

    mock_transcript.append({
        "startTime": start,
        "endTime": start + duration,
        "text": text,
        "words": word_objs
    })

# Now we rewrite app.js
with open('app.js', 'r', encoding='utf-8') as f:
    app_js = f.read()

# Replace the mockTranscript array
new_js = "const mockTranscript = " + json.dumps(mock_transcript, indent=2, ensure_ascii=False) + ";\n"
new_js += app_js[app_js.find("let player;"):]

with open('app.js', 'w', encoding='utf-8') as f:
    f.write(new_js)

print("app.js updated successfully")
