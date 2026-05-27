"""
Single streaming popup class that handles AI responses and dictionary lookups.
Replaces the old Long_message_popup completely.
"""

import customtkinter as ctk
import os
import random
from PIL import Image
from typing import Optional, Callable

from lib.async_utils import stream_to_widgets, set_widget_text, clear_widget
from lib.chain import ChainManager
from lib.ui_components import LookupPanel, ThinkBox, popup_message
from lib.debug_utils import DebugLogger

# Import CEDICT functions for lookup-only mode
try:
    from lib.ccedict import lookup_cedict
except ImportError:
    lookup_cedict = None

current_folder = os.path.dirname(os.path.abspath(__file__))
repo_folder = os.path.dirname(current_folder)


class StreamingPopup:
    """
    Single popup class that handles:
    - AI streaming responses (Sparkle Notes, Immersion Mode, etc.)
    - Dictionary lookups (Lookup Only mode)
    - Chained word clicks (maintaining content hierarchy)
    """
    
    def __init__(
        self,
        word: str,
        master,
        chain_mgr: ChainManager,
        ai_client,
        mode: Optional[str] = None,
        display_image: bool = True,
        word_index: Optional[dict] = None,
        char_def_index: Optional[dict] = None,
        data_service=None,
        on_save_callback: Optional[Callable] = None,
        show_thinking: bool = True
    ):
        self.word = word
        self.master = master
        self.chain_mgr = chain_mgr
        self.ai = ai_client
        self.mode = mode or "Sparkle Notes"
        self.display_image = display_image
        self.word_index = word_index or {}
        self.char_def_index = char_def_index or {}
        self.data_service = data_service
        self.on_save_callback = on_save_callback
        self.show_thinking = show_thinking
        
        self.debug = DebugLogger("StreamingPopup")
        self.response_full_text = ""
        
        # Check if this is lookup-only mode
        self.is_lookup_only = (self.mode == "Lookup Only")
        
        # Create query node (this updates chain_mgr.active_node_id)
        self.query_node_id = chain_mgr.create_query_node(word, self.mode)
        
        # Create UI
        self._setup_ui()
        
        # Start content generation (AI or dictionary)
        self._start_content_generation()
    
    def _setup_ui(self):
        """Setup the popup UI."""
        # Create popup window
        self.popup = ctk.CTkToplevel(self.master)
        
        # Set title based on mode
        if self.is_lookup_only:
            self.popup.title(f"Dictionary: {self.word}")
        else:
            self.popup.title(f"Explanation: {self.word}")
        
        self.popup.geometry("900x550")
        self.popup.attributes("-topmost", True)
        
        # Bind close event
        self.popup.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.debug.debug(f"Created popup for '{self.word}' in mode '{self.mode}'")
        
        # Header
        header_frame = ctk.CTkFrame(self.popup, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(10, 5))
        
        # Icon based on mode
        icon = "📖" if self.is_lookup_only else "✨"
        ctk.CTkLabel(
            header_frame,
            text=f"{icon} {self.word}",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(side="left")
        
        # Mode badge
        mode_badge = ctk.CTkLabel(
            header_frame,
            text=self.mode,
            font=ctk.CTkFont(size=11),
            text_color="gray",
            corner_radius=10
        )
        mode_badge.pack(side="left", padx=(10, 0))
        
        # Optional image (only for AI modes)
        if self.display_image and not self.is_lookup_only:
            self._add_decorative_image(header_frame)
        
        # Main content area
        content_frame = ctk.CTkFrame(self.popup, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Text panel (left side)
        text_panel = ctk.CTkFrame(content_frame, fg_color="transparent")
        text_panel.pack(side="left", fill="both", expand=True)
        
        # Think box (only for AI modes with thinking enabled)
        self.think_box = None
        if not self.is_lookup_only and self.show_thinking:
            self.think_box = ThinkBox(text_panel)
            self.think_box.pack(side="top", fill="x", pady=(0, 5))
        
        # Main text area
        self.text_box = ctk.CTkTextbox(text_panel, wrap="word", font=("Mengshen-Handwritten", 18))
        self.text_box.configure(state="disabled")
        self.text_box.pack(side="left", fill="both", expand=True)
        
        # Lookup panel (right side) - enables chained word clicks
        self.lookup_panel = LookupPanel(
            content_frame,
            word_index=self.word_index,
            char_def_index=self.char_def_index,
            generate_explanation_callback=self._on_word_click,
            data_service=self.data_service,
            context=self.chain_mgr
        )
        self.lookup_panel.pack(side="right", fill="y", padx=5, pady=5, ipadx=10, ipady=10)
        self.lookup_panel.configure(width=180)
        
        # Bind text areas to lookup panel
        self._bind_lookup_panel()
        
        # Chain info footer
        self._add_chain_info()
    
    def _bind_lookup_panel(self):
        """Bind text areas to lookup panel for hover/click detection."""
        try:
            self.lookup_panel.bind_text_box(self.text_box)
            if self.think_box:
                self.lookup_panel.bind_text_box(self.think_box.text_box)
        except Exception as e:
            self.debug.debug(f"Could not bind lookup panel: {e}")
    
    def _add_decorative_image(self, parent):
        """Add a decorative image to the popup."""
        try:
            img_num = random.randint(1, 5)
            img_path = os.path.join(repo_folder, ".misc", "long_response", f"{img_num}.png")
            if os.path.exists(img_path):
                img = Image.open(img_path)
                max_size = (80, 80)
                scale = min(max_size[0]/img.size[0], max_size[1]/img.size[1])
                photo = ctk.CTkImage(img, size=(int(img.size[0]*scale), int(img.size[1]*scale)))
                img_label = ctk.CTkLabel(parent, image=photo, text="")
                img_label.image = photo
                img_label.pack(side="right", padx=10)
        except Exception as e:
            self.debug.debug(f"Could not load image: {e}")
    
    def _add_chain_info(self):
        """Add chain information footer."""
        chain_frame = ctk.CTkFrame(self.popup, fg_color="transparent")
        chain_frame.pack(side="bottom", fill="x", padx=10, pady=5)
        
        # Show current node info
        node_text = f"🔗 Node: {self.query_node_id}"
        if self.chain_mgr.active_node_id != self.query_node_id:
            node_text += f" → {self.chain_mgr.active_node_id}"
        
        node_label = ctk.CTkLabel(
            chain_frame,
            text=node_text,
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        node_label.pack(side="left", padx=5)
        
        # View chain button
        view_btn = ctk.CTkButton(
            chain_frame,
            text="View Chain",
            width=80,
            height=25,
            command=self._view_chain
        )
        view_btn.pack(side="right", padx=5)
    
    def _start_content_generation(self):
        """Start generating content (AI or dictionary lookup)."""
        if self.is_lookup_only:
            self._do_dictionary_lookup()
        else:
            self._start_ai_streaming()
    
    def _do_dictionary_lookup(self):
        """Perform CEDICT dictionary lookup (no AI)."""
        set_widget_text(self.text_box, "📖 Looking up word in dictionary...")
        
        result_text = self._format_dictionary_result()
        set_widget_text(self.text_box, result_text)
        
        # Create response node
        self.response_full_text = result_text
        self.response_node_id = self.chain_mgr.create_response_node(
            content=result_text,
            title=f"Dictionary: {self.word}",
            metadata={"mode": self.mode, "source": "cedict"}
        )
        
        self._add_save_button()
    
    def _format_dictionary_result(self) -> str:
        """Format dictionary lookup result as readable text."""
        if not lookup_cedict:
            return "❌ CEDICT dictionary not available.\n\nPlease check that cedict_ts.u8 file exists."
        
        try:
            word_entry, char_matches = lookup_cedict(self.word, self.word_index, self.char_def_index)
            
            if word_entry:
                lines = []
                lines.append(f"📖 {word_entry.get('simplified', self.word)}")
                if word_entry.get('traditional') and word_entry.get('traditional') != self.word:
                    lines.append(f"繁体: {word_entry.get('traditional')}")
                lines.append("")
                lines.append("定义:")
                for i, definition in enumerate(word_entry.get('definitions', []), 1):
                    lines.append(f"  {i}. {definition}")
                return "\n".join(lines)
            
            elif char_matches:
                lines = [f"🔤 字符分解: '{self.word}'"]
                lines.append("")
                for char, entry in char_matches:
                    lines.append(f"• {char}: {entry.get('simplified', char)}")
                    if entry.get('definitions'):
                        lines.append(f"    {'; '.join(entry.get('definitions', [])[:2])}")
                    lines.append("")
                return "\n".join(lines)
            
            else:
                return f"❌ 未找到匹配: '{self.word}'\n\n未在字典中找到此词。"
        
        except Exception as e:
            return f"❌ 字典查询错误: {str(e)}"
    
    def _start_ai_streaming(self):
        """Start streaming AI response to the text box."""
        set_widget_text(self.text_box, "🤔 Generating explanation...")
        if self.think_box:
            clear_widget(self.think_box.text_box)
        
        if not self.ai:
            set_widget_text(self.text_box, "❌ AI client not available. Please check your Ollama setup.")
            return
        
        prompt = self._build_prompt()
        
        def generator():
            return self.ai.generate_response(prompt, display_thinking=self.show_thinking)
        
        def on_complete(full_text):
            self.response_full_text = full_text
            self._on_stream_complete(full_text)
        
        stream_to_widgets(
            root=self.popup,
            generator=generator(),
            text_widget=self.text_box,
            think_widget=self.think_box.text_box if self.think_box else None,
            on_complete=on_complete,
            show_thinking=self.show_thinking
        )
    
    def _build_prompt(self) -> str:
        """Build the AI prompt with chain context."""
        parent_context = ""
        if self.chain_mgr.active_node_id != self.query_node_id:
            parent_node = self.chain_mgr.get_node(self.chain_mgr.active_node_id)
            if parent_node and parent_node.get('node_type') == 'response':
                content = parent_node.get('content', '')[:200]
                if content:
                    parent_context = f"\n[Previous context from {parent_node.get('title', 'previous')}]: {content}\n"
        
        return f"{parent_context}Explain the Chinese word '{self.word}' in {self.mode} mode. Provide translation, breakdown, and example sentence."
    
    def _on_stream_complete(self, full_text: str):
        """Called when AI streaming finishes."""
        self.debug.debug(f"Streaming complete for '{self.word}', creating response node")
        
        self.response_node_id = self.chain_mgr.create_response_node(
            content=full_text,
            title=f"Response to: {self.word}",
            metadata={"mode": self.mode, "source": "ai_response"}
        )
        
        self._add_save_button()
        self.chain_mgr.save_word(self.word, full_text)
    
    def _add_save_button(self):
        """Add save button to the popup."""
        def save_word():
            word_id = self.chain_mgr.save_word(self.word, self.response_full_text)
            if word_id:
                popup_message("Saved", f"✓ '{self.word}' added to vocabulary!", parent=self.popup)
                if self.on_save_callback:
                    self.on_save_callback(self.word, word_id)
        
        button_frame = ctk.CTkFrame(self.popup, fg_color="transparent")
        button_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        
        save_btn = ctk.CTkButton(
            button_frame,
            text="💾 Save Word to Vocabulary",
            fg_color="green",
            command=save_word
        )
        save_btn.pack(side="left", padx=5)
        
        close_btn = ctk.CTkButton(
            button_frame,
            text="Close",
            fg_color="gray",
            command=self._on_close
        )
        close_btn.pack(side="right", padx=5)
    
    def _on_word_click(self, word: str, mode: Optional[str] = None, context=None):
        """Called when user clicks a word - creates chained popup."""
        self.debug.debug(f"🔗 Chaining: '{word}' clicked in popup for '{self.word}'")
        self.debug.debug(f"   Current active_node_id: {self.chain_mgr.active_node_id}")
        
        effective_chain_mgr = context if context else self.chain_mgr
        effective_mode = mode or self.mode
        
        new_popup = StreamingPopup(
            word=word,
            master=self.popup,
            chain_mgr=effective_chain_mgr,
            ai_client=self.ai,
            mode=effective_mode,
            display_image=self.display_image and (effective_mode != "Lookup Only"),
            word_index=self.word_index,
            char_def_index=self.char_def_index,
            data_service=self.data_service,
            on_save_callback=self.on_save_callback,
            show_thinking=self.show_thinking
        )
        new_popup.focus()
    
    def _view_chain(self):
        """Open chain viewer for the current node."""
        if not self.chain_mgr.db:
            return
        
        from lib.chain_viewer import ChainViewer
        viewer = ChainViewer(
            self.popup,
            self.chain_mgr.db,
            self.chain_mgr.active_node_id or self.query_node_id,
            f"Chain for: {self.word}"
        )
        viewer.focus()
    
    def _on_close(self):
        """Close the popup."""
        self.debug.debug(f"Closing popup for '{self.word}'")
        self.popup.destroy()
    
    def focus(self):
        """Bring popup to front."""
        self.popup.lift()
        self.popup.focus_force()