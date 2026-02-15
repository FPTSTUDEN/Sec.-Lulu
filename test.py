import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.withdraw() # Hides the main tiny window
# messagebox.showinfo("Alert", "This is a standard popup!")
# Long test popup
def long_test_popup():
    long_popup = tk.Toplevel()
    long_popup.title("Long Test Popup")
    text = "This is a long test popup. " * 20
    label = tk.Label(long_popup, text=text, wraplength=400) # Wrap text
    label.pack(pady=20) # Add some padding
    long_popup.after(3000, long_popup.destroy)  # Auto close after 3 seconds
    long_popup.mainloop()
long_test_popup()
# === Minimal PySide6 App with Threading and Popup ===
# from PySide6.QtWidgets import *
# from PySide6.QtCore import *
# import threading
# import time

# class Worker(QObject):
#     finished = Signal(str)
    
#     @Slot(str)
#     def work(self, data):
#         time.sleep(2)  # Simulate work
#         self.finished.emit(f"Result: {data}")

# class Popup(QDialog):
#     def __init__(self, text):
#         super().__init__()
#         self.setWindowTitle("Popup")
#         layout = QVBoxLayout()
#         layout.addWidget(QLabel(text))
#         btn = QPushButton("Close")
#         btn.clicked.connect(self.close)
#         layout.addWidget(btn)
#         self.setLayout(layout)
#         QTimer.singleShot(3000, self.close)  # Auto close

# class MainWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         btn = QPushButton("Start")
#         btn.clicked.connect(self.start_work)
#         self.setCentralWidget(btn)
    
#     def start_work(self):
#         # Threading
#         self.thread = QThread()
#         self.worker = Worker()
#         self.worker.moveToThread(self.thread)
#         self.thread.started.connect(lambda: self.worker.work("data"))
#         self.worker.finished.connect(self.on_finished)
#         self.worker.finished.connect(self.thread.quit)
#         self.thread.start()
    
#     def on_finished(self, result):
#         # Popup
#         popup = Popup(result)
#         popup.show()

# app = QApplication([])
# win = MainWindow()
# win.show()
# app.exec()


