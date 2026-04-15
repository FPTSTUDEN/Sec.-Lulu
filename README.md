<!-- ![banner](./.misc/crimson%20banner%20-%20ChatGPT.png) -->
<h1 align="center">
    <!-- <img src="./.misc/cover.png" width="100%"/> -->
    Secretary Lulu
    <!-- <br> -->
</h1>

> <img align="right" alt="cover" src="./.misc/cover.png" width=35% height=35%>

> <img align="right" alt="cards" src="./.misc/cards.png" width=35% height=35%>
> Stop looking up words. Start living them.
In the flow of reading or browsing, every unfamiliar word is an opportunity lost to the friction of switching tabs. Sec. Lulu - an AI language learning assistant - hopes to bridge that gap by **recording new words as you go** (clipboard or OCR), tailoring them into a **structured learning program** just for you.

Instead of static dictionary entries, you receive AI-driven insights, usage examples, and creative stories that turn abstract characters into memorable concepts.</p>

The setup is local, no cloud, no data collection. Just you and your language learning journey.

**Currently supporting:**

- Chinese

## Features

- Monitors clipboard for new words
- Organises word learning data into a personal profile
- *Daily "What you learned" summaries with tips, reviews and exercises (in progress*)

> <img align="right" alt="cover" src="./.misc/example.png" width=35% height=35%>
<p>

### Modes

- **Lookup-only**: fastest, searches individual words on local dictionary
- **Simple**: fast, short,concise response from AI
- **Detailed**: immersive response from AI

**To-Do:**

- [x] **Anki-based** word review session
- [x] Home: Better "What you learned" summaries (scrollable box, update AI profile)
- [ ] AI flexibly blending both languages (When a volcano erupts, magma will喷出 from the volcano's口)
- [ ] Review mode (6)
- [ ] Full Sentence mode(word pick UI: show translation + quick def +  switch to mixed language) (integrated revision, better explanation on long-complex sentences)
- [ ] better challenge
- [ ] More test cases for each mode for debugging
- [ ] More features
- [ ] Renewed UI
- [ ] EasyOCR integration because Powertoys OCR messed it up sometimes

- [ ] Initial clipboard data isn't sent
- [ ] Card UI
- [ ] TTS
- [ ] Bunch of db.py and reviewer.py errors
- [ ] Removing None from ControlPanel breaks everything

## Tech stack

- **Python** for core logic
- **Ollama**: Qwen

## Installation guide

Please refer to the [GUIDE.md](./GUIDE.md) file

## Bugs

- Sometimes new clipboard words are not registered
- invalid command name "1804464740544\< lambda \>"
- bgerror failed to handle background error.
    Original error: invalid command name "1804464659968check_dpi_scaling"
    Error in bgerror: can't invoke "tk" command: application has been destroyed

## Credits

- Mengshen font: Copyright 2020 mengshen project with Copyright 2020 LXGW
- [Perchance](https://perchance.org/text-to-image-plugin)
