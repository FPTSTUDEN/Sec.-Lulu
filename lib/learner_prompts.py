def get_prompt(word,frequency):
    if frequency ==1:
        prompt = f"""Please explain this Chinese word "{word}" to a beginner learner encountering this word for the first time. Provide:
    1. Explanation in both English and Chinese
    2. One example sentence in Chinese
    Use simple language and clear formatting.
    """
    elif frequency ==2:
        prompt = f"""The learner is reviewing the Chinese word "{word}" for the {frequency} time. Please provide:
        1. A brief explanation in both English and Chinese
        2. One example sentence in Chinese
        Use simple language and clear formatting.
        """
    else:
        prompt = f"""The learner is having trouble remembering the Chinese word "{word}" after {frequency} reviews! Please provide:
        1. A memorable explanation in both English and Chinese
        2. Word-by-word meaning
        3. Example sentences in Chinese
        Use simple language and clear formatting.
        """
    return prompt