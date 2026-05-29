"""
Sentence Explorer - Break down Chinese text sentence by sentence.
Uses simplified node-based database API.
"""

import customtkinter as ctk
import threading
import re
from datetime import datetime
from typing import List, Dict, Optional
import uuid

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.db import VocabDatabase


class SentenceExplorerFrame(ctk.CTkFrame):
    """Frame for analyzing Chinese text sentence by sentence."""
    
    def __init__(self, master, ai_client, db: VocabDatabase, 
                 word_index=None, char_def_index=None, **kwargs):
        super().__init__(master, **kwargs)
        self.ai = ai_client
        self.db = db
        self.word_index = word_index or {}
        self.char_def_index = char_def_index or {}
        self.current_analysis_id = None
        self.current_content_id = None
        self.current_session_id = None
        self.windows = None
        self._setup_ui()
    
    def _get_windows(self):
        if self.windows is None:
            import lib.windows
            self.windows = lib.windows
        return self.windows
    
    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        ctk.CTkLabel(self, text="📖 Sentence Explorer", 
                     font=ctk.CTkFont(size=28, weight="bold")).grid(row=0, column=0, pady=15)
        
        input_frame = ctk.CTkFrame(self, fg_color=("gray95", "gray15"))
        input_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(input_frame, text="Paste Chinese text here:").grid(row=0, column=0, sticky="w", padx=10, pady=(10,0))
        
        self.text_input = ctk.CTkTextbox(input_frame, height=120, wrap="word", font=("Mengshen-Handwritten", 14))
        self.text_input.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        option_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        option_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        ctk.CTkLabel(option_frame, text="Title:").pack(side="left", padx=5)
        self.title_entry = ctk.CTkEntry(option_frame, width=200, placeholder_text="Optional")
        self.title_entry.pack(side="left", padx=5)
        
        # Session controls
        session_frame = ctk.CTkFrame(option_frame, fg_color="transparent")
        session_frame.pack(side="left", padx=10)
        
        ctk.CTkLabel(session_frame, text="🎯 Session:").pack(side="left")
        
        self.session_var = ctk.StringVar(value="Auto")
        session_options = ["Auto", "Manhua", "Song", "News", "Conversation", "General"]
        self.session_menu = ctk.CTkOptionMenu(session_frame, values=session_options, 
                                               variable=self.session_var, width=90)
        self.session_menu.pack(side="left", padx=5)
        
        self.session_status_label = ctk.CTkLabel(session_frame, text="", font=ctk.CTkFont(size=10))
        self.session_status_label.pack(side="left", padx=5)
        
        self.new_session_btn = ctk.CTkButton(session_frame, text="📂", width=30, height=25,
                                              command=self._create_new_session)
        self.new_session_btn.pack(side="left", padx=2)
        
        self.end_session_btn = ctk.CTkButton(session_frame, text="⏹️", width=30, height=25,
                                              fg_color="orange", command=self._end_current_session)
        self.end_session_btn.pack(side="left", padx=2)
        
        self.history_btn = ctk.CTkButton(session_frame, text="📜", width=30, height=25,
                                          command=self._show_session_history)
        self.history_btn.pack(side="left", padx=2)
        
        # Process buttons
        self.process_btn = ctk.CTkButton(option_frame, text="🔨 Analyze Text", command=self._analyze_text)
        self.process_btn.pack(side="right", padx=5)
        self.clear_btn = ctk.CTkButton(option_frame, text="🗑️ Clear", fg_color="gray", command=self._clear_all, width=80)
        self.clear_btn.pack(side="right", padx=5)
        self.saved_btn = ctk.CTkButton(option_frame, text="📚 Saved", fg_color="blue", command=self._show_saved_analyses, width=80)
        self.saved_btn.pack(side="right", padx=5)
        
        win = self._get_windows()
        self.think_component = win.ThinkBox(self)
        self.think_component.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        
        self.results_frame = ctk.CTkScrollableFrame(self, label_text="Deconstructed Sentences")
        self.results_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.results_frame.grid_columnconfigure(0, weight=1)
        
        self.status_label = ctk.CTkLabel(self, text="", text_color="gray")
        self.status_label.grid(row=4, column=0, pady=5)
        
        self._refresh_session_status()
    
    def _create_new_session(self):
        """Create a new learning session."""
        win = self._get_windows()
        
        popup = ctk.CTkToplevel(self)
        popup.geometry("300x250")
        popup.title("New Session")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text="Create New Learning Session", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        
        ctk.CTkLabel(popup, text="Session Type:").pack(anchor="w", padx=20)
        type_var = ctk.StringVar(value="General")
        type_menu = ctk.CTkOptionMenu(popup, values=["Manhua", "Song", "News", "Conversation", "General"], 
                                       variable=type_var)
        type_menu.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(popup, text="Source Name (optional):").pack(anchor="w", padx=20)
        source_entry = ctk.CTkEntry(popup, placeholder_text="e.g., Legend of the Sword Ch3")
        source_entry.pack(fill="x", padx=20, pady=5)
        
        def create():
            source = source_entry.get().strip() or None
            session_id = self.db.create_session(type_var.get(), source)
            self.current_session_id = session_id
            self.session_var.set(type_var.get())
            self._refresh_session_status()
            popup.destroy()
            win.popup_message("Session Created", f"Session created!\nAdd words while studying to track them.")
        
        ctk.CTkButton(popup, text="Create", command=create, fg_color="green").pack(pady=10)
    
    def _end_current_session(self):
        """End the current active session."""
        win = self._get_windows()
        active = self.db.get_active_session()
        if not active:
            win.popup_message("No Active Session", "No active session to end.", parent=self)
            return
        
        if win.popup_message("End Session", f"End session with {active.get('word_count', 0)} words?", is_yes_no=True, parent=self):
            # Sessions don't need explicit end in simplified API
            self.current_session_id = None
            self._refresh_session_status()
            win.popup_message("Session Ended", f"Session ended.", parent=self)
    
    def _refresh_session_status(self):
        """Update session status display."""
        active = self.db.get_active_session()
        if active:
            self.current_session_id = active['id']
            title = active.get('title', 'Session')
            self.session_status_label.configure(text=f"📚 {title[:30]}: {active.get('word_count', 0)} words", 
                                                 text_color="green")
        else:
            self.current_session_id = None
            self.session_status_label.configure(text="No active session", text_color="gray")
    
    def _get_or_create_session(self) -> int:
        """Get active session or create new one based on user selection."""
        session_type = self.session_var.get()
        
        if session_type == "Auto":
            active = self.db.get_active_session()
            if active:
                return active['id']
            else:
                return self.db.create_session("General", "Auto-created")
        else:
            active = self.db.get_active_session()
            if active and active.get('title', '').startswith(session_type):
                return active['id']
            else:
                source = self.title_entry.get().strip() or session_type
                return self.db.create_session(session_type, source)
    
    def _split_sentences(self, text: str) -> List[str]:
        splitters = r'[。！？；\n]+'
        raw_sentences = re.split(splitters, text)
        return [s.strip() for s in raw_sentences if s.strip()]
    
    def _parse_ai_response(self, sentence: str, response: str, index: int) -> Dict:
        """Parse AI's sentence analysis response into structured data."""
        analysis = {
            'index': index,
            'original': sentence,
            'keywords': [],
            'translation': '',
            'simplified_paraphrase': '',
            'why_matters': '',
            'remember_hook': '',
            'difficulty': 3
        }
        
        # Parse Key words
        keywords_section = re.search(
            r'\*\*Key words? to know:\*\*(.*?)(?=\*\*What|\*\*Simplified|\*\*Why|\*\*Remember|\Z)', 
            response, re.DOTALL | re.IGNORECASE
        )
        
        if keywords_section:
            kw_text = keywords_section.group(1)
            pattern = r'\*\*([^*]+)\s*\(([^)]+)\)\*\*\s*[-–—:]\s*(.+?)(?=\n\s*[-•*]|\n\s*\*\*|\Z)'
            for match in re.finditer(pattern, kw_text, re.DOTALL):
                word = match.group(1).strip()
                pinyin = match.group(2).strip()
                insight = match.group(3).strip()[:150]
                analysis['keywords'].append({'word': word, 'pinyin': pinyin, 'insight': insight, 'importance': 0.7})
        
        # Parse Translation
        trans_match = re.search(
            r'\*\*What it says?:\*\*(.*?)(?=\*\*Simplified|\*\*Why|\*\*Remember|\Z)', 
            response, re.DOTALL | re.IGNORECASE
        )
        if trans_match:
            analysis['translation'] = trans_match.group(1).strip()[:300]
        
        # Parse Simplified paraphrase
        simple_match = re.search(
            r'\*\*Simplified(?: Chinese)?(?: paraphrase)?:\*\*(.*?)(?=\*\*Why|\*\*Remember|\Z)', 
            response, re.DOTALL | re.IGNORECASE
        )
        if simple_match:
            analysis['simplified_paraphrase'] = simple_match.group(1).strip()[:200]
        
        # Parse Why matters
        why_match = re.search(
            r'\*\*Why it matters?:\*\*(.*?)(?=\*\*Remember|\*\*Interactive|\Z)', 
            response, re.DOTALL | re.IGNORECASE
        )
        if why_match:
            analysis['why_matters'] = why_match.group(1).strip()[:400]
        
        # Parse Remember hook
        hook_match = re.search(
            r'\*\*Remember it:\*\*(.*?)(?=\*\*Interactive|\Z)', 
            response, re.DOTALL | re.IGNORECASE
        )
        if hook_match:
            analysis['remember_hook'] = hook_match.group(1).strip()[:200]
        
        return analysis
    
    def _analyze_text(self):
        text = self.text_input.get("1.0", "end-1c").strip()
        if not text:
            self._get_windows().popup_message("Empty Text", "Please paste some Chinese text to analyze.")
            return
        
        # Get or create session
        self.current_session_id = self._get_or_create_session()
        self._refresh_session_status()
        
        self.process_btn.configure(state="disabled", text="⏳ Analyzing...")
        self.think_component.clear_think()
        self.status_label.configure(text="Analyzing sentences...", text_color="orange")
        self._clear_results()
        
        self.current_text = text
        self.current_title = self.title_entry.get().strip() or f"Text_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        def process():
            sentences = self._split_sentences(text)
            all_analyses = []
            difficulty_sum = 0
            
            self._update_status_after(0, f"Found {len(sentences)} sentences. Analyzing...", "orange")
            
            # Create analysis node
            analysis_node_id = self.db.create_content_node(
                node_type='analysis',
                content=text[:500],
                title=self.current_title,
                session_id=self.current_session_id,
                metadata={'total_sentences': len(sentences)}
            )
            self.current_analysis_id = analysis_node_id
            
            for i, sentence in enumerate(sentences, 1):
                self._update_status_after(0, f"Analyzing sentence {i}/{len(sentences)}...", "orange")
                
                prompt = f"""💫 {sentence}"""

# Please analyze this sentence following EXACTLY this format:

# **Key words to know:**
# - **word (pinyin)** - creative insight (5-10 words)
# - **word2 (pinyin2)** - creative insight

# **What it says:** [clear English translation]

# **Simplified paraphrase:** [say the same meaning with simpler Chinese]

# **Why it matters:** [one interesting observation, 1-2 sentences]

# **Remember it:** [memory hook using the main word]

# Keep it warm and concise like Xiao Xi."""
                
                full_response = ""
                win = self._get_windows()
                
                for chunk in self.ai.generate_response(prompt, display_thinking=True):
                    if chunk.startswith("__THINK__"):
                        thinking_text = chunk[len("__THINK__"):]
                        self._after_append_think(thinking_text)
                    else:
                        full_response += chunk
                
                analysis = self._parse_ai_response(sentence, full_response, i)
                all_analyses.append(analysis)
                difficulty_sum += analysis.get('difficulty', 3)
                
                # Save sentence as node
                sentence_content = f"{sentence}\n\nTranslation: {analysis.get('translation', '')}\nWhy it matters: {analysis.get('why_matters', '')}\nRemember: {analysis.get('remember_hook', '')}"
                sentence_node_id = self.db.create_content_node(
                    node_type='sentence',
                    content=sentence_content,
                    title=f"Sentence {i}",
                    parent_id=analysis_node_id,
                    session_id=self.current_session_id,
                    metadata={
                        'translation': analysis.get('translation', ''),
                        'simplified_paraphrase': analysis.get('simplified_paraphrase', ''),
                        'why_matters': analysis.get('why_matters', ''),
                        'remember_hook': analysis.get('remember_hook', ''),
                        'difficulty': analysis.get('difficulty', 3)
                    }
                )
                
                # Save keywords as word nodes
                for kw in analysis.get('keywords', []):
                    word_text = kw.get('word', '')
                    if word_text:
                        existing = self.db.get_word(word_text)
                        if not existing:
                            self.db.create_word(
                                word_text,
                                kw.get('insight', ''),
                                parent_id=sentence_node_id
                            )
                        else:
                            self.db.update_node(existing['id'], parent_id=sentence_node_id)
                        
                        # Add word to session
                        if self.current_session_id:
                            word_node = self.db.get_word(word_text)
                            if word_node:
                                self.db.update_node(word_node['id'], session_id=self.current_session_id)
                
                self._after_add_card(analysis, i)
            
            avg_difficulty = difficulty_sum / len(sentences) if sentences else 3
            if avg_difficulty < 1.5:
                level = "HSK1-2"
            elif avg_difficulty < 2.5:
                level = "HSK3"
            elif avg_difficulty < 3.5:
                level = "HSK4"
            else:
                level = "HSK5+"
            
            # Update analysis node with level
            self.db.update_node(analysis_node_id, metadata={'estimated_level': level, 'total_sentences': len(sentences)})
            
            self._refresh_session_status()
            self._update_status_after(0, f"✅ Complete! {len(sentences)} sentences, {level} level", "green")
            self._after_enable_button()
        
        threading.Thread(target=process, daemon=True).start()
    
    def _show_session_history(self):
        """Show session history popup."""
        win = self._get_windows()
        sessions = self.db.get_all_sessions()
        
        if not sessions:
            win.popup_message("Sessions", "No sessions recorded yet.", parent=self)
            return
        
        popup = ctk.CTkToplevel(self)
        popup.geometry("700x500")
        popup.title("Session History")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text="📚 Your Learning Sessions", 
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        list_frame = ctk.CTkScrollableFrame(popup)
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        for s in sessions:
            item_frame = ctk.CTkFrame(list_frame)
            item_frame.pack(fill="x", pady=3)
            
            date_str = datetime.fromtimestamp(s['created_at']).strftime('%m-%d %H:%M')
            title = s.get('title', 'Session')
            status = "🟢"
            
            ctk.CTkLabel(item_frame, text=f"{status} 📚", 
                         font=ctk.CTkFont(weight="bold"), width=40).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=title[:40], width=200).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=f"{s.get('word_count', 0)} words", width=80).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=date_str, width=100, text_color="gray").pack(side="left", padx=5)
            
            def view(sid=s['id']):
                self._view_session_details(sid)
                popup.destroy()
            ctk.CTkButton(item_frame, text="View", width=60, command=view).pack(side="right", padx=5)
    
    def _view_session_details(self, session_id: int):
        """Show detailed view of a session with all words."""
        win = self._get_windows()
        words = self.db.get_session_words(session_id)
        
        popup = ctk.CTkToplevel(self)
        popup.geometry("600x500")
        popup.title(f"Session Details")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text=f"📚 Session Details", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        if words:
            list_frame = ctk.CTkScrollableFrame(popup)
            list_frame.pack(fill="both", expand=True, padx=20, pady=10)
            
            for w in words:
                word_frame = ctk.CTkFrame(list_frame)
                word_frame.pack(fill="x", pady=2)
                ctk.CTkLabel(word_frame, text=w['content'], font=ctk.CTkFont(weight="bold"), width=120).pack(side="left", padx=5)
                ctk.CTkLabel(word_frame, text=w.get('translation', '')[:50], width=300).pack(side="left", padx=5)
        else:
            ctk.CTkLabel(popup, text="No words in this session yet.").pack(pady=20)
    
    def _create_sentence_card(self, sentence_data: Dict, index: int):
        """Create a card showing all AI fields."""
        win = self._get_windows()
        
        card = ctk.CTkFrame(self.results_frame, fg_color=("gray90", "gray20"), corner_radius=10)
        card.pack(fill="x", pady=5, padx=5)
        card.sentence_data = sentence_data
        card.expanded = False
        
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        
        preview = sentence_data['original'][:60] + "..." if len(sentence_data['original']) > 60 else sentence_data['original']
        ctk.CTkLabel(header, text=f"📖 {index}. {preview}", 
                     font=ctk.CTkFont(weight="bold"), anchor="w").pack(side="left", fill="x", expand=True)
        
        expand_btn = ctk.CTkButton(header, text="▼", width=30, height=30, command=lambda c=card: self._toggle_card(c))
        expand_btn.pack(side="right", padx=2)
        card.expand_btn = expand_btn
        
        # Expanded content frame
        card.expanded_frame = ctk.CTkFrame(card, fg_color="transparent")
        
        # 1. Key Words
        keywords = sentence_data.get('keywords', [])
        if keywords:
            kw_frame = ctk.CTkFrame(card.expanded_frame, fg_color="transparent")
            kw_frame.pack(fill="x", pady=5)
            ctk.CTkLabel(kw_frame, text="🔑 Key words to know:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
            for kw in keywords:
                kw_text = f"  • **{kw.get('word', '')}** ({kw.get('pinyin', '')}) — {kw.get('insight', '')}"
                ctk.CTkLabel(kw_frame, text=kw_text, wraplength=500, justify="left").pack(anchor="w", padx=20)
        
        # 2. Translation
        if sentence_data.get('translation'):
            trans_frame = ctk.CTkFrame(card.expanded_frame, fg_color="transparent")
            trans_frame.pack(fill="x", pady=5)
            ctk.CTkLabel(trans_frame, text="🌐 What it says:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
            ctk.CTkLabel(trans_frame, text=sentence_data['translation'], wraplength=500, justify="left").pack(anchor="w", padx=20)
        
        # 3. Simplified Paraphrase
        if sentence_data.get('simplified_paraphrase'):
            simple_frame = ctk.CTkFrame(card.expanded_frame, fg_color="transparent")
            simple_frame.pack(fill="x", pady=5)
            ctk.CTkLabel(simple_frame, text="📝 Simplified:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
            ctk.CTkLabel(simple_frame, text=sentence_data['simplified_paraphrase'], wraplength=500, justify="left", 
                         text_color="green").pack(anchor="w", padx=20)
        
        # 4. Why it matters
        if sentence_data.get('why_matters'):
            why_frame = ctk.CTkFrame(card.expanded_frame, fg_color="transparent")
            why_frame.pack(fill="x", pady=5)
            ctk.CTkLabel(why_frame, text="💭 Why it matters:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
            ctk.CTkLabel(why_frame, text=sentence_data['why_matters'], wraplength=500, justify="left").pack(anchor="w", padx=20)
        
        # 5. Remember it (hook)
        if sentence_data.get('remember_hook'):
            hook_frame = ctk.CTkFrame(card.expanded_frame, fg_color="transparent")
            hook_frame.pack(fill="x", pady=5)
            ctk.CTkLabel(hook_frame, text="🔗 Remember it:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
            ctk.CTkLabel(hook_frame, text=sentence_data['remember_hook'], wraplength=500, justify="left",
                         text_color="orange").pack(anchor="w", padx=20)
    
    def _toggle_card(self, card):
        card.expanded = not card.expanded
        if card.expanded:
            card.expanded_frame.pack(fill="x", padx=15, pady=10)
            card.expand_btn.configure(text="▲")
        else:
            card.expanded_frame.pack_forget()
            card.expand_btn.configure(text="▼")
    
    def _show_saved_analyses(self):
        win = self._get_windows()
        analyses = self.db.get_recent_nodes(limit=20, node_type='analysis')
        if not analyses:
            win.popup_message("No Saved Analyses", "No analyses found. Analyze some text first!")
            return
        
        popup = ctk.CTkToplevel(self)
        popup.geometry("600x400")
        popup.title("Saved Analyses")
        popup.attributes("-topmost", True)
        ctk.CTkLabel(popup, text="📚 Your Saved Sentence Analyses", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        list_frame = ctk.CTkScrollableFrame(popup)
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        for a in analyses:
            item_frame = ctk.CTkFrame(list_frame)
            item_frame.pack(fill="x", pady=3)
            date_str = datetime.fromtimestamp(a['created_at']).strftime('%Y-%m-%d')
            title = a.get('title', f"Analysis {a['id']}")[:40]
            
            ctk.CTkLabel(item_frame, text=f"📖 {title}", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
            
            def load(aid=a['id']):
                self._load_analysis(aid)
                popup.destroy()
            ctk.CTkButton(item_frame, text="Load", width=60, command=load).pack(side="right", padx=5)
            
            def delete(aid=a['id']):
                if win.popup_message("Delete", f"Delete '{title}'?", is_yes_no=True):
                    self.db.delete_node(aid)
                    popup.destroy()
                    self._show_saved_analyses()
            ctk.CTkButton(item_frame, text="🗑️", width=40, fg_color="red", command=delete).pack(side="right", padx=5)
    
    def _load_analysis(self, analysis_id: int):
        self._clear_results()
        self.current_analysis_id = analysis_id
        analysis_node = self.db.get_node(analysis_id)
        
        if analysis_node:
            self.title_entry.delete(0, "end")
            self.title_entry.insert(0, analysis_node.get('title', ''))
            self.text_input.delete("1.0", "end")
            self.text_input.insert("1.0", analysis_node.get('content', ''))
        
        sentences = self.db.get_children(analysis_id, node_type='sentence')
        for i, sent_node in enumerate(sentences, 1):
            # Build sentence data from node
            import ast
            metadata = {}
            if sent_node.get('metadata'):
                try:
                    metadata = ast.literal_eval(sent_node['metadata']) if isinstance(sent_node['metadata'], str) else sent_node['metadata']
                except:
                    metadata = {}
            
            sentence_data = {
                'id': sent_node['id'],
                'original': sent_node['content'].split('\n\n')[0] if sent_node['content'] else '',
                'translation': metadata.get('translation', ''),
                'simplified_paraphrase': metadata.get('simplified_paraphrase', ''),
                'why_matters': metadata.get('why_matters', ''),
                'remember_hook': metadata.get('remember_hook', ''),
                'difficulty': metadata.get('difficulty', 3),
                'keywords': [],
                'notes': []
            }
            
            # Get keywords (word nodes with this sentence as parent)
            keywords = self.db.get_children(sent_node['id'], node_type='word')
            for kw in keywords:
                sentence_data['keywords'].append({
                    'word': kw.get('content', ''),
                    'pinyin': '',
                    'insight': kw.get('translation', ''),
                    'importance': 0.7
                })
            
            self._create_sentence_card(sentence_data, i)
        
        self.status_label.configure(text=f"✅ Loaded {len(sentences)} sentences", text_color="green")
    
    def _clear_results(self):
        for widget in self.results_frame.winfo_children():
            widget.destroy()
    
    def _clear_all(self):
        self.text_input.delete("1.0", "end")
        self.title_entry.delete(0, "end")
        self._clear_results()
        self.think_component.clear_think()
        self.current_analysis_id = None
        self.current_content_id = None
        self.status_label.configure(text="", text_color="gray")
    
    def _update_status_after(self, delay, text, color):
        self.after(delay, lambda: self.status_label.configure(text=text, text_color=color))
    
    def _after_append_think(self, text):
        self.after(0, lambda: self.think_component.append_think(text))
    
    def _after_add_card(self, analysis, index):
        def add():
            card_data = {
                'id': None,
                'original': analysis.get('original', ''),
                'translation': analysis.get('translation', ''),
                'simplified_paraphrase': analysis.get('simplified_paraphrase', ''),
                'why_matters': analysis.get('why_matters', ''),
                'remember_hook': analysis.get('remember_hook', ''),
                'difficulty': analysis.get('difficulty', 3),
                'keywords': analysis.get('keywords', []),
                'notes': []
            }
            self._create_sentence_card(card_data, index)
        self.after(0, add)
    
    def _after_enable_button(self):
        self.after(0, lambda: self.process_btn.configure(state="normal", text="🔨 Analyze Text"))