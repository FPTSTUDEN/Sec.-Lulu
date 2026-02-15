import customtkinter
import os
def button_callback():
    print("button clicked")

app = customtkinter.CTk()
app.geometry("400x150")

# Set path to current folder

current_folder = os.path.dirname(os.path.abspath(__file__))
# customtkinter.FontManager.load_font(os.path.join(current_folder, "Mengshen-HanSerif.ttf"))
customtkinter.FontManager.load_font(os.path.join(current_folder, "Mengshen-Handwritten.ttf"))

button = customtkinter.CTkButton(app, text="my button", command=button_callback, font=("Mengshen-Handwritten",20))
button.pack(padx=20, pady=20)

app.mainloop()