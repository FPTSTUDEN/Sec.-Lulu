<!-- ![banner](./.misc/crimson%20banner%20-%20ChatGPT.png) -->
<h1 align="center">
    <!-- <img src="./.misc/cover.png" width="100%"/> -->
    Secretary Lulu
    <!-- <br> -->
</h1>

> <img align="right" alt="cover" src="./.misc/cover.png" width=25% height=25%>
Sec. Lulu is an AI language learning assistant that records new words as you go (clipboard or OCR), tailoring them into a structured learning program just for you.

The setup is local, no cloud, no data collection. Just you and your language learning journey.

**Currently supporting:**

- Chinese

**To-Do:**

- [x] Learner's word database for SRS and future features
- [x] Repeated scanned word: explain mindfully + update revision (3-4)
- [x] Side panel (always-on-top) for start/pausing operations
- [x] Review section for word revision
- [x] Home: Challenge generator
- [x] Mock database for test runs: ```python app_integrated.py --use-mock```
- [ ] EasyOCR integration because Powertoys OCR messed it up sometimes
- [ ] Home: "What you learned" summaries
- [ ] Personality-rich **AI profile**, flexibly blending both languages
- [ ] PaddleOCR integration
- [ ] Proper UI

## Tech stack

- **Python** for core logic
- **Ollama**: Qwen

## Features (in progress)

- Monitors clipboard for new words
- Organises word learning data into a personal profile
- Daily "What you learned" summaries with tips, reviews and exercises

## Bugs

- Sometimes new clipboard words are not registered
- invalid command name "1804464740544\< lambda \>"
- bgerror failed to handle background error.
    Original error: invalid command name "1804464659968check_dpi_scaling"
    Error in bgerror: can't invoke "tk" command: application has been destroyed

## Credits

- Mengshen font: Copyright 2020 mengshen project with Copyright 2020 LXGW
- [Perchance](https://perchance.org/text-to-image-plugin)
