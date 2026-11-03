"""A graphical lightshow editor. Launch with python editor.py."""
import colorsys
from copy import deepcopy
from pathlib import Path
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from editor_model import KINDS, Step, appearance, dumps, loads, swatch, validate


SCRIPTS = Path(__file__).resolve().parent / "scripts"
DEFAULTS = {"Color": [330, 35, 80], "White light": [3500, 80],
            "Brightness": [80], "White tone": [3500], "Turn on": [],
            "Turn off": [], "Pause": []}
PASTELS = [("Rose", 330), ("Peach", 25), ("Butter", 55),
           ("Mint", 155), ("Sky", 205), ("Lavender", 270)]


class Editor:
    def __init__(self, root):
        self.root = root
        self.steps, self.comments = [], []
        self.path, self.selected, self.timer = None, None, None
        self.dirty, self.loading = False, False
        self.history, self.future = [], []
        root.title("Lightshow Studio")
        root.geometry("1120x760")
        root.minsize(960, 680)
        root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        style.configure("Treeview", rowheight=40, font=("Segoe UI", 11))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        header = ttk.Frame(root, padding=16)
        header.pack(fill="x")
        ttk.Label(header, text="Lightshow Studio", font=("Segoe UI", 20, "bold")).pack(side="left")
        for title, action in (("New", self.new), ("Open…", self.open),
                              ("Save", self.save), ("Save as…", lambda: self.save(True))):
            ttk.Button(header, text=title, command=action).pack(side="left", padx=(12, 0))
        body = ttk.Panedwindow(root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=16)
        left, right = ttk.Frame(body), ttk.Frame(body, padding=(20, 0, 0, 0))
        body.add(left, weight=3)
        body.add(right, weight=2)
        ttk.Label(left, text="Your sequence", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 8))
        listing = ttk.Frame(left)
        listing.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(listing, columns=("step", "hold"), selectmode="browse")
        self.tree.heading("#0", text="Color")
        self.tree.column("#0", width=65, stretch=False)
        self.tree.heading("step", text="Light step")
        self.tree.column("step", width=250)
        self.tree.heading("hold", text="Hold")
        self.tree.column("hold", width=85, stretch=False)
        scroll = ttk.Scrollbar(listing, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.select)
        actions = ttk.Frame(left, padding=(0, 10))
        actions.pack(fill="x")
        for title, action in (("+ Add", self.add), ("Duplicate", self.duplicate),
                              ("Delete", self.delete), ("↑", lambda: self.move(-1)),
                              ("↓", lambda: self.move(1)), ("Undo", self.undo), ("Redo", self.redo)):
            ttk.Button(actions, text=title, command=action, width=9).pack(side="left", padx=(0, 4))
        ttk.Label(right, text="Make it yours", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        self.form = ttk.Frame(right)
        self.form.pack(fill="x", pady=10)
        self.preview_canvas = tk.Canvas(right, height=150, background="#272936", highlightthickness=0)
        self.preview_canvas.pack(fill="x", pady=(12, 6))
        ttk.Label(right, text="Screen preview • no bulb connection needed", wraplength=350).pack(anchor="w")
        buttons = ttk.Frame(right)
        buttons.pack(fill="x", pady=10)
        ttk.Button(buttons, text="▶ Preview show", command=self.preview).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="■ Stop", command=self.stop).pack(side="left")
        self.loop = tk.BooleanVar(value=True)
        ttk.Checkbutton(buttons, text="Loop", variable=self.loop).pack(side="left", padx=8)
        self.status = tk.StringVar()
        ttk.Label(root, textvariable=self.status, padding=16).pack(fill="x")
        root.bind("<Control-s>", lambda e: self.save())
        root.bind("<Control-o>", lambda e: self.open())
        root.bind("<Control-n>", lambda e: self.new())
        self.steps = [Step(), Step("Color", [155, 35, 80])]
        self.refresh(0)

    def title(self):
        name = self.path.stem if self.path else "New show"
        self.root.title(f"{name}{' • Unsaved' if self.dirty else ''} — Lightshow Studio")

    def snapshot(self):
        self.history.append(deepcopy(self.steps))
        self.history = self.history[-100:]
        self.future.clear()
        self.dirty = True
        self.stop()

    def refresh(self, index=None):
        self.loading = True
        self.tree.delete(*self.tree.get_children())
        self.images = []
        state = ((1, 1, 1), 80, True)
        for i, step in enumerate(self.steps):
            state = appearance(step, state)
            image = tk.PhotoImage(width=32, height=24)
            image.put(swatch(state), to=(0, 0, 32, 24))
            self.images.append(image)
            label = step.kind
            if step.kind in ("White light", "White tone"):
                label += f" • {step.values[0]} K"
            elif step.kind == "Brightness":
                label += f" • {step.values[0]}%"
            self.tree.insert("", "end", iid=str(i), image=image,
                             values=(f"{i + 1}. {label}", f"{step.seconds:g} sec"))
        self.selected = min(index, len(self.steps) - 1) if index is not None and self.steps else None
        if self.selected is not None:
            self.tree.selection_set(str(self.selected))
            self.tree.see(str(self.selected))
        self.loading = False
        self.build_form()
        self.title()
        self.status.set(f"{len(self.steps)} steps • {sum(s.seconds for s in self.steps):g} seconds per loop")

    def select(self, event=None):
        if self.loading or not self.tree.selection():
            return
        index = int(self.tree.selection()[0])
        if index == self.selected:
            return
        if not self.commit():
            if self.selected is not None:
                self.tree.selection_set(str(self.selected))
            return
        self.selected = index
        self.stop()
        self.refresh(index)

    def build_form(self):
        for child in self.form.winfo_children():
            child.destroy()
        if self.selected is None:
            ttk.Label(self.form, text="Add a step to start your show.").pack(anchor="w")
            return
        step = self.steps[self.selected]
        self.kind = tk.StringVar(value=step.kind)
        ttk.Label(self.form, text="What should the light do?").pack(anchor="w")
        combo = ttk.Combobox(self.form, values=KINDS, textvariable=self.kind, state="readonly")
        combo.pack(fill="x", pady=(4, 10))
        combo.bind("<<ComboboxSelected>>", self.change_kind)
        self.seconds = tk.StringVar(value=f"{step.seconds:g}")
        self.values = list(step.values)
        self.brightness = None
        self.temperature = None
        if step.kind == "Color":
            palette = ttk.Frame(self.form)
            palette.pack(fill="x", pady=5)
            for i, (name, hue) in enumerate(PASTELS):
                color = swatch(appearance(Step("Color", [hue, 35, 100])))
                tk.Button(palette, text=name, bg=color, fg="#222222", relief="flat",
                          command=lambda h=hue: self.pick_pastel(h)).grid(row=i // 3, column=i % 3, padx=3, pady=3, sticky="ew")
            for i in range(3):
                palette.columnconfigure(i, weight=1)
            ttk.Button(self.form, text="Choose another color…", command=self.choose_color).pack(fill="x", pady=6)
        if step.kind in ("White light", "White tone"):
            ttk.Label(self.form, text="White tone • lower is warmer").pack(anchor="w")
            self.temperature = tk.StringVar(value=str(step.values[0]))
            ttk.Spinbox(self.form, from_=1500, to=9000, increment=100,
                        textvariable=self.temperature).pack(fill="x", pady=(4, 10))
        if step.kind in ("Color", "White light", "Brightness"):
            ttk.Label(self.form, text="Brightness (%)").pack(anchor="w")
            self.brightness = tk.DoubleVar(value=step.values[-1])
            ttk.Scale(self.form, from_=0, to=100, variable=self.brightness,
                      command=lambda value: self.level.set(f"{float(value):.0f}%")).pack(fill="x")
            self.level = tk.StringVar(value=f"{step.values[-1]}%")
            ttk.Label(self.form, textvariable=self.level).pack(anchor="e")
        ttk.Label(self.form, text="Hold for (seconds)" if step.kind != "Pause" else "Wait for (seconds)").pack(anchor="w", pady=(8, 4))
        ttk.Spinbox(self.form, from_=0, to=86400, increment=0.25, textvariable=self.seconds).pack(fill="x")
        ttk.Button(self.form, text="Apply to step", command=self.apply).pack(fill="x", pady=(12, 0))
        self.show_selected()

    def read_form(self):
        if self.selected is None:
            return None
        values = list(self.values)
        if self.brightness is not None:
            values[-1] = round(self.brightness.get())
        if self.temperature is not None:
            values[0] = int(self.temperature.get())
        step = Step(self.kind.get(), values, float(self.seconds.get()))
        validate(step)
        return step

    def commit(self):
        try:
            step = self.read_form()
        except (ValueError, tk.TclError) as error:
            messagebox.showerror("Check this step", f"Please check the hold time and light settings.\n{error}")
            return False
        if step is not None and step != self.steps[self.selected]:
            self.snapshot()
            self.steps[self.selected] = step
            self.title()
        return True

    def apply(self):
        if self.commit():
            self.refresh(self.selected)

    def change_kind(self, event=None):
        # Keep the hold time when changing what the selected step does.
        kind = self.kind.get()
        self.kind.set(self.steps[self.selected].kind)
        if not self.commit():
            return
        self.snapshot()
        self.steps[self.selected] = Step(kind, list(DEFAULTS[kind]), self.steps[self.selected].seconds)
        self.refresh(self.selected)

    def pick_pastel(self, hue):
        self.values[0:2] = [hue, 35]
        self.apply()

    def choose_color(self):
        color = swatch(appearance(Step("Color", [*self.values[:2], 100])))
        rgb, _ = colorchooser.askcolor(color, title="Choose your light color", parent=self.root)
        if rgb:
            h, s, _ = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
            self.values[0:2] = [round(h * 360), round(s * 100)]
            self.apply()

    def show_selected(self):
        state = ((1, 1, 1), 80, True)
        for step in self.steps[:self.selected + 1]:
            state = appearance(step, state)
        self.preview_canvas.configure(background=swatch(state))

    def add(self):
        if not self.commit():
            return
        index = self.selected + 1 if self.selected is not None else len(self.steps)
        self.snapshot()
        self.steps.insert(index, Step())
        self.refresh(index)

    def duplicate(self):
        if self.selected is not None and self.commit():
            index = self.selected
            self.snapshot()
            self.steps.insert(index + 1, deepcopy(self.steps[index]))
            self.refresh(index + 1)

    def delete(self):
        if self.selected is not None:
            index = self.selected
            self.snapshot()
            del self.steps[index]
            self.refresh(index)

    def move(self, offset):
        if self.selected is None or not self.commit():
            return
        index, target = self.selected, self.selected + offset
        if 0 <= target < len(self.steps):
            self.snapshot()
            self.steps[index], self.steps[target] = self.steps[target], self.steps[index]
            self.refresh(target)

    def undo(self):
        if not self.commit():
            return
        if self.history:
            self.stop()
            self.future.append(deepcopy(self.steps))
            self.steps = self.history.pop()
            self.dirty = True
            self.refresh(self.selected)

    def redo(self):
        if not self.commit():
            return
        if self.future:
            self.stop()
            self.history.append(deepcopy(self.steps))
            self.steps = self.future.pop()
            self.dirty = True
            self.refresh(self.selected)

    def confirm(self):
        if not self.commit():
            return False
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel("Save your show?", "Save your changes before continuing?")
        return self.save() if answer else answer is False

    def new(self):
        if self.confirm():
            self.stop()
            self.steps, self.comments = [Step()], []
            self.path, self.dirty = None, True
            self.history, self.future = [], []
            self.refresh(0)

    def open(self):
        if not self.confirm():
            return
        name = filedialog.askopenfilename(initialdir=SCRIPTS, filetypes=[("Lightshow files", "*.csv")])
        if not name:
            return
        try:
            steps, comments = loads(Path(name).read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, ValueError) as error:
            messagebox.showerror("Cannot open show", str(error))
            return
        self.stop()
        self.steps, self.comments, self.path = steps, comments, Path(name)
        self.dirty, self.history, self.future = False, [], []
        self.refresh(0)

    def save(self, save_as=False):
        if not self.commit():
            return False
        if not self.steps:
            messagebox.showinfo("Add a light step", "Add at least one step before saving your show.")
            return False
        target = self.path
        if save_as or target is None:
            name = filedialog.asksaveasfilename(initialdir=target.parent if target else SCRIPTS,
                initialfile=target.name if target else "my_show.csv", defaultextension=".csv",
                filetypes=[("Lightshow files", "*.csv")])
            if not name:
                return False
            target = Path(name)
        try:
            target.write_text(dumps(self.steps, self.comments), encoding="utf-8")
        except (OSError, ValueError) as error:
            messagebox.showerror("Cannot save show", str(error))
            return False
        self.path, self.dirty = target, False
        self.title()
        self.status.set(f"Saved {target.name}")
        return True

    def preview(self):
        if not self.commit() or not self.steps:
            return
        self.stop()
        self.play_steps = deepcopy(self.steps)
        self.play_state = ((1, 1, 1), 80, True)
        self.play(0)

    def play(self, index):
        self.timer = None
        if index >= len(self.play_steps):
            if self.loop.get():
                index = 0
            else:
                self.status.set("Preview finished")
                return
        step = self.play_steps[index]
        self.play_state = appearance(step, self.play_state)
        self.preview_canvas.configure(background=swatch(self.play_state))
        self.tree.see(str(index))
        self.status.set(f"Playing step {index + 1} of {len(self.play_steps)} • {step.kind} • {step.seconds:g} seconds")
        self.timer = self.root.after(max(1, round(step.seconds * 1000)), lambda: self.play(index + 1))

    def stop(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
            self.status.set("Preview stopped")

    def close(self):
        if self.confirm():
            self.stop()
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    Editor(root)
    root.mainloop()
