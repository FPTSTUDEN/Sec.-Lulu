def parse_cedict_line(line):
    if line.startswith("#"):
        return None
    
    trad, simp, rest = line.split(" ", 2)
    pinyin = rest.split("]")[0][1:]
    defs = rest.split("/")[1:-1]
    
    return {
        "traditional": trad,
        "simplified": simp,
        "pinyin": pinyin,
        "definitions": defs
    }
def lookup_cedict(word, entries):
    '''Returns the definition for a given word. If the word is not found, returns definitions of individual characters.'''
    for entry in entries:
        if entry["simplified"] == word or entry["traditional"] == word:
            return entry, []
    # If not found, try character-level lookup
    char_matches = []
    for char in word:
        for entry in entries:
            if entry["simplified"] == char or entry["traditional"] == char:
                char_matches.append((char, entry))
                break
    return None, char_matches
# Load CEDICT data
entries = []
with open("cedict_ts.u8", "r", encoding="utf-8") as f:
    for line in f:
        entry = parse_cedict_line(line)
        if entry:
            entries.append(entry)

print(entries[0])

# lookup example
for entry in entries:
    if entry["simplified"] == "中国":
        print(entry)

# lookup example with character-level matching
def_word, def_chars = lookup_cedict("中国", entries)
print(f"Word: {def_word}")
print(f"Character matches: {def_chars}")
def_word, def_chars = lookup_cedict("一个中国人", entries)
print(f"Word: {def_word}")
print(f"Character matches: {def_chars}")