"""
Sentence Explorer - Break down Chinese text sentence by sentence.
Refactored to use SessionManager and ExpandableCard.
"""

import customtkinter as ctk
import threading
import re
from datetime import datetime
from typing import List, Dict
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.db import VocabDatabase
from lib.ui_components import SessionManager, ExpandableCard, PopupManager


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
        
        # Use SessionManager component
        self.session_manager = SessionManager(option_frame, self.db, 
                                               on_session_changed=self._on_session_changed)
        self.session_manager.pack(side="left", padx=10)
        
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
    
    def _on_session_changed(self, session_id):
        """Handle session change."""
        pass
    
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
            PopupManager.show_info(self, "Empty Text", "Please paste some Chinese text to analyze.")
            return
        
        # Get or create session
        session_id = self.session_manager.get_or_create_session(self.title_entry.get().strip())
        
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
                session_id=session_id,
                metadata={'total_sentences': len(sentences)}
            )
            self.current_analysis_id = analysis_node_id
            
            for i, sentence in enumerate(sentences, 1):
                self._update_status_after(0, f"Analyzing sentence {i}/{len(sentences)}...", "orange")
                
                prompt = f"""💫 {sentence}"""
                
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
                    session_id=session_id,
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
                        word_node = self.db.get_word(word_text)
                        if word_node:
                            self.db.update_node(word_node['id'], session_id=session_id)
                
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
            
            self.session_manager._refresh_status()
            self._update_status_after(0, f"✅ Complete! {len(sentences)} sentences, {level} level", "green")
            self._after_enable_button()
        
        threading.Thread(target=process, daemon=True).start()
    
    def _create_sentence_card(self, sentence_data: Dict, index: int):
        """Create an expandable card for a sentence."""
        preview = sentence_data['original'][:60] + "..." if len(sentence_data['original']) > 60 else sentence_data['original']
        
        card = ExpandableCard(
            self.results_frame,
            title=f"📖 {index}. {preview}",
            subtitle="",
            icon="",
            preview=""
        )
        
        # Keywords section
        keywords = sentence_data.get('keywords', [])
        if keywords:
            kw_text = "\n".join([f"  • **{kw.get('word', '')}** ({kw.get('pinyin', '')}) — {kw.get('insight', '')}" 
                                 for kw in keywords])
            card.add_expanded_section("🔑 Key words to know:", kw_text)
        
        # Translation
        if sentence_data.get('translation'):
            card.add_expanded_section("🌐 What it says:", sentence_data['translation'])
        
        # Simplified paraphrase
        if sentence_data.get('simplified_paraphrase'):
            card.add_expanded_section("📝 Simplified:", sentence_data['simplified_paraphrase'], text_color="green")
        
        # Why it matters
        if sentence_data.get('why_matters'):
            card.add_expanded_section("💭 Why it matters:", sentence_data['why_matters'])
        
        # Remember hook
        if sentence_data.get('remember_hook'):
            card.add_expanded_section("🔗 Remember it:", sentence_data['remember_hook'], text_color="orange")
        
        # Auto-expand first card
        if index == 1 and not hasattr(self, '_first_card_expanded'):
            self._first_card_expanded = True
            card.expanded = False
            card._toggle_expand()
    
    def _show_saved_analyses(self):
        analyses = self.db.get_recent_nodes(limit=20, node_type='analysis')
        if not analyses:
            PopupManager.show_info(self, "No Saved Analyses", "No analyses found. Analyze some text first!")
            return
        
        def display_func(item):
            return f"📖 {item.get('title', f'Analysis {item['id']}')[:40]}"
        
        def on_select(analysis):
            self._load_analysis(analysis['id'])
        
        PopupManager.create_selection_list(
            self, "Saved Analyses", analyses, display_func, on_select,
            width=600, height=400
        )
    
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
        self._first_card_expanded = False
    
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