<!-- ![banner](./.misc/crimson%20banner%20-%20ChatGPT.png) -->
<h1 align="center">
    <!-- <img src="./.misc/cover.png" width="100%"/> -->
    Secretary Lulu
    <!-- <br> -->
</h1>

> <img align="right" alt="cover" src="./.misc/cover.png" width=25% height=25%>
> Stop looking up words. Start living them.
In the flow of reading or browsing, every unfamiliar word is an opportunity lost to the friction of switching tabs.
Sec. Lulu - an AI language learning assistant - hopes to bridge that gap by **recording new words as you go** (clipboard or OCR), tailoring them into a **structured learning program** just for you. Instead of static dictionary entries, you receive AI-driven insights, usage examples, and creative stories that turn abstract characters into memorable concepts.

The setup is local, no cloud, no data collection. Just you and your language learning journey.

**Currently supporting:**

- Chinese

**To-Do:**

- [x] Learner's word database
- [x] Repeated scanned word: explain mindfully + update revision (3-4)
- [x] Side panel (always-on-top) for start/pausing operations
- [x] **Anki-based** word review session
- [x] Home: Challenge generator
- [x] Mock database for test runs: ```python app_integrated.py --use-mock```
- [ ] Home: "What you learned" summaries
- [ ] Lite/Detailed mode: AI gives brief definition (faster) or explains word in detail
- [ ] EasyOCR integration because Powertoys OCR messed it up sometimes
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
