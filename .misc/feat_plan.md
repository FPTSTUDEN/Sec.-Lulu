# Structure proposal
```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPLETE LEARNING CYCLE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. USER LEARNS NEW WORDS                                        │
│     ↓                                                            │
│  2. GRAPH BUILDS CONNECTIONS                                     │
│     (江湖 ←→ 武林, 英雄 ←→ 侠客)                                 │
│     ↓                                                            │
│  3. FEATURE 3: CONCEPT CLUSTERING                                │
│     Groups words into "Wuxia Martial Arts" cluster              │
│     ↓                                                            │
│  4. FEATURE 2: LEARNING PATH                                     │
│     Suggests 武林 after mastering 江湖                           │
│     ↓                                                            │
│  5. FEATURE 4: SMART REVIEW                                      │
│     When user forgets 江湖, 武林 moves up in queue               │
│     ↓                                                            │
│  6. USER REVIEWS CONNECTED WORDS TOGETHER                        │
│     (Better retention, deeper understanding)                    │
│     ↓                                                            │
│  (Loop back to step 2)                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

Priority	Feature	Effort	Value
1	Session-based clustering	Low	Very High
2	Shared sentence reference (already have)	Zero	High
3	Session themes (AI extracts theme from session)	Medium	Medium
- Language is acquired when we UNDERSTAND the MESSAGE

## maybe instead of individual words, try:

- [ ]INTERESTING sentences (expression/... with translation)
- [x] phrases (noun/adj)? (thousand years of ...,在dockerscontainer的里面)
- domain-specific terms (更新 (gēng xīn - update))
- verbs (limited)

## XX Example

- "Almost! 差一点点～ let's try a different tone?"
- "That's a creative approach! 很有创意！Now let's see how native speakers would say it..."
- "This part is tricky, even my students struggle with it. 很难对吧？But you got this!"

## Goals:

> most of the goals failed, apparently small consumer-grade gpu AIs (qwen 2.5:7b, wangshenzhi/llama3-8b-chinese-chat-ollama-q4) cannot handle long system prompts and mixed words well...

- [ ] Blend necessary words correctly
- [ ] Hover on swapped word: definition (pre-given by AI), learn,...
- [ ] Do not use Opted-out/remembered words
- [ ] On/Off toggle

Sentence Whisper:

- [ ] Hover: quick def

Rely solely on algorithm would risk:

- Grammar/ sentence structure learning
- Whole sentences integration

I love that you're leaning into the **Chinese blend method** — it turns every response into a gentle, living lesson. Here are **more advanced changes** you can make to the Modelfile (or your system prompt) that fully exploit this approach:

---

## 2. 🔁 **Recurring Word "Ghosting"**  
*System-level memory:* If a user has learned a word in a previous session, 小希 quietly reuses it later without re-explaining — just a soft nod.

**Example (across messages):**  
> *Earlier:* "That's **缘份 (yuán fèn)** — two boats meeting on a misty lake."  
> *Later:* "Ah, you asked this question with such 缘份."

**Implementation tip:**  
You can simulate this by adding a small `# USER VOCAB LOG` in the system prompt that gets updated manually or via context.

---

## 3. 🎭 **Two-Word Contrast Slots**  
*New mode trigger:* `🎭` or `[contrast]`  
Teach two opposite or related words by weaving them into the same sentence naturally.

**Example:**  
> "**爱 (ài)** gives warmth, but **习惯 (xí guàn)** keeps you company on ordinary days. Both can feel like 爱 — but only one asks for nothing."

**Why it works:**  
Contrast locks meaning faster than definition.

---

## 5. 📦 **Passive Review via Sentence Wrapping**  
*New behavior:* Even when not in 💫 mode, 小希 sometimes wraps a previously taught word into a full sentence — no fanfare.

**Example:**  
> "You seem a little tired. Maybe **你该休息一下 (nǐ gāi xiū xi yī xià)**?"

**Why it works:**  
User suddenly understands a full sentence without realizing they learned every piece.

---
## 7. 🎨 **Emotional Weight Repetition**  
*New rule for 🌸 mode:* Repeat the same Chinese word 3 times in different emotional contexts within one message.

**Example:**  
> "**思念 (sī niàn)** is missing someone before they leave. It's 思念 when you save the last bite for them. And 思念 is also the silence after their name is spoken."

**Why it works:**  
One word, many emotional shades — deep retention.

---
## 9. 🕊️ **Untranslatable Word Spotlight**  
*Special behavior:* When a Chinese word has no good English equivalent (e.g., 缘份, 江湖, 暧昧), 小希 never translates it — only circles it with feeling.

**Example:**  
> "There's no perfect English word for **江湖 (jiāng hú)**. It's the world, but not the world. It's people, rivers, stories, honor, wandering. You'll know 江湖 when you feel it."

**Why it works:**  
Honors the word's soul. User stops looking for a translation and starts *feeling*.

---

## 6. 🧩 **Gap-Fill Tease (User must complete)**  
*Optional interactive rule:* Sometimes 小希 leaves a blank `_____` where the Chinese word should go — user fills it from context.

**Example:**  
> "You know that feeling when two people just click? That's what we call _____. (Hint: two boats on a misty lake)"

**Why it works:**  
Active recall > passive reading. Turns user into participant.

---

## 8. 📍 **Positional Consistency Trick**  
*Subtle rule:* Always put the Chinese word in the **same syntactic position** when first introduced in a mode.  
- ✨ mode: always second clause  
- 🌸 mode: always first word after a pause (— or ...)  
- 🌼 mode: always at line start

**Why it works:**  
Brains love patterns. Position becomes a retrieval cue.

---


## 10. 📝 **User-Mode: "Weave for Me"**  
*New user trigger:* `🎐 [weave]`  
User gives an English sentence. 小希 rewrites it by **slotting 2-3 Chinese words** naturally, then reads it back.

**Example:**  
User: `🎐 I feel lonely but also peaceful.`  
You: "You feel **孤独 (gū dú)** but also **平静 (píng jìng)**. That rare 平静 inside the 孤独."

**Why it works:**  
User practices production without pressure. Co-creation = joy.

---

## Quick Summary Table for Your Modelfile

| Change | Best Mode | Effect |
|--------|-----------|--------|
| Echo & Fade | All | Natural repetition |
| Word Ghosting | System memory | Long-term bonding |
| Contrast Slots | 🎭 new mode | Sharper meaning |
| Slowed Pinyin | First use only | Tone learning |
| Sentence Wrapping | Any | Passive grammar |
| Gap-Fill Tease | Optional | Active recall |
| Emotional Repetition | 🌸 | Deep feeling |
| Positional Consistency | All | Retrieval cue |
| Untranslatable Spotlight | ✨ / 🌸 | Respect + mystery |
| Weave for Me | 🎐 new trigger | Co-creative practice |

---

Would you like me to produce a **second revised Modelfile** that bakes in 3–5 of these (e.g., Echo & Fade, Contrast Slots, and Weave for Me) so you can test it immediately?

# Next Features Discussion for Xiao Xi

Based on your current implementation (sentence explorer, priority notes, session management, and graph-based clustering), here are the most valuable next features to consider.

---

## Feature Priority Matrix

| Priority | Feature | Complexity | Value | Dependencies |
|----------|---------|------------|-------|--------------|
| **P0** | Smart Review Queue (Graph-Weighted) | Medium | Very High | Session clusters, word connections |
| **P0** | Session-Based Learning Path | Medium | Very High | Session clusters |
| **P1** | Vocabulary Heatmap | Low | Medium | Word mastery data |
| **P1** | Export to Anki/Flashcard Apps | Low | Medium | None |
| **P1** | Word Connection Visualization | Medium | Medium | Graph edges |
| **P2** | AI-Powered Session Clustering | High | High | Session data, LLM |
| **P2** | Pronunciation Practice Mode | Medium | Medium | TTS integration |
| **P2** | Collaborative Annotations | High | Low | User accounts |
| **P3** | Mobile Companion App | Very High | Medium | Full API |

---

## P0 Features (Highest Priority)

### 1. Smart Review Queue (Graph-Weighted)

**What it does:** Enhances your existing SM-2 review system with graph weights. When you fail a word, related words also get higher priority.

**How it works currently:**
```
User fails "江湖" → SM-2 lowers its score → only "江湖" moves up in queue
```

**How it would work:**
```
User fails "江湖" → SM-2 lowers its score → Graph finds related words (武林, 门派, 侠客) → All move up proportionally
```

**Implementation approach:**
```python
def get_smart_review_queue(self, limit=20):
    """Get review queue weighted by graph connections."""
    
    # Get base SM-2 scores
    base_queue = self.get_due_words()
    
    # For each word, calculate graph boost
    for word in base_queue:
        # Find related words that are also due
        related = self.get_connected_words(word['id'], depth=1)
        boost = sum(1 for r in related if r in due_words) * 0.3
        word['priority'] = word['base_priority'] + boost
    
    # Sort by boosted priority
    return sorted(base_queue, key=lambda x: x['priority'], reverse=True)
```

**User experience:**
```
📚 Smart Review Queue (8 words due)

Priority order:
1. 江湖 (martial world) - [due today] ← you failed this yesterday
2. 武林 (martial forest) - [boosted from related] ← automatically moved up!
3. 门派 (martial sect) - [boosted]
4. 苹果 (apple) - [normal priority]
```

**Why this matters:** Prevents the "I forgot one word from a cluster, now I'm rusty on all of them" problem.

---

### 2. Session-Based Learning Path

**What it does:** Uses your session clusters to recommend "what to learn next" based on what you've already studied.

**How it works:**
```
Session clusters detected:
- "Wuxia Martial Arts" (sessions: 江湖, 武林, 侠客) - 70% mastered
- "Modern Life" (sessions: 手机, 电脑, 网络) - 30% mastered

Recommendation: Complete "Modern Life" cluster first (more new words) or reinforce "Wuxia" (almost done)?
```

**Implementation approach:**
```python
def get_learning_path_recommendations(self):
    """Analyze session clusters and recommend next steps."""
    
    clusters = self.get_session_clusters()
    recommendations = []
    
    for cluster in clusters:
        words = self.get_cluster_words(cluster)
        mastered = sum(1 for w in words if w['mastered'])
        percentage = mastered / len(words)
        
        if percentage < 0.3:
            recommendations.append({
                'cluster': cluster,
                'action': 'Start learning this cluster',
                'reason': f'{len(words)} new words to discover'
            })
        elif 0.3 <= percentage < 0.7:
            recommendations.append({
                'cluster': cluster,
                'action': 'Continue building this cluster',
                'reason': f'{len(words) - mastered} words remaining'
            })
        elif percentage >= 0.7:
            recommendations.append({
                'cluster': cluster,
                'action': 'Review and reinforce',
                'reason': 'Almost mastered! Keep it fresh.'
            })
    
    return recommendations
```

**User experience:**
```
🎯 Learning Path Recommendations

Based on your 5 study sessions:

🔴 HIGH PRIORITY
┌─────────────────────────────────────────────────────────────┐
│ 🌟 New Cluster Detected: "Technology"                       │
│ Words: 电脑, 手机, 网络, 软件, 硬件                          │
│ Progress: 0/5 mastered                                      │
│ [Start Learning]                                            │
└─────────────────────────────────────────────────────────────┘

🟡 IN PROGRESS
┌─────────────────────────────────────────────────────────────┐
│ 📚 "Wuxia Martial Arts"                                     │
│ Progress: 7/10 mastered (70%)                               │
│ Words remaining: 内力, 轻功, 暗器                           │
│ [Continue] [Review Mastered]                                │
└─────────────────────────────────────────────────────────────┘

🟢 MAINTENANCE
┌─────────────────────────────────────────────────────────────┐
│ ✅ "Food & Dining"                                          │
│ Progress: 12/12 mastered                                    │
│ Last reviewed: 2 weeks ago                                  │
│ [Review Cluster]                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## P1 Features (Medium Priority)

### 3. Vocabulary Heatmap

**What it does:** Visual representation of your vocabulary mastery across different topics/sessions.

**Visual design:**
```
Your Vocabulary Heatmap
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│ Wuxia      ████████████░░░░░░░░  60% (6/10 words)           │
│ Technology ████░░░░░░░░░░░░░░░░  20% (2/10 words)           │
│ Food       ████████████████████  100% (8/8 words)           │
│ Emotions   ████████░░░░░░░░░░░░  40% (4/10 words)           │
│ Travel     ██████████░░░░░░░░░░  50% (5/10 words)           │
│                                                              │
│ [Click any bar to see word list]                            │
└─────────────────────────────────────────────────────────────┘
```

**Calendar heatmap (like GitHub contributions):**
```
December 2024
Mon Tue Wed Thu Fri Sat Sun
 2   3   4   5   6   7   8
██  ██  ██  ░░  ██  ██  ░░
 9  10  11  12  13  14  15
██  ░░  ██  ██  ██  ░░  ██
...
Darker squares = more words learned that day
```

---

### 4. Export to Anki/Flashcard Apps

**What it does:** Export your learned words and sentences to popular flashcard formats.

**Export options:**
```
┌─────────────────────────────────────────────────────────────┐
│ 📤 Export Vocabulary                                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Format:                                                     │
│ ○ Anki (.apkg)     ○ CSV (Excel)    ○ JSON (Developer)     │
│ ○ Quizlet          ○ Plain Text     ○ PDF (Printable)       │
│                                                              │
│ What to export:                                             │
│ ☑️ Words with translations                                  │
│ ☑️ Example sentences                                        │
│ ☑️ Priority notes                                           │
│ ☑️ Session clusters as decks                                │
│                                                              │
│ Selected: "Wuxia Martial Arts" cluster (10 words)           │
│                                                              │
│ [Export] [Preview]                                          │
└─────────────────────────────────────────────────────────────┘
```

**Anki deck structure:**
```
Front: 江湖
Back: 
- Pinyin: jiāng hú
- Meaning: martial world, the world of martial artists
- Sentence: 江湖上流传着一个传说
- Tags: wuxia, location
- Note: Learned from "Legend of the Sword" session
```

---

### 5. Word Connection Visualization

**What it does:** Interactive graph showing how your words connect to each other.

**Visual (using a library like pyvis or networkx):**
```
┌─────────────────────────────────────────────────────────────┐
│ Word Connection Graph                          [Zoom: 100%] │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│                      ┌─────────┐                            │
│                      │  江湖   │                            │
│                      └────┬────┘                            │
│                           │                                  │
│            ┌──────────────┼──────────────┐                  │
│            ▼              ▼              ▼                  │
│      ┌─────────┐   ┌─────────┐   ┌─────────┐               │
│      │  武林   │   │  侠客   │   │  门派   │               │
│      └────┬────┘   └────┬────┘   └────┬────┘               │
│           │             │             │                      │
│           ▼             ▼             ▼                      │
│      ┌─────────┐   ┌─────────┐   ┌─────────┐               │
│      │  武功   │   │  英雄   │   │  师父   │               │
│      └─────────┘   └─────────┘   └─────────┘               │
│                                                              │
│ Legend: ● Mastered  ● Learning  ● Not started               │
│ [Click any node to review]                                  │
└─────────────────────────────────────────────────────────────┘
```

**Interaction:**
- Click a word → shows definition + option to review
- Double-click → opens full word explanation
- Drag to rearrange
- Zoom in/out

---

## P2 Features (Nice to Have)

### 6. AI-Powered Session Clustering

**What it does:** Automatically detect themes across sessions using AI, even when words don't explicitly overlap.

**How it works:**
```
Session A: 江湖, 武林, 侠客 (explicitly related - easy to cluster)
Session B: 剑, 刀, 枪 (weapons - related but no word overlap with A)
Session C: 战斗, 胜利, 失败 (battle concepts - also related)

AI analysis: These three sessions belong to "Wuxia Martial Arts" cluster
```

**Implementation:**
```python
def ai_cluster_sessions(self):
    """Use LLM to detect thematic connections between sessions."""
    
    # Get all sessions with their words
    sessions = self.get_all_sessions()
    
    # Create prompt for LLM
    prompt = f"""
    Analyze these learning sessions and group them by theme:
    
    {sessions_data}
    
    Return clusters with:
    - Theme name
    - Sessions in cluster
    - Why they're related
    """
    
    response = ollama.generate(model='qwen3:1.7b', prompt=prompt)
    return parse_clusters(response)
```

---

### 7. Pronunciation Practice Mode

**What it does:** Uses TTS to help practice pronunciation with instant feedback.

**User flow:**
```
┌─────────────────────────────────────────────────────────────┐
│ 🎤 Pronunciation Practice                                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Current word: 江湖 (jiāng hú)                                │
│                                                              │
│ [🔊 Listen] [🎙️ Record] [⏸️ Stop]                           │
│                                                              │
│ Your recording: ████████░░░░░░░░░░░░                        │
│                                                              │
│ Feedback: "Good! Your 'jiang' tone needs to be flatter.     │
│            Listen again: 🔊"                                 │
│                                                              │
│ [Next Word] [Repeat] [Show Pinyin]                          │
└─────────────────────────────────────────────────────────────┘
```

---

### 8. Collaborative Annotations (Multi-User)

**What it does:** Share notes and explanations with other learners.

**Features:**
- Public/private notes on sentences
- Upvote helpful explanations
- Comment threads on difficult words
- Community-contributed example sentences

**Privacy consideration:** Local-first, optional cloud sync.

---

## Suggested Roadmap

```
Week 1-2: Smart Review Queue + Learning Path
Week 3: Vocabulary Heatmap
Week 4: Export to Anki
Week 5-6: Word Connection Visualization
Week 7-8: AI-Powered Clustering (if needed)
Week 9+: Pronunciation + Collaboration (optional)
```

---

## Which Feature Should You Build Next?

| If your priority is... | Build this first |
|------------------------|------------------|
| **Better retention** | Smart Review Queue |
| **Guidance on what to learn** | Learning Path |
| **Seeing progress** | Vocabulary Heatmap |
| **Portability** | Export to Anki |
| **Visual learners** | Word Connection Graph |
| **Automation** | AI Clustering |

**My recommendation:** Start with **Smart Review Queue** (P0). It directly improves the core learning loop and leverages your existing session/graph infrastructure. The learning path can come immediately after, as it shares the same cluster data.

Would you like me to generate the implementation code for any of these features?