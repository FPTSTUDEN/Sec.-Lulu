# test_chain_visual.py
"""Interactive test for content chaining"""

import time
from lib.db import VocabDatabase
from lib.debug_utils import DebugLogger

def test_chaining_visual():
    logger = DebugLogger("ChainTest")
    
    # Use a test database
    db = VocabDatabase("test_chain.db")
    
    # Simulate a real conversation flow
    logger.info("="*60)
    logger.info("SIMULATING REAL CHAINING SCENARIO")
    logger.info("="*60)
    
    # Step 1: User copies text
    original_text = "我喜欢学习中文"
    logger.info(f"\n1. User copies text: '{original_text}'")
    node1 = db.create_content_node(
        node_type='raw_text',
        content=original_text,
        title="Copied Text",
        session_id=None
    )
    logger.info(f"   Created raw_text node: {node1}")
    
    # Step 2: User clicks on a word to look up
    lookup_word = "学习"
    logger.info(f"\n2. User looks up word: '{lookup_word}'")
    node2 = db.create_content_node(
        node_type='query',
        content=lookup_word,
        title=f"Lookup: {lookup_word}",
        parent_node_id=node1,
        metadata={"source": "clipboard_click"}
    )
    logger.info(f"   Created query node: {node2} (parent={node1})")
    
    # Step 3: AI generates response
    logger.info(f"\n3. AI generates response for '{lookup_word}'")
    response_text = f"'{lookup_word}' means 'to study' or 'to learn'"
    node3 = db.create_content_node(
        node_type='response',
        content=response_text,
        title=f"Explanation: {lookup_word}",
        parent_node_id=node2,
        metadata={"source": "ai_response", "mode": "Sparkle Notes"}
    )
    logger.info(f"   Created response node: {node3} (parent={node2})")
    
    # Step 4: User clicks on a word IN the response
    new_lookup = "中文"
    logger.info(f"\n4. User clicks on word in response: '{new_lookup}'")
    node4 = db.create_content_node(
        node_type='query',
        content=new_lookup,
        title=f"Lookup: {new_lookup}",
        parent_node_id=node3,
        metadata={"source": "response_click"}
    )
    logger.info(f"   Created chained query node: {node4} (parent={node3})")
    
    # Step 5: AI responds to the new query
    logger.info(f"\n5. AI generates response for '{new_lookup}'")
    response2_text = f"'{new_lookup}' means 'Chinese language'"
    node5 = db.create_content_node(
        node_type='response',
        content=response2_text,
        title=f"Explanation: {new_lookup}",
        parent_node_id=node4,
        metadata={"source": "ai_response", "mode": "Sparkle Notes"}
    )
    logger.info(f"   Created response node: {node5} (parent={node4})")
    
    # Show chains
    logger.info("\n" + "="*60)
    logger.info("CHAIN FOR ORIGINAL RESPONSE (node3):")
    db.debug_print_chain(node3)
    
    logger.info("\n" + "="*60)
    logger.info("CHAIN FOR CHAINED RESPONSE (node5):")
    db.debug_print_chain(node5)
    
    # Verify chain length
    chain3 = db.get_content_chain(node3)
    chain5 = db.get_content_chain(node5)
    
    logger.info(f"\n✅ Node3 chain length: {len(chain3)} (expected 3)")
    logger.info(f"✅ Node5 chain length: {len(chain5)} (expected 5)")
    
    assert len(chain3) == 3, f"Expected 3 nodes, got {len(chain3)}"
    assert len(chain5) == 5, f"Expected 5 nodes, got {len(chain5)}"
    
    logger.info("\n🎉 Chain test passed!")
    
    # Print full chain for node5
    logger.info("\nFull chain for node5:")
    for i, node in enumerate(chain5):
        logger.info(f"  [{i}] {node['node_type']}: {node.get('title', 'No title')[:50]}")
    
    return db

if __name__ == "__main__":
    test_chaining_visual()
    print("\n" + "="*60)
    print("To run with your actual app, restart and copy text.")
    print("The debug console (🐛 button) will show chain information.")
    print("Press Ctrl+D in any popup to debug its chain.")