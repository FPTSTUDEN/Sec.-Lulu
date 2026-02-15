import tkinter as tk
from tkinter import font

root = tk.Tk()
root.title("Custom Overlay")
root.geometry("400x200")

# 1. Custom Font
# Note: "Helvetica" is standard, but you can use "Impact" or "Courier"
custom_font = font.Font(family="Comic Sans MS", size=16, weight="bold")

# 2. Adding an Image (Requires a .png or .gif in the same folder)
# img = tk.PhotoImage(file="logo.png")
# label_img = tk.Label(root, image=img)
# label_img.pack()

# 3. GUI Actions (Label and Button)
label = tk.Label(root, text="Hello World", font=custom_font)
label.pack(pady=10)

def on_click():
    label.config(text="Button Clicked!", fg="red")

button = tk.Button(root, text="Click Me", command=on_click)
button.pack()

root.mainloop()