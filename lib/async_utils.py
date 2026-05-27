"""
Unified async utilities for the vocabulary learning app.
Single set of functions for all async operations.
"""

import threading
import customtkinter as ctk
from typing import Callable, Generator, Optional, Any


def run_async(
    root: ctk.CTk,
    worker_func: Callable[[], Any],
    on_done: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None
) -> threading.Thread:
    """
    Run any function in background, call callback on UI thread.
    
    Args:
        root: Tkinter root widget (for after())
        worker_func: Function to run (returns value or None)
        on_done: Called with result on UI thread
        on_error: Called with exception on UI thread
    
    Returns:
        The background thread
    """
    def wrapper():
        try:
            result = worker_func()
            if on_done:
                root.after(0, lambda: on_done(result))
        except Exception as e:
            print(f"Async error: {e}")
            if on_error:
                root.after(0, lambda: on_error(e))
    
    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    return thread


def stream_to_widgets(
    root: ctk.CTk,
    generator: Generator[str, None, None],
    text_widget: ctk.CTkTextbox,
    think_widget: Optional[ctk.CTkTextbox] = None,
    on_complete: Optional[Callable[[str], None]] = None,
    show_thinking: bool = True
) -> threading.Thread:
    """
    Stream generator output to text widgets.
    
    Args:
        root: Tkinter root widget
        generator: Generator that yields strings (may contain __THINK__ markers)
        text_widget: CTkTextbox for main content
        think_widget: Optional CTkTextbox for thinking output
        on_complete: Called with full text when done
        show_thinking: If False, ignore __THINK__ markers
    
    Returns:
        The background thread
    """
    full_text = []
    
    def _append(widget: ctk.CTkTextbox, text: str):
        """Thread-safe append to CTkTextbox."""
        try:
            widget.configure(state="normal")
            widget.insert("end", text)
            widget.configure(state="disabled")
            widget.see("end")
        except:
            pass
    
    def _clear(widget: ctk.CTkTextbox):
        """Thread-safe clear."""
        try:
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.configure(state="disabled")
        except:
            pass
    
    def worker():
        try:
            for chunk in generator:
                if show_thinking and chunk.startswith("__THINK__"):
                    thinking = chunk[len("__THINK__"):]
                    if think_widget:
                        root.after(0, lambda t=thinking: _append(think_widget, t))
                else:
                    full_text.append(chunk)
                    root.after(0, lambda c=chunk: _append(text_widget, c))
            
            if on_complete:
                root.after(0, lambda: on_complete(''.join(full_text)))
        except Exception as e:
            print(f"Streaming error: {e}")
            root.after(0, lambda: _append(text_widget, f"\n\n[Error: {e}]"))
    
    # Clear widgets before starting
    root.after(0, lambda: _clear(text_widget))
    if think_widget:
        root.after(0, lambda: _clear(think_widget))
    
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread


def set_widget_text(widget: ctk.CTkTextbox, text: str):
    """
    Set text widget content (must be called from UI thread).
    
    Args:
        widget: CTkTextbox to modify
        text: New text content
    """
    try:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")
    except:
        pass


def clear_widget(widget: ctk.CTkTextbox):
    """
    Clear text widget (must be called from UI thread).
    
    Args:
        widget: CTkTextbox to clear
    """
    try:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.configure(state="disabled")
    except:
        pass