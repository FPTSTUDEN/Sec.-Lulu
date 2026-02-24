import tkinter as tk
import customtkinter
import os
current_folder = os.path.dirname(os.path.abspath(__file__))
# customtkinter.FontManager.load_font(os.path.join(current_folder, "Mengshen-HanSerif.ttf"))
customtkinter.FontManager.load_font(os.path.join(current_folder, "Mengshen-Handwritten.ttf"))
def popup_message(title, message):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    tk.messagebox.showinfo(title, message)
    root.destroy()
class Long_message_popup:
    def __init__(self, title, message):
        long_popup = customtkinter.CTk()
        long_popup.geometry("600x300")
        # Title in bold with custom font
        title_label = customtkinter.CTkLabel(long_popup, text=title, font=("Mengshen-Handwritten", 20, "bold"))
        title_label.pack(pady=(5, 5))
        # Message in scrollable text box with custom font
        text_box = customtkinter.CTkTextbox(long_popup, wrap="word", font=("Mengshen-Handwritten", 16))
        text_box.insert("1.0", message)
        text_box.configure(state="disabled")  # Make it read-only
        text_box.pack(padx=20, pady=10, fill="both", expand=True)
        # label = customtkinter.CTkLabel(long_popup, text=message, wraplength=380, font=("Mengshen-Handwritten", 12))
        # label.pack(pady=20)
        self.long_popup = long_popup
    def show(self):
        self.long_popup.mainloop()
    def add_button(self, text, command):
        if command is None:
            command = self.long_popup.destroy
        btn = customtkinter.CTkButton(self.long_popup, text=text, command=command)
        btn.pack(pady=10)
class ControlPanel:
    def __init__(self): # always-on-top popup, with start,pause,exit buttons
        self.opened=True
        self.done=False
        self.root = customtkinter.CTk()
        self.root.title("Monitor")
        self.root.resizable(width=False, height=False)
        self.root.wm_attributes("-topmost", True)
        btn = customtkinter.CTkButton(self.root, text="Start", command=lambda: self.start())
        btn.pack(side="top", fill="x")
        btn = customtkinter.CTkButton(self.root, text="Pause", command=lambda: self.pause())
        btn.pack(side="top", fill="x")
        btn = customtkinter.CTkButton(self.root, text="Exit", command=lambda: self.cancel())
        btn.pack(side="top", fill="x")
    def show(self):
        self.root.mainloop()
    def hide(self):
        self.root.destroy()
    def start(self):
        self.opened=True
    def pause(self):
        self.opened=False
    def cancel(self):
        # print("Cancelled")
        self.done=True
        # print(self.done)
        self.root.destroy()
if __name__ == "__main__":
    popup_message("Test Message", "This is a test message to verify the popup_message function is working correctly.")
    panel=ControlPanel()
    panel.show()
    longpop=Long_message_popup("Test Long Message", "This is a long message to test the Long_message_popup class. It should wrap properly and use the custom font loaded from the Mengshen-Handwritten.ttf file. If you see this message clearly, it means the function is working correctly!"*5)
    longpop.show()
