"""Desktop controls for a configured LegoCam measurement session."""
import base64
from datetime import datetime
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import cv2

from legocam import read_json, references


class App:
    def __init__(self, root):
        self.root = root
        root.title("LegoCam")
        root.geometry("1050x1000")
        self.messages = queue.Queue()
        self.busy = False
        self.session = tk.StringVar(value="sessions/final_rig")
        self.block = tk.StringVar(value="B100")
        self.role = tk.StringVar(value="calibration")
        self.placement = tk.StringVar(value="centre-horizontal")
        self.label = tk.StringVar(value="lego_one")
        self.radial = tk.BooleanVar(value=False)
        top = ttk.Frame(root, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="LegoCam length and width", font=("Segoe UI", 18)).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(top, text="Session").grid(row=1, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.session, width=40).grid(row=1, column=1, columnspan=2, sticky="w")
        ttk.Label(top, text="Reference block").grid(row=2, column=0, sticky="w")
        ttk.Combobox(top, textvariable=self.block, values=list(references()), state="readonly", width=12).grid(row=2, column=1, sticky="w")
        ttk.Combobox(top, textvariable=self.role, values=["calibration", "validation"], state="readonly", width=15).grid(row=2, column=2)
        ttk.Button(top, text="Capture reference", command=self.reference).grid(row=2, column=3, padx=8)
        ttk.Label(top, text="Placement").grid(row=3, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.placement, width=25).grid(row=3, column=1, columnspan=2, sticky="w")
        ttk.Label(top, text="Brick label").grid(row=4, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.label, width=25).grid(row=4, column=1, columnspan=2, sticky="w")
        ttk.Button(top, text="Capture brick", command=self.brick).grid(row=4, column=3, padx=8)
        ttk.Button(top, text="Fit calibration", command=lambda: self.run(["fit", "--radial"] if self.radial.get() else ["fit"])).grid(row=5, column=0, pady=10)
        ttk.Button(top, text="Calculate results", command=lambda: self.run(["results"])).grid(row=5, column=1)
        ttk.Button(top, text="Show latest results", command=self.results).grid(row=5, column=2)
        ttk.Button(top, text="Build report", command=lambda: self.run([], report=True)).grid(row=5, column=3)
        ttk.Checkbutton(top, text="Fit radial correction (validate against held-out blocks)", variable=self.radial).grid(row=6, column=0, columnspan=4, sticky="w")
        ttk.Label(top, text="Keep the rig fixed. Inspect the green outline after each capture. Results remain provisional until validated.").grid(row=7, column=0, columnspan=4, sticky="w")
        self.preview = ttk.Label(root)
        self.preview.pack()
        self.log = tk.Text(root, height=11, wrap="word")
        self.log.pack(fill="both", expand=True, padx=12, pady=8)
        self.log.insert("end", "Ready. Each capture saves five frames from one placement.\n")
        self.refresh_preview()
        root.after(200, self.poll)

    def reference(self):
        label = self.block.get()+"_"+datetime.now().strftime("%H%M%S")
        self.run(["capture", "--label", label, "--role", self.role.get(), "--block", self.block.get(), "--placement", self.placement.get()])

    def brick(self):
        self.run(["capture", "--label", self.label.get()+"_"+datetime.now().strftime("%H%M%S"),
                  "--role", "measurement", "--placement", self.placement.get()])

    def run(self, arguments, report=False):
        if self.busy:
            messagebox.showinfo("Capture in progress", "Wait for the current operation to finish.")
            return
        if not (Path(self.session.get())/"setup.json").exists():
            messagebox.showerror("Setup needed", "Configure this session with legocam.py setup first. See WORKFLOW.md.")
            return
        self.busy = True
        command = [sys.executable, str(Path(__file__).with_name("build_report.py" if report else "legocam.py")), "--session", self.session.get(), *arguments]
        self.log.insert("end", "Working: "+" ".join(arguments)+"\n")
        def worker():
            try:
                result = subprocess.run(command, capture_output=True, text=True)
                self.messages.put((result.returncode, result.stdout+result.stderr))
            except Exception as error:
                self.messages.put((1, str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            code, text = self.messages.get_nowait()
            self.busy = False
            self.log.insert("end", text+"\n")
            self.log.see("end")
            self.refresh_preview()
            if code:
                messagebox.showerror("Operation failed", text[-1200:])
        except queue.Empty:
            pass
        self.root.after(200, self.poll)

    def refresh_preview(self):
        path = Path(self.session.get())/"latest_preview.jpg"
        if not path.exists():
            return
        image = cv2.imread(str(path))
        if image is None:
            return
        image = cv2.resize(image, (720, 568))
        ok, png = cv2.imencode(".png", image)
        if ok:
            self.photo = tk.PhotoImage(data=base64.b64encode(png).decode("ascii"))
            self.preview.configure(image=self.photo)

    def results(self):
        path = Path(self.session.get())/"summary.json"
        if not path.exists():
            messagebox.showinfo("Results", "Fit calibration and calculate results first.")
            return
        summary = read_json(path)
        window = tk.Toplevel(self.root)
        window.title("Measurement results")
        tree = ttk.Treeview(window, columns=("label", "role", "length", "width"), show="headings")
        for key, heading in zip(tree["columns"], ("Capture", "Role", "Length mm", "Width mm")):
            tree.heading(key, text=heading)
        for row in summary["records"]:
            tree.insert("", "end", values=(row["label"], row["role"], f"{row['length_mm']:.3f}", f"{row['width_mm']:.3f}"))
        tree.pack(fill="both", expand=True)
        ttk.Label(window, text=summary["uncertainty_status"]).pack(padx=8, pady=8)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
