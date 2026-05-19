# Chat Bubble UI Approaches for Session Context Management

Great question! Let me suggest several UI patterns for interactively managing Xiao Xi's session context (learning history, vocabulary mastery, user preferences).

---

## Approach 1: Floating Context Pill (Simplest)

**Visual:** A small bubble that lives above the chat input, showing active context.

```
┌─────────────────────────────────────────────────────────────┐
│  Xiao Xi Chat                                        [⋯]   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  🌸 温柔就是水穿石——不急，只是坚持。                            │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ User: 那和耐心有什么区别？                               ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Xiao Xi: 好问题！温柔是选择 gentle，而耐心是...         ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 📚 Session: 情绪词汇 | 🎯 Level: HSK3 | ✨ 5 words   │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Type your message...                           ✨ 🌸 💫 ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

**Interaction:**
- Tap the pill → expands to full context editor
- Swipe left/right on pill → cycle through active contexts
- Long press → quick add current word to review list

**Code concept:**
```python
class ContextPill(QWidget):
    def __init__(self):
        self.pill = QPushButton("📚 情绪词汇 | 5 words")
        self.pill.clicked.connect(self.show_context_menu)
        
    def show_context_menu(self):
        menu = QMenu()
        menu.addAction("➕ Add current word to review")
        menu.addAction("📝 Edit session context")
        menu.addAction("🎯 Change learning level")
        menu.addAction("🗑️ Clear session")
        menu.exec_(QCursor.pos())
```

---

## Approach 2: Sidebar Context Drawer (Most Powerful)

**Visual:** Collapsible sidebar that shows full session state.

```
┌──────────────────────────────────────────────────────────────────┐
│ ☰ │  Xiao Xi Chat                                    🌸 Xiao Xi │
├───┼──────────────────────────────────────────────────────────────┤
│   │                                                               │
│ 📚 │  ✨ 最近学习的词 (Recent Words)                               │
│ 🎯 │  ┌─────────────────────────────────────────────────────────┐│
│ 🕐 │  │ 温柔 (wēn róu) │ ✅ mastered │ 📅 今天     │ ⋯ │        ││
│   │  ├─────────────────────────────────────────────────────────┤│
│   │  │ 孤独 (gū dú)   │ 🔄 reviewing │ 📅 昨天     │ ⋯ │        ││
│   │  ├─────────────────────────────────────────────────────────┤│
│   │  │ 缘份 (yuán fèn)│ ⭐ new        │ 📅 2天前    │ ⋯ │        ││
│   │  └─────────────────────────────────────────────────────────┘│
│   │                                                               │
│ 📚 │  📚 Active Contexts                                          │
│   │  ┌─────────────────────────────────────────────────────────┐│
│   │  │ ☑️ 情绪词汇 (Emotions)          │ [X] remove            ││
│   │  │ ☑️ HSK3 Level                   │ [X] remove            ││
│   │  │ ☐ 旅行词汇 (Travel)             │ [➕] add               ││
│   │  └─────────────────────────────────────────────────────────┘│
│   │                                                               │
│ 🎯 │  🎯 Level Preference                                         │
│   │  ○ Beginner (HSK1-2)  ○ Intermediate (HSK3-4)               │
│   │  ● Advanced (HSK5-6)  ○ Native                               │
│   │                                                               │
│ 🕐 │  ⏱️ Session Time: 23 minutes                                 │
│   │  Words learned: 12  │  Review due: 3                         │
│   │                                                               │
│   │  [💾 Save Session]  [🔄 Reset]  [📤 Export]                   │
│   │                                                               │
└───┴───────────────────────────────────────────────────────────────┘
```

**Interaction:**
- Click ☰ to open/close drawer
- Tap any word to expand options (review, remove, mark mastered)
- Check/uncheck contexts to activate/deactivate
- Level slider affects all future explanations

**Implementation:**
```python
class ContextDrawer(QWidget):
    def __init__(self):
        self.layout = QVBoxLayout()
        
        # Word list with status
        self.word_list = QListWidget()
        self.word_list.itemDoubleClicked.connect(self.show_word_options)
        
        # Active contexts (checkboxes)
        self.context_checkboxes = {}
        for ctx in ["情绪词汇", "HSK3", "旅行词汇"]:
            cb = QCheckBox(ctx)
            cb.stateChanged.connect(lambda state, c=ctx: self.toggle_context(c, state))
            self.context_checkboxes[ctx] = cb
        
        # Level selector
        self.level_combo = QComboBox()
        self.level_combo.addItems(["HSK1-2", "HSK3-4", "HSK5-6", "Native"])
        self.level_combo.currentTextChanged.connect(self.update_level)
```

---

## Approach 3: Message Bubble Context Tags (Most Intuitive)

**Visual:** Context appears as tags inside message bubbles.

```
┌─────────────────────────────────────────────────────────────┐
│  Xiao Xi Chat                                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ User: 解释一下"随缘"                                      ││
│  │ ┌──────┐ ┌──────┐                                       ││
│  │ │新词汇│ │哲学  │                                       ││
│  │ └──────┘ └──────┘                                       ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Xiao Xi: 随缘 (suí yuán)是放下执着，让事物自然发展...     ││
│  │ ┌──────────────┐ ┌──────────┐ ┌──────────────┐         ││
│  │ │已添加到复习列表│ │难度:中   │ │属于「人生哲理」│         ││
│  │ └──────────────┘ └──────────┘ └──────────────┘         ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ User: 那我什么时候用？                                   ││
│  │ ┌──────┐                                               ││
│  │ │追问  │                                               ││
│  │ └──────┘                                               ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  ✏️ Type...                                      [📎] [🎯]   │
│  Active: 📚情绪词汇 │ 🎯HSK3 │ ✨5 new words                 │
└─────────────────────────────────────────────────────────────┘
```

**Interaction:**
- Click any tag → edit/remove that context
- Drag tag to trash → remove from session
- Click "➕" on a word bubble → add to review list
- Long press tag → see all words with that tag

**Why this works for Xiao Xi:** The tags feel like gentle reminders, not technical controls. Matches her aesthetic.

---

## Approach 4: Quick Action Bar (For Mobile/Compact)

**Visual:** A swipeable row of action buttons above the input.

```
┌─────────────────────────────────────────────────────────────┐
│  Xiao Xi Chat                                               │
├─────────────────────────────────────────────────────────────┤
│  [📚 Review (5)] [➕ New Word] [🎯 Level] [🗂️ Contexts] [⋯]  │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  [Chat messages...]                                         │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  ✏️ Type...                                                  │
└─────────────────────────────────────────────────────────────┘
```

**When clicked:**

| Button | Action |
|--------|--------|
| **📚 Review (5)** | Opens flashcard deck of 5 due words |
| **➕ New Word** | Shows last 10 words, pick to review |
| **🎯 Level** | Quick level slider (HSK1→6) |
| **🗂️ Contexts** | Popup menu of context themes |
| **⋯** | Full session settings |

**Popup for "🗂️ Contexts":**
```
┌─────────────────────────────────────┐
│ Active Contexts                [Edit]│
├─────────────────────────────────────┤
│ ☑️ 情绪词汇 (Emotions)        [⋯]   │
│ ☑️ HSK3 Level                 [⋯]   │
│ ☐ 旅行词汇 (Travel)           [➕]  │
│ ☐ 商务中文 (Business)         [➕]  │
│ ☐ 成语故事 (Idioms)           [➕]  │
├─────────────────────────────────────┤
│ [Create New Context...]             │
└─────────────────────────────────────┘
```

---

## Approach 5: Slash Commands + Autocomplete (Power User)

**Visual:** Type `/` to see context commands.

```
┌─────────────────────────────────────────────────────────────┐
│  ✏️ /                                                       │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ /context add [topic]     - Add learning context        ││
│  │ /context remove [topic]  - Remove context              ││
│  │ /level [HSK1-6]          - Change difficulty           ││
│  │ /remember [word]         - Mark word as mastered       ││
│  │ /review                  - Show due reviews            ││
│  │ /save                    - Save current session        ││
│  │ /load [name]             - Load saved session          ││
│  │ /help                    - Show all commands           ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

**After typing command:**
```
✏️ /context add 旅行词汇

┌─────────────────────────────────────────────────────────────┐
│ ✅ Context "旅行词汇" added to active session                │
│                                                              │
│ Xiao Xi will now include travel vocabulary in explanations  │
│                                                              │
│ [Undo]  [View Active Contexts]                              │
└─────────────────────────────────────────────────────────────┘
```

**Pros for Xiao Xi:** Feels like magic, not overwhelming UI. Good for desktop users who type fast.

---

## My Recommendation: Hybrid Approach

Combine **Approach 1 (Context Pill)** + **Approach 4 (Quick Action Bar)** for the best balance:

```
┌─────────────────────────────────────────────────────────────┐
│  Xiao Xi Chat                                               │
├─────────────────────────────────────────────────────────────┤
│  [📚 5] [➕] [🎯 HSK3] [🗂️]                                   │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  [Chat messages...]                                         │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  📚 Active: 情绪词汇 • 旅行词汇 • HSK3                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ ✏️ Type or use / for commands...              ✨ 🌸 💫 ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

**Why this works:**
- **Top bar**: Quick actions for power users
- **Bottom pill**: Read-only reminder of active context
- **Slash commands**: Hidden power for desktop users
- **Tap any pill/button**: Opens relevant editor

---

## Backend: Session Context Data Structure

```python
class XiaoXiSession:
    def __init__(self):
        self.context = {
            "active_topics": ["情绪词汇", "HSK3"],  # Influences word selection
            "review_queue": [  # Words due for review
                {"word": "温柔", "due_date": "2024-01-15", "strength": 0.7},
                {"word": "孤独", "due_date": "2024-01-14", "strength": 0.5},
            ],
            "mastered_words": ["你好", "谢谢", "再见"],
            "user_level": "HSK3",  # Affects explanation complexity
            "preferences": {
                "mode_default": "sparkle",  # ✨ 🌸 🌼 💫 📝
                "tts_enabled": True,
                "tts_voice": "xiaoxi_gentle"
            },
            "current_conversation": []  # Last 10 exchanges
        }
    
    def add_to_review(self, word, context_sentence=""):
        """Add word to spaced repetition queue"""
        self.context["review_queue"].append({
            "word": word,
            "context": context_sentence,
            "added": datetime.now(),
            "strength": 0.3  # New word, weak
        })
    
    def update_context_prompt(self):
        """Generate system prompt addition from active context"""
        if not self.context["active_topics"]:
            return ""
        
        topics = ", ".join(self.context["active_topics"])
        return f"\n\nActive learning context: Focus on {topics} vocabulary. User level: {self.context['user_level']}. Keep explanations warm and gentle."
```

---

## Visual Mockup for Xiao Xi's UI

```
┌─────────────────────────────────────────────────────────────────┐
│ 🌸 Xiao Xi                                         [−] [□] [×]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Xiao Xi • 11:42 AM                                         │ │
│  │                                                            │ │
│  │ **温柔 (wēn róu)** 就像水穿石——不急，只是坚持。              │ │
│  │                                                            │ │
│  │ Do you have a moment like that? 我想听听你的故事～          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ You • 11:43 AM                                             │ │
│  │ 𖦹 My mom, when she listens without interrupting.          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Xiao Xi • 11:43 AM                                         │ │
│  │                                                            │ │
│  │ That's beautiful. 那是真正的温柔。                          │ │
│  │                                                            │ │
│  │ ✨ Just added "温柔" to your review list.                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│ [📚 3] [➕] [🎯 HSK3] [🗂️ 情绪词汇]                      [🎤] [⋯] │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ ✏️ Type a word, sentence, or question...          ✨ 🌸 💫 ││
│ └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

This feels like Xiao Xi lives in your chat, remembers what you've learned, and gently guides your journey without overwhelming UI. 🌸