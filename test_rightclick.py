import customtkinter as ctk
from CTkMenuBarPlus import ContextMenu

def copy_action():
    print("Copied!")

def paste_action():
    print("Pasted!")

def format_bold():
    print("Apply bold")

def format_italic():
    print("Apply italic")

app = ctk.CTk()
label = ctk.CTkLabel(app, text="Right-click me for nested menu!")
label.pack(padx=20, pady=20)

# Create context menu
context_menu = ContextMenu(label)

# Add top-level options
context_menu.add_option("Copy", copy_action, accelerator="Ctrl+C")
context_menu.add_option("Paste", paste_action, accelerator="Ctrl+V")
context_menu.add_separator()

# Add a submenu (nested options)
format_submenu = context_menu.add_submenu("Format")  # Creates the nested menu
format_submenu.add_option("Bold", format_bold)
format_submenu.add_option("Italic", format_italic)
format_submenu.add_separator()
format_submenu.add_option("Underline", lambda: print("Apply underline"))

# Add another submenu
edit_submenu = context_menu.add_submenu("Edit")
edit_submenu.add_option("Find", lambda: print("Find"))
edit_submenu.add_option("Replace", lambda: print("Replace"))

app.mainloop()