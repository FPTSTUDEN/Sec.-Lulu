#!/usr/bin/env python
"""Test script for hover lookup feature"""

from lib.ccedict import extract_chinese_word_at_position, is_chinese_char, lookup_cedict, load_cedict_entries

# Test is_chinese_char
print("Testing is_chinese_char:")
print(f"  中 is Chinese: {is_chinese_char('中')}")
print(f"  A is Chinese: {is_chinese_char('A')}")
print()

# Test extract_chinese_word_at_position with longest-match
text = "你好世界，这是一个测试"
print(f"Text: {text}")
print()

# Load CEDICT to test longest-match
_, word_index, char_index, char_def_index = load_cedict_entries("cedict_ts.u8")
print("Testing extract_chinese_word_at_position (longest-match from position):")
print()

# Test various positions
test_positions = [0, 1, 2, 3, 5, 7, 10]
for pos in test_positions:
    if pos < len(text):
        word, start, end = extract_chinese_word_at_position(text, pos, word_index)
        if word:
            print(f"  Position {pos} ('{text[pos]}'): extracted '{word}' [{start}:{end}]")
        else:
            print(f"  Position {pos} ('{text[pos]}'): no valid word found")

print()
print("Testing lookup_cedict with char_def_index (ONLY single-char definitions):")
test_words = ["你好", "世界", "一个", "测试", "xyz"]
for w in test_words:
    entry, chars = lookup_cedict(w, word_index, char_def_index)
    if entry:
        print(f"  {w}: Found (pinyin: {entry['pinyin']})")
    elif chars:
        print(f"  {w}: Character matches {len(chars)}")
        for char, char_entry in chars:
            print(f"       {char}: {char_entry['pinyin']}")
    else:
        print(f"  {w}: No match")
