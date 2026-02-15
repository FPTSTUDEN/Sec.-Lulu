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
def popup_long_message(title, message):
    long_popup = customtkinter.CTk()
    long_popup.geometry("600x300")
    # Title in bold with custom font
    title_label = customtkinter.CTkLabel(long_popup, text=title, font=("Mengshen-Handwritten", 16, "bold"))
    title_label.pack(pady=(5, 5))
    # Message in scrollable text box with custom font
    text_box = customtkinter.CTkTextbox(long_popup, wrap="word", font=("Mengshen-Handwritten", 12))
    text_box.insert("1.0", message)
    text_box.configure(state="disabled")  # Make it read-only
    text_box.pack(padx=20, pady=10, fill="both", expand=True)
    # label = customtkinter.CTkLabel(long_popup, text=message, wraplength=380, font=("Mengshen-Handwritten", 12))
    # label.pack(pady=20)
    long_popup.mainloop()
if __name__ == "__main__":
    popup_message("Test Message", "This is a test message to verify the popup_message function is working correctly.")
    popup_long_message("Test Long Message", "This is a long message to test the popup_long_message function. It should wrap properly and use the custom font loaded from the Mengshen-Handwritten.ttf file. If you see this message clearly, it means the function is working correctly!"*5)