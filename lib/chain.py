"""
Chain management for content hierarchy tracking.
Single source of truth for node creation and chain linking.
"""

import re
from typing import Optional, Dict, Any


class ChainManager:
    """
    Manages the chain of content nodes.
    Active node always points to the last created node.
    Enables automatic parent linking for chained responses.
    """
    
    def __init__(self, db, session_id: Optional[str] = None):
        """
        Args:
            db: VocabDatabase instance
            session_id: Current learning session ID (optional)
        """
        self.db = db
        self.active_node_id: Optional[int] = None
        self.session_id = session_id
        self._debug = True  # Set to False to disable debug output
    
    def _log(self, msg: str):
        """Debug logging."""
        if self._debug:
            print(f"🔗 [ChainManager] {msg}")
    
    def create_query_node(self, word: str, mode: Optional[str] = None) -> int:
        """
        Create a query node for a word lookup.
        Parent is the current active_node_id (last response).
        
        Args:
            word: The word being looked up
            mode: Response mode (Sparkle Notes, etc.)
        
        Returns:
            New node ID
        """
        parent_info = f"parent={self.active_node_id}" if self.active_node_id else "parent=None (root)"
        self._log(f"Creating query node for '{word}' with {parent_info}")
        
        node_id = self.db.create_content_node(
            node_type='query',
            content=word,
            title=f"Query: {word}",
            parent_node_id=self.active_node_id,
            session_id=self.session_id,
            metadata={"mode": mode, "source": "user_query"}
        )
        
        self.active_node_id = node_id
        self._log(f"✓ Created query node {node_id}, active_node_id now {self.active_node_id}")
        return node_id
    
    def create_response_node(self, content: str, title: str, metadata: Optional[Dict] = None) -> int:
        """
        Create a response node as child of the current active node (query).
        
        Args:
            content: The AI response text
            title: Node title
            metadata: Additional metadata
        
        Returns:
            New node ID
        """
        self._log(f"Creating response node for '{title[:50]}...' as child of {self.active_node_id}")
        
        node_id = self.db.create_content_node(
            node_type='response',
            content=content,
            title=title,
            parent_node_id=self.active_node_id,
            session_id=self.session_id,
            metadata=metadata or {"source": "ai_response"}
        )
        
        self.active_node_id = node_id
        self._log(f"✓ Created response node {node_id}, active_node_id now {self.active_node_id}")
        return node_id
    
    def create_lookup_node(self, word: str, mode: Optional[str] = None) -> int:
        """
        Create a word lookup node (for dictionary lookups without AI).
        
        Args:
            word: The word being looked up
            mode: The mode used
        
        Returns:
            New node ID
        """
        self._log(f"Creating lookup node for '{word}'")
        
        node_id = self.db.create_content_node(
            node_type='word_lookup',
            content=word,
            title=f"Lookup: {word}",
            parent_node_id=self.active_node_id,
            session_id=self.session_id,
            metadata={"mode": mode, "source": "dictionary"}
        )
        
        self.active_node_id = node_id
        return node_id
    
    def get_node(self, node_id: int) -> Optional[Dict]:
        """Get a node by ID."""
        return self.db.get_content_node(node_id)
    
    def get_chain(self, node_id: Optional[int] = None) -> list:
        """Get the full chain from the specified node or active node."""
        target_id = node_id or self.active_node_id
        if not target_id:
            return []
        return self.db.get_content_chain(target_id)
    
    def save_word(self, word: str, context_text: str) -> Optional[str]:
        """
        Save a word to vocabulary with translation extracted from context.
        
        Args:
            word: The Chinese word
            context_text: AI response containing translation/explanation
        
        Returns:
            Word ID if saved, None otherwise
        """
        translation = self._extract_translation(context_text)
        
        # Check if word already exists
        existing_id = self.db.get_word_id(word)
        if existing_id:
            self._log(f"Word '{word}' already exists (ID: {existing_id})")
            return existing_id
        
        # Add new word
        word_id = self.db.add_word(word, translation, example="")
        self._log(f"✓ Saved word '{word}' with translation: {translation[:50]}...")
        
        # Record occurrence at current active node
        if self.active_node_id and word_id:
            self.db.record_word_occurrence(word_id, self.active_node_id, 0, len(word))
            self._log(f"  Recorded occurrence at node {self.active_node_id}")
        
        return word_id
    
    def _extract_translation(self, text: str) -> str:
        """
        Extract translation from AI response text.
        Takes first sentence or first 150 characters.
        """
        if not text:
            return ""
        
        # Try to extract first sentence
        sentences = re.split(r'[。！？\.\!\?]', text)
        first = sentences[0].strip() if sentences else text
        
        # Limit length
        if len(first) > 150:
            first = first[:147] + "..."
        
        return first
    
    def reset(self):
        """Reset the chain (start a new chain)."""
        self._log("Resetting chain (active_node_id -> None)")
        self.active_node_id = None
    
    def get_active_chain_summary(self) -> str:
        """Get a summary of the current chain for debugging."""
        if not self.active_node_id:
            return "No active node"
        
        chain = self.get_chain()
        if not chain:
            return f"Node {self.active_node_id} has no chain"
        
        summary = []
        for i, node in enumerate(chain):
            indent = "  " * i
            summary.append(f"{indent}└─ [{node['node_type']}] {node.get('title', 'Untitled')[:40]}")
        
        return "\n".join(summary)