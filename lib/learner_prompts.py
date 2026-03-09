# When a volcano erupts, magma will喷出 from the volcano's口.
# Modes: 
# Sparkle Notes - a concise explanation of the word, suitable for a quick review.
# Immersion Mode - a detailed explanation of the word, including example sentences and word-by-word meaning, to help the learner fully understand and remember the word.
def get_prompt(word,frequency):
    if frequency < 3:
        prompt = f"""Immersion Mode: What does the Chinese word "{word}" mean? 
    """
    else:
        prompt = f"""Immersion Mode: Explain the Chinese word "{word}" to someone having trouble remembering it. """
    return prompt
def get_short_prompt(word,frequency):
    return f"""Sparkle Notes: What does the Chinese word "{word}" mean? """