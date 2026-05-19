Here are more clean code improvements and logic simplifications for the codebase:

## 1. **Use Dataclasses for Configuration and State**

```python
from dataclasses import dataclass, field
from typing import Optional, Callable, Tuple, List

@dataclass
class AppState:
    """Centralized application state"""
    is_generating: bool = False
    ai_opened: bool = True
    monitoring_active: bool = False
    current_mode: str = MODES[1]
    show_thinking: bool = True
    thinking_enabled: bool = False
    
@dataclass
class WordEntry:
    """Word data structure"""
    simplified: str
    traditional: str
    pinyin: str = ""
    definitions: List[str] = field(default_factory=list)
    example: str = ""
    
@dataclass
class CedictIndices:
    """Cedict lookup indices container"""
    word_index: dict = field(default_factory=dict)
    char_def_index: dict = field(default_factory=dict)
    
    @classmethod
    def load(cls):
        """Factory method to load indices"""
        try:
            from lib.ccedict import load_cedict_entries
            _, word_index, _, char_def_index = load_cedict_entries("cedict_ts.u8")
            return cls(word_index=word_index, char_def_index=char_def_index)
        except Exception:
            return cls()
```

## 2. **Extract Theme Management**

```python
class ThemeManager:
    """Centralized theme configuration"""
    THEMES = {
        "dark": {
            "bg": ("gray85", "gray25"),
            "accent": "orange",
            "error": "#942626",
            "success": "green",
            "warning": "orange"
        }
    }
    
    @staticmethod
    def setup():
        customtkinter.set_appearance_mode("dark")
        theme_path = os.path.join(current_folder, "theme.json")
        if os.path.exists(theme_path):
            customtkinter.set_default_color_theme(theme_path)
    
    @staticmethod
    def get_color(key: str) -> str:
        return ThemeManager.THEMES["dark"].get(key, "gray")
```

## 3. **Simplify Hover/Click Binding with Context Manager**

```python
from contextlib import contextmanager

class HoverBinding:
    """Simplified hover binding with context manager"""
    
    @staticmethod
    @contextmanager
    def track_selection(text_widget):
        """Context manager for tracking text selection"""
        press_data = {}
        try:
            yield press_data
        finally:
            pass
    
    @staticmethod
    def bind_text_widget(textbox, on_hover=None, on_click=None):
        """Single-method binding for text widgets"""
        underlying = getattr(textbox, '_textbox', None)
        if not underlying:
            return
            
        if on_hover:
            underlying.bind("<Motion>", lambda e: on_hover(underlying.index(f"@{e.x},{e.y}")))
            underlying.bind("<Leave>", lambda e: on_hover(None))
        
        if on_click:
            # Simplified click detection with single event
            underlying.bind("<Button-1>", lambda e: on_click(underlying.index(f"@{e.x},{e.y}")))
```

## 4. **Use Properties for UI State Management**

```python
class ControlPanelSimplified:
    """ControlPanel with property-based state management"""
    
    def __init__(self, app_callback=None, ai_client=None):
        self._ai_opened = True
        self._monitoring_active = False
        self._advanced_visible = False
        self.ai = ai_client or OllamaClient()
        self.app_callback = app_callback
        self._setup_ui()
    
    @property
    def is_monitoring(self) -> bool:
        return self._monitoring_active
    
    @is_monitoring.setter
    def is_monitoring(self, value: bool):
        self._monitoring_active = value
        self._update_monitoring_ui()
    
    @property
    def ai_loaded(self) -> bool:
        return self._ai_opened
    
    @ai_loaded.setter
    def ai_loaded(self, value: bool):
        self._ai_opened = value
        self.ai_btn.configure(
            text="🤖 Unload" if value else "🤖 Load",
            fg_color="green" if value else "gray"
        )
    
    def _update_monitoring_ui(self):
        self.state_btn.configure(
            text="⏸️" if self.is_monitoring else "▶️",
            fg_color="orange" if self.is_monitoring else "green"
        )
```

## 5. **Extract Stream Processing to Generator Function**

```python
def process_streaming_response(ai, prompt, show_thinking=True):
    """Clean generator that yields (is_think, content) tuples"""
    for chunk in ai.generate_response(prompt, show_thinking):
        if chunk.startswith("__THINK__"):
            yield (True, chunk[9:])  # (is_think, content)
        else:
            yield (False, chunk)

# Usage becomes much cleaner:
def generate_content(self, prompt):
    handler = self.get_handler()
    for is_think, content in process_streaming_response(self.ai, prompt):
        if is_think:
            handler.append_think(content)
        else:
            handler.append_text(content)
```

## 6. **Use Template Method Pattern for AI-Powered Widgets**

```python
class AIWidget(customtkinter.CTkFrame):
    """Base class for widgets that use AI generation"""
    
    def __init__(self, master, ai_client, **kwargs):
        super().__init__(master, **kwargs)
        self.ai = ai_client
        self.is_generating = False
        self._setup_ui()
    
    def _setup_ui(self):
        """Template method - override in subclasses"""
        self.setup_content_area()
        self.setup_buttons()
        self.setup_lookup_panel()
    
    def generate(self, prompt: str):
        """Template method for generation with loading state"""
        if self.is_generating:
            return
        
        self.is_generating = True
        self.on_generation_start()
        
        def generate_task():
            try:
                for is_think, content in process_streaming_response(self.ai, prompt):
                    self.after(0, lambda: self.on_chunk(is_think, content))
                self.after(0, self.on_generation_complete)
            except Exception as e:
                self.after(0, lambda: self.on_generation_error(str(e)))
            finally:
                self.is_generating = False
        
        threading.Thread(target=generate_task, daemon=True).start()
    
    # Hook methods for subclasses
    def setup_content_area(self): pass
    def setup_buttons(self): pass
    def setup_lookup_panel(self): pass
    def on_generation_start(self): pass
    def on_chunk(self, is_think: bool, content: str): pass
    def on_generation_complete(self): pass
    def on_generation_error(self, error: str): pass

# Concrete implementation
class ChallengeWidget(AIWidget):
    def setup_content_area(self):
        self.text_area = customtkinter.CTkTextbox(self, wrap="word")
        self.text_area.pack(fill="both", expand=True)
    
    def on_generation_start(self):
        self.progress_bar.start()
        self.generate_btn.configure(state="disabled")
```

## 7. **Simplify Dictionary Lookup with DefaultDict**

```python
from collections import defaultdict

class CedictLookup:
    """Simplified CEDICT lookup with defaultdict"""
    
    def __init__(self):
        self.word_index = defaultdict(list)
        self.char_index = defaultdict(dict)
    
    def lookup(self, word: str) -> Tuple[Optional[dict], List]:
        """Clean lookup with better defaults"""
        word_entry = self.word_index.get(word)
        if word_entry:
            return word_entry, []
        
        char_matches = []
        for char in word:
            if entry := self.char_index.get(char):
                char_matches.append((char, entry))
        
        return None, char_matches
    
    def format_definition(self, word: str) -> str:
        """Single responsibility: format definition"""
        word_entry, char_matches = self.lookup(word)
        
        if word_entry:
            return self._format_word_entry(word_entry)
        elif char_matches:
            return self._format_char_matches(char_matches)
        return "No match found"
    
    def _format_word_entry(self, entry: dict) -> str:
        lines = [f"📖 {entry.get('simplified', '')}\n({entry.get('traditional', '')})\n"]
        lines.extend(f"• {d}" for d in entry.get('definitions', []))
        return "\n".join(lines)
    
    def _format_char_matches(self, matches: List) -> str:
        lines = ["Character breakdown:"]
        lines.extend(f"• {char}: {entry.get('simplified', '')}" for char, entry in matches)
        return "\n".join(lines)
```

## 8. **Use Enums for Mode Management**

```python
from enum import Enum, auto

class ResponseMode(Enum):
    LOOKUP_ONLY = "Lookup Only"
    SPARKLE_NOTES = "Sparkle Notes"
    IMMERSION_MODE = "Immersion Mode"
    WORD_BLOSSOM = "Word Blossom"
    SENTENCE_WHISPER = "Sentence Whisper"
    
    @classmethod
    def get_prompt_template(cls, mode: 'ResponseMode') -> str:
        templates = {
            cls.WORD_BLOSSOM: "Word Blossom Mode: {}",
            cls.SPARKLE_NOTES: "Sparkle Notes Mode: {}",
            cls.IMMERSION_MODE: "Immersion Mode: {}",
            cls.SENTENCE_WHISPER: "Sentence Whisper: {}",
        }
        return templates.get(mode, "{}")
    
    @classmethod
    def values(cls):
        return [mode.value for mode in cls]

# Usage
mode = ResponseMode.WORD_BLOSSOM
prompt = mode.get_prompt_template().format(word_list)
```

## 9. **Simplify Threading with Decorators**

```python
from functools import wraps
from typing import Callable

def async_ui_update(func: Callable):
    """Decorator to run function in thread and update UI via after"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if hasattr(self, 'is_generating') and self.is_generating:
            return
        
        def task():
            try:
                result = func(self, *args, **kwargs)
                if result and self.master:
                    self.master.after(0, lambda: self._on_async_complete(result))
            except Exception as e:
                if self.master:
                    self.master.after(0, lambda: self._on_async_error(str(e)))
        
        if hasattr(self, 'master'):
            self.master.after(0, lambda: setattr(self, 'is_generating', True))
            threading.Thread(target=task, daemon=True).start()
    
    return wrapper

# Usage
class HomeFrameSimplified(ctk.CTkFrame):
    @async_ui_update
    def generate_challenge(self):
        # Long-running operation
        return self.ai.generate_response(prompt)
    
    def _on_async_complete(self, result):
        self.is_generating = False
        self.display_result(result)
```

## 10. **Replace Nested Conditionals with Guard Clauses**

```python
# Before
def _on_text_motion(self, event):
    try:
        text_widget = event.widget
        index = text_widget.index(f"@{event.x},{event.y}")
        if not index:
            return
        # ... 20 more lines of nested conditions
    except Exception:
        pass

# After
def _on_text_motion(self, event):
    """Clean version with guard clauses"""
    try:
        text_widget = event.widget
        index = self._get_text_index(text_widget, event.x, event.y)
        if not index:
            return
        
        word = self._extract_word_at_position(text_widget, index)
        if not word or word == self.last_looked_up_word:
            return
        
        self._update_lookup_panel(word)
    except Exception:
        pass

def _get_text_index(self, widget, x, y):
    """Extract text position"""
    return widget.index(f"@{x},{y}")

def _extract_word_at_position(self, widget, index):
    """Extract Chinese word at position"""
    # Single responsibility method
    pass
```

## 11. **Use Composition Over Inheritance for UI Factories**

```python
class UIFactory:
    """Factory for creating consistent UI components"""
    
    @staticmethod
    def create_label(parent, text, font_size=12, weight="normal", **kwargs):
        return customtkinter.CTkLabel(
            parent, 
            text=text,
            font=("Mengshen-Handwritten", font_size, weight),
            **kwargs
        )
    
    @staticmethod
    def create_textbox(parent, height=100, wrap="word", font_size=12):
        return customtkinter.CTkTextbox(
            parent,
            wrap=wrap,
            font=("Mengshen-Handwritten", font_size),
            height=height
        )
    
    @staticmethod
    def create_button(parent, text, command, color="gray", width=None):
        btn = customtkinter.CTkButton(parent, text=text, command=command)
        if color != "gray":
            btn.configure(fg_color=UIFactory._get_color(color))
        if width:
            btn.configure(width=width)
        return btn
    
    @staticmethod
    def _get_color(name):
        colors = {"green": "#2e7d32", "red": "#942626", "orange": "#ed6c02"}
        return colors.get(name, "gray")
```

## 12. **Implement Message Bus for Component Communication**

```python
from typing import Any, Callable, Dict, List

class EventBus:
    """Simple event bus for decoupled component communication"""
    _instance = None
    _handlers: Dict[str, List[Callable]] = {}
    
    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def on(self, event: str, handler: Callable):
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)
    
    def emit(self, event: str, data: Any = None):
        for handler in self._handlers.get(event, []):
            handler(data)

# Usage
bus = EventBus()
bus.on("word_selected", lambda word: lookup_panel.update(word))
bus.on("mode_changed", lambda mode: update_prompt_template(mode))
```

## 13. **Simplify Clipboard Handling**

```python
class ClipboardManager:
    """Clean clipboard management"""
    
    MAX_LENGTH = 1000
    
    def __init__(self):
        self.current_text = ""
        self.is_valid = False
    
    def update(self, text: str) -> Tuple[str, bool]:
        """Update clipboard state, return (text, is_valid)"""
        if len(text) > self.MAX_LENGTH:
            return "", False
        
        self.current_text = text
        self.is_valid = self._has_chinese(text)
        return self.current_text, self.is_valid
    
    def _has_chinese(self, text: str) -> bool:
        return any('\u4e00' <= char <= '\u9fff' for char in text)
    
    def get_display_text(self) -> str:
        if not self.current_text:
            return "(No clipboard text)"
        icon = "🔤" if self.is_valid else "📋"
        return f"{icon} {self.current_text[:50]}..."
```

## 20. **Main Application Class with Clean Initialization**

```python
class VocabularyApp:
    """Clean main application with dependency injection"""
    
    def __init__(self, ai_client=None, database=None):
        self.ai = ai_client or OllamaClient()
        self.db = database
        self.state = AppState()
        self.theme = ThemeManager()
        self.cedict = CedictIndices.load()
        self.bus = EventBus()
        self.clipboard = ClipboardManager()
        
        self.theme.setup()
        self._setup_control_panel()
        self._setup_main_window()
    
    def _setup_control_panel(self):
        self.panel = ControlPanelSimplified(
            app_callback=self.open_main_window,
            ai_client=self.ai
        )
        self.panel.generate_callback = self.on_clipboard_click
    
    def _setup_main_window(self):
        # Lazy initialization to avoid circular dependencies
        pass
    
    def run(self):
        self.panel.show()
    
    def on_clipboard_click(self, text: str):
        """Handle clipboard click with proper validation"""
        if not text:
            return
        self.bus.emit("explanation_requested", text)
```

These improvements make the code:
- **More maintainable**: Single responsibility, clear structure
- **More testable**: Dependencies injected, pure functions
- **Less repetitive**: DRY principle, template methods
- **More readable**: Guard clauses, descriptive names, smaller functions
- **More extensible**: Open/closed principle via inheritance and composition