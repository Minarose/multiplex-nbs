"""Standalone desktop interface. Tk draws the UI and the analysis runs in this process."""
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import font, messagebox, ttk

from . import __build__, __version__
from .demo import make_brain_demo
from .io import describe, make_demo, result_csv, result_mat, run_dataset, validate_dataset
from .native_figures import CAPTIONS, METHODS, draw_method_figure
from .native_reference import TOPICS, paragraph, reference_page


# Dark: Material-style tinted charcoal (#121212 family, hue nudged toward the brand teal).
# Depth comes from lighter surfaces, not shadows; text is off-white at about 87% and 60%
# emphasis; the accent is a desaturated pastel teal so it does not vibrate on dark grey.
DARK = dict(bg="#121515", rail="#0f1212", surface="#1b1f1f", raised="#232828", line="#2e3434",
            input="#101313", fg="#e2e6e5", muted="#9aa2a0", faint="#646d6b",
            accent="#80cbc4", on_accent="#0b1d1b", plot="#1b1f1f", other="#5c6664", warn="#e3cf8c",
            select="#29403d",
            field="#1b1f1f", plate="#232b2a", plate_edge="#4a6b66", grid="#2c3636", node="#56625f",
            wire="#80cbc4", paper="#e2e6e5", paper_muted="#9aa2a0")
# Mono: black and white. Neutral greys only; white is the single accent.
MONO = dict(bg="#121212", rail="#0e0e0e", surface="#1c1c1c", raised="#252525", line="#313131",
            input="#0f0f0f", fg="#e6e6e6", muted="#9c9c9c", faint="#666666",
            accent="#e6e6e6", on_accent="#121212", plot="#1c1c1c", other="#5e5e5e", warn="#d6d6d6",
            select="#383838",
            field="#1c1c1c", plate="#262626", plate_edge="#6a6a6a", grid="#303030", node="#5a5a5a",
            wire="#e6e6e6", paper="#e6e6e6", paper_muted="#9c9c9c")
# Light: the same teal hue as dark mode at a deeper tone (#00695c) so it stays readable on a
# light page; greys are tinted toward teal to match.
LIGHT = dict(bg="#f5f8f8", rail="#f5f8f8", raised="#d9e7e5", input="#e5efee", faint="#7a8c8a", select="#00695c",
             surface="#e5efee", fg="#132523", muted="#3e5652", line="#adc2bf",
             accent="#00695c", on_accent="#ffffff", plot="#e0ecea", other="#637b77", warn="#85531a",
             field="#e7f1f0", plate="#d0e5e2", plate_edge="#4f8f87", grid="#bad4d0", node="#6f918c",
             wire="#00695c", paper="#10302c", paper_muted="#3f5e59")


THEMES = {"light": LIGHT, "dark": DARK, "mono": MONO}
THEME_LABELS = (("light", "Light"), ("dark", "Dark"), ("mono", "Mono"))

PAGES = {"home":"Overview", "data":"Data", "model":"Statistical model", "results":"Results", **TOPICS}


class DesktopRoot(tk.Tk):
    def readprofile(self, baseName, className):
        # Desktop builds do not use Tcl or Python customization scripts from the user's home folder.
        pass


class NativeApp:
    def __init__(self, root, full_screen=False):
        self.root = root
        self.data = self.description = self.result = None
        self.name = ""
        self.config = {}
        self.pages = {}
        self.scroll_positions = {}
        self.page = self.return_page = "home"
        self.worker = None
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.demo_mode = tk.StringVar(root, "multiplex")
        self.theme = "light"
        self.nav = {}
        root.title("Multiplex-NBS")
        root.minsize(1000, 640)
        width = min(1350, max(1000, root.winfo_screenwidth() - 48))
        height = min(930, max(640, root.winfo_screenheight() - 80))
        root.geometry(f"{width}x{height}")
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self._style()
        shell = ttk.Frame(root)
        shell.pack(fill="both", expand=True)
        self.side = ttk.Frame(shell, padding=(24, 30, 22, 24), style="Rail.TFrame")
        self.side.pack(side="left", fill="y")
        ttk.Separator(shell, orient="vertical").pack(side="left", fill="y")
        self._navigation()
        workspace = ttk.Frame(shell)
        workspace.pack(side="left", fill="both", expand=True)
        # One scroll unit is one pixel, so wheels and trackpads scroll smoothly.
        self.viewport = tk.Canvas(workspace, bg=self.colors["bg"], bd=0, highlightthickness=0, yscrollincrement=1)
        bar = ttk.Scrollbar(workspace, orient="vertical", command=self.viewport.yview)
        self.viewport.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.viewport.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.viewport, padding=(52, 40, 52, 56))
        self.window_id = self.viewport.create_window(0, 0, anchor="nw", window=self.body)
        self.body.bind("<Configure>", self._size_canvas)
        self.viewport.bind("<Configure>", lambda e: self.viewport.itemconfigure(self.window_id, width=e.width))
        root.bind_all("<MouseWheel>", self._scroll, add=True)
        try:
            # Tk 9 reports trackpads and the Magic Mouse as TouchpadScroll, not MouseWheel.
            root.bind_all("<TouchpadScroll>", self._touchpad, add=True)
        except tk.TclError:
            pass
        if root.tk.call("tk", "windowingsystem") == "x11":
            root.bind_all("<Button-4>", self._scroll, add=True)
            root.bind_all("<Button-5>", self._scroll, add=True)
        root.bind("<F11>", lambda e: self.set_full_screen(not self.full_screen()))
        root.bind("<Escape>", lambda e: self.set_full_screen(False))
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.show("home")
        self.set_full_screen(full_screen)

    def _style(self):
        c = self.colors = THEMES.get(self.theme, LIGHT)
        dark = self.theme != "light"
        platform = self.root.tk.call("tk", "windowingsystem")
        self.family = {"aqua":"Helvetica Neue", "win32":"Segoe UI"}.get(platform, "DejaVu Sans")
        default = font.nametofont("TkDefaultFont")
        default.configure(family=self.family, size=12)
        font.nametofont("TkTextFont").configure(family=self.family, size=12)
        self.root.option_add("*TCombobox*Listbox.background", c["surface"])
        self.root.option_add("*TCombobox*Listbox.foreground", c["fg"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", c["select"] if dark else c["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", c["fg"] if dark else c["on_accent"])
        style = self.style
        style.configure(".", background=c["bg"], foreground=c["fg"], fieldbackground=c["surface"],
                        bordercolor=c["line"], lightcolor=c["line"], darkcolor=c["line"],
                        troughcolor=c["bg"], selectbackground=c["accent"], selectforeground=c["on_accent"],
                        font=default)
        style.configure("TButton", padding=(16, 6), width=0, background=c["raised"] if dark else c["surface"],
                        foreground=c["fg"], bordercolor=c["line"],
                        lightcolor=c["raised"] if dark else c["line"], darkcolor=c["raised"] if dark else c["line"])
        style.map("TButton", background=[("active", c["line"] if dark else c["line"])],
                  lightcolor=[("active", c["line"])], darkcolor=[("active", c["line"])],
                  foreground=[("disabled", c["faint"])])
        style.configure("Primary.TButton", background=c["accent"], foreground=c["on_accent"], font=(self.family,12,"bold"),
                        bordercolor=c["accent"], lightcolor=c["accent"], darkcolor=c["accent"])
        style.map("Primary.TButton", background=[("disabled",c["line"]),("active",c["fg"])],
                  foreground=[("disabled",c["muted"]),("active",c["bg"])])
        for name,size,bold in [("PageTitle",26,True),("Heading",16,True),("Brand",20,True),("Kicker",11,True),("Muted",12,False)]:
            style.configure(name+".TLabel",font=(self.family,size,"bold" if bold else "normal"),
                            foreground=c["muted"] if name in ("Kicker","Muted") else c["fg"])
        style.configure("Nav.TButton", anchor="w", padding=(12, 9), relief="flat", background=c["bg"])
        style.configure("Segment.TFrame", background=c["line"])
        style.configure("SideSegment.Toolbutton", background=c["bg"], foreground=c["fg"], padding=(14, 8),
                        font=(self.family, 12), relief="flat", borderwidth=0, anchor="center")
        style.map("SideSegment.Toolbutton", background=[("selected", c["accent"]), ("active", c["surface"])],
                  foreground=[("selected", c["on_accent"])], focuscolor=[("selected", c["accent"]), ("!selected", c["bg"])])
        style.configure("SideAction.TButton", background=c["bg"], foreground=c["muted"], padding=(0, 5),
                        relief="flat", borderwidth=0, font=(self.family, 12), anchor="w")
        style.map("SideAction.TButton", background=[("active", c["bg"])], foreground=[("active", c["fg"])])
        style.configure("SideNote.TLabel", foreground=c["muted"], font=(self.family, 10))
        # Cards, segmented choices and text styles shared by the pages.
        self.mono = {"aqua": "Menlo", "win32": "Consolas"}.get(platform, "DejaVu Sans Mono")
        style.configure("Lead2.TLabel", foreground=c["fg"], font=(self.family, 14))
        style.configure("Lead3.TLabel", foreground=c["fg"], font=(self.family, 13))
        style.configure("Card.TFrame", background=c["surface"])
        style.configure("Card.TLabel", background=c["surface"], foreground=c["fg"])
        style.configure("CardTitle.TLabel", background=c["surface"], foreground=c["fg"], font=(self.family, 15, "bold"))
        style.configure("CardSmallHeading.TLabel", background=c["surface"], foreground=c["fg"], font=(self.family, 12, "bold"))
        style.configure("CardKicker.TLabel", background=c["surface"], foreground=c["muted"], font=(self.family, 10, "bold"))
        style.configure("CardMuted.TLabel", background=c["surface"], foreground=c["muted"])
        style.configure("CardWarn.TLabel", background=c["surface"], foreground=c["warn"])
        style.configure("CardCode.TLabel", background=c["surface"], foreground=c["fg"], font=(self.mono, 12))
        style.configure("Card.TRadiobutton", background=c["surface"], foreground=c["fg"], font=(self.family, 13, "bold"),
                        indicatorbackground=c["input"] if dark else "#ffffff", indicatorforeground=c["accent"],
                        upperbordercolor=c["faint"], lowerbordercolor=c["faint"])
        style.map("Card.TRadiobutton", background=[("active", c["surface"])])
        style.configure("Card.TButton", background=c["bg"], foreground=c["fg"])
        style.map("Card.TButton", background=[("active", c["line"])])
        style.configure("Choice.Toolbutton", background=c["bg"], foreground=c["fg"], padding=(18, 8),
                        font=(self.family, 12), relief="flat", borderwidth=0)
        style.map("Choice.Toolbutton", background=[("selected", c["accent"]), ("active", c["surface"])],
                  foreground=[("selected", c["on_accent"])], focuscolor=[("selected", c["accent"]), ("!selected", c["bg"])])
        style.configure("Tab.Toolbutton", background=c["bg"], foreground=c["muted"], padding=(16, 8),
                        font=(self.family, 12), relief="flat", borderwidth=0)
        style.map("Tab.Toolbutton", background=[("selected", c["surface"]), ("active", c["surface"])],
                  foreground=[("selected", c["accent"]), ("active", c["fg"])],
                  focuscolor=[("selected", c["surface"]), ("!selected", c["bg"])])
        style.configure("Kpi.TFrame", background=c["surface"])
        style.configure("KpiLabel.TLabel", background=c["surface"], foreground=c["muted"], font=(self.family, 11))
        style.configure("KpiValue.TLabel", background=c["surface"], foreground=c["fg"], font=(self.family, 21, "bold"))
        style.configure("Notice.TFrame", background=c["surface"])
        style.configure("Notice.TLabel", background=c["surface"], foreground=c["fg"])
        style.configure("Detail.TLabel", foreground=c["muted"], font=(self.family, 11))
        style.configure("DetailValue.TLabel", foreground=c["fg"], font=(self.family, 12))
        style.configure("Code.TLabel", foreground=c["fg"], font=(self.mono, 12))
        style.configure("Link.TButton", background=c["bg"], foreground=c["accent"], padding=(0, 4), relief="flat",
                        borderwidth=0, font=(self.family, 12, "underline"))
        style.map("Link.TButton", background=[("active", c["bg"])], foreground=[("active", c["fg"])])
        # Checkboxes show a teal tick in a light box, so they never look like a legend colour swatch.
        box = c["input"] if dark else "#ffffff"
        style.configure("TCheckbutton", background=c["bg"], foreground=c["fg"], indicatorbackground=box,
                        indicatorforeground=c["accent"], upperbordercolor=c["faint"], lowerbordercolor=c["faint"])
        style.map("TCheckbutton", background=[("active", c["bg"])], indicatorbackground=[("pressed", c["surface"])])
        style.configure("Selected.Nav.TButton",background=c["surface"],foreground=c["accent"], font=(self.family,12,"bold"))
        style.configure("TLabelframe", bordercolor=c["line"], relief="solid")
        style.configure("TLabelframe.Label", font=(self.family,13,"bold"))
        style.configure("Treeview", rowheight=max(34,default.metrics("linespace")+16),fieldbackground=c["surface"])
        style.configure("Treeview.Heading",font=(self.family,11,"bold"),background=c["surface"],foreground=c["fg"])
        style.configure("Treeview", background=c["surface"], foreground=c["fg"], bordercolor=c["line"],
                        lightcolor=c["surface"], darkcolor=c["surface"])
        style.configure("Treeview.Heading", relief="flat", bordercolor=c["line"],
                        lightcolor=c["surface"], darkcolor=c["surface"], foreground=c["muted"] if dark else c["fg"])
        style.map("Treeview", background=[("selected", c["select"] if dark else c["accent"])],
                  foreground=[("selected", c["fg"] if dark else c["on_accent"])])
        for name in ("TCombobox","TEntry","TSpinbox"):
            field = c["input"] if dark else c["surface"]
            style.configure(name,padding=(8, 7),fieldbackground=field,foreground=c["fg"],arrowcolor=c["muted"] if dark else c["fg"],
                            insertcolor=c["fg"], bordercolor=c["line"], lightcolor=field, darkcolor=field,
                            background=c["raised"] if dark else c["surface"])
            style.map(name,fieldbackground=[("readonly",field),("disabled",c["bg"])],
                      foreground=[("disabled",c["faint"]),("readonly",c["fg"])],
                      bordercolor=[("focus", c["accent"])])
        style.configure("TProgressbar", background=c["accent"])
        style.configure("TScrollbar", background=c["raised"] if dark else c["line"], troughcolor=c["bg"],
                        arrowcolor=c["muted"], bordercolor=c["bg"], lightcolor=c["raised"] if dark else c["line"],
                        darkcolor=c["raised"] if dark else c["line"])
        style.map("TScrollbar", background=[("active", c["other"])])
        style.configure("TSeparator", background=c["line"])
        # Player controls: compact buttons and a larger slider in the accent colour.
        style.configure("Compact.TButton", padding=(10, 4))
        style.configure("Player.Horizontal.TScale", background=c["accent"], troughcolor=c["raised"] if dark else c["surface"],
                        bordercolor=c["line"], lightcolor=c["accent"], darkcolor=c["accent"],
                        sliderlength=30, arrowsize=24, gripsize=0)
        style.map("Player.Horizontal.TScale", background=[("active", c["fg"] if not dark else c["paper"])])
        style.configure("Accent.TFrame", background=c["accent"])
        self.root.configure(bg=c["bg"])
        if platform == "aqua":
            # The macOS title bar follows the colour mode.
            try:
                self.root.wm_attributes("-appearance", "darkaqua" if dark else "aqua")
            except tk.TclError:
                pass

    def _navigation(self):
        s = self.side
        ttk.Label(s,text="Multiplex-NBS",style="Brand.TLabel").pack(anchor="w")
        ttk.Label(s,text="Version "+__version__,style="Muted.TLabel").pack(anchor="w",pady=(4,22))
        foot = ttk.Frame(s)
        foot.pack(side="bottom", fill="x", pady=(18, 0))
        self.theme_var = tk.StringVar(self.root, self.theme)
        modes = ttk.Frame(foot, style="Segment.TFrame", padding=1)
        modes.pack(anchor="w")
        for value, label in THEME_LABELS:
            ttk.Radiobutton(modes, text=label, value=value, variable=self.theme_var, style="SideSegment.Toolbutton",
                            command=lambda: self.switch_theme(self.theme_var.get())).pack(side="left")
        ttk.Button(foot, text="Quit", style="SideAction.TButton", command=self.quit).pack(anchor="w", pady=(14, 0))
        ttk.Label(foot, text="All analysis runs locally.", style="SideNote.TLabel").pack(anchor="w", pady=(10, 0))
        area = ttk.Frame(s)
        area.pack(fill="both", expand=True)
        area.columnconfigure(0, weight=1)
        area.rowconfigure(0, weight=1)
        self.nav_view = tk.Canvas(area, height=1, width=1, highlightthickness=0,
                                  bd=0, background=self.colors["bg"], yscrollincrement=1)
        self.nav_view.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(area, orient="vertical", command=self.nav_view.yview)
        self.nav_view.configure(yscrollcommand=scrollbar.set)
        topics = ttk.Frame(self.nav_view)
        window = self.nav_view.create_window(0, 0, anchor="nw", window=topics)

        def fit_navigation(_event=None):
            canvas = self.nav_view
            width, height = topics.winfo_reqwidth(), topics.winfo_reqheight()
            canvas.configure(width=width, scrollregion=(0, 0, width, height))
            canvas.itemconfigure(window, width=max(width, canvas.winfo_width()))
            if height > canvas.winfo_height():
                scrollbar.grid(row=0, column=1, sticky="ns")
            else:
                scrollbar.grid_remove()
                canvas.yview_moveto(0)

        def reveal_focus(event):
            height = topics.winfo_reqheight()
            top = self.nav_view.canvasy(0)
            bottom = top + self.nav_view.winfo_height()
            y = event.widget.winfo_y()
            end = y + event.widget.winfo_height()
            if y < top:
                self.nav_view.yview_moveto(y / height)
            elif end > bottom:
                self.nav_view.yview_moveto((end - self.nav_view.winfo_height()) / height)

        self.nav_topics = topics
        topics.bind("<Configure>", fit_navigation)
        self.nav_view.bind("<Configure>", fit_navigation)
        for group,keys in (("",["home"]),("ANALYSIS",["data","model","results"]),("REFERENCE",list(TOPICS))):
            if group:
                ttk.Label(topics,text=group,style="Kicker.TLabel").pack(anchor="w",padx=(12,0),pady=(26,8))
            for key in keys:
                button=ttk.Button(topics,text=PAGES[key],style="Nav.TButton",command=lambda k=key:self.show(k))
                button.pack(fill="x",pady=2)
                button.bind("<FocusIn>", reveal_focus)
                self.nav[key]=button

    def _size_canvas(self, event=None):
        self.viewport.configure(scrollregion=self.viewport.bbox("all"))

    def _scroll_target(self, event):
        widget = event.widget
        if not isinstance(widget, tk.Misc) or widget.winfo_toplevel() != self.root:
            return None
        if widget.winfo_class() in ("Treeview", "Text", "Listbox", "TCombobox", "TSpinbox"):
            return None
        target = self.nav_view if str(widget).startswith(str(self.side) + ".") else self.viewport
        return target if target.yview() != (0.0, 1.0) else None

    def _scroll_pixels(self, target, pixels):
        step = int(round(pixels))
        target.yview_scroll(step or (1 if pixels > 0 else -1), "units")

    def _scroll(self, event):
        target = self._scroll_target(event)
        delta = {4: 120, 5: -120}.get(getattr(event, "num", None), event.delta)
        if target is not None and delta:
            # Tk 9 reports 120 per wheel notch (as Tk's own widgets do: 30 px a notch);
            # older macOS Tk reports small deltas.
            self._scroll_pixels(target, -delta / 4 if abs(delta) >= 120 else -delta * 12)

    def _touchpad(self, event):
        target = self._scroll_target(event)
        if target is None:
            return
        _dx, dy = (int(v) for v in self.root.tk.splitlist(self.root.tk.call("tk::PreciseScrollDeltas", event.delta)))
        if dy:
            self._scroll_pixels(target, -dy)

    def full_screen(self):
        return bool(self.root.tk.getboolean(self.root.attributes("-fullscreen")))

    def set_full_screen(self,value):
        self.root.attributes("-fullscreen", bool(value))

    def switch_theme(self, theme=None):
        self.theme = theme or ("light" if self.theme == "dark" else "dark")
        self.theme_var.set(self.theme)
        self._style()
        self.viewport.configure(bg=self.colors["bg"])
        self.nav_view.configure(bg=self.colors["bg"])
        if "home" in self.pages:
            self.draw_overview()
        for page in self.pages.values():
            for widget in self._canvases(page):
                widget.event_generate("<<ThemeChanged>>")
        if "results" in self.pages:
            self.results_view.refresh()

    def _canvases(self, parent):
        for child in parent.winfo_children():
            if isinstance(child, tk.Canvas):
                yield child
            yield from self._canvases(child)

    @staticmethod
    def page_title(key):
        return PAGES.get(key,"Overview")

    def copy(self,text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def error(self,message):
        messagebox.showerror("Multiplex-NBS",str(message),parent=self.root)

    def _invalidate(self,*keys):
        for key in keys:
            frame = self.pages.pop(key,None)
            if frame is not None:
                frame.destroy()
            self.scroll_positions.pop(key,None)

    def _nav_state(self):
        for key,button in self.nav.items():
            disabled=(self.worker is not None or (key=="model" and self.data is None) or
                      (key=="results" and self.result is None))
            button.configure(state="disabled" if disabled else "normal",
                             style="Selected.Nav.TButton" if key==self.page else "Nav.TButton")

    def show(self,key):
        if self.worker is not None and key!="progress":
            return
        if key=="model" and self.data is None:
            key="data"
        if key=="results" and self.result is None:
            return
        previous=self.page
        if key in TOPICS and previous not in TOPICS and previous!="progress":
            self.return_page=previous
        if previous in self.pages:
            self.scroll_positions[previous]=self.viewport.yview()[0]
            self.pages[previous].pack_forget()
        # Refresh the return button's target when the reader consults help from a new step.
        if key in TOPICS:
            self._invalidate(key)
        self.page=key
        if key not in self.pages:
            frame=ttk.Frame(self.body)
            self.pages[key]=frame
            frame.pack(fill="both",expand=True)
            if key=="home":
                self._home(frame)
            elif key=="data":
                from .native_setup import data_page
                data_page(self,frame)
            elif key=="model":
                from .native_setup import model_page
                model_page(self,frame)
            elif key=="results":
                from .native_results import results_page
                self.results_view=results_page(self,frame)
            elif key=="progress":
                self._progress(frame)
            else:
                reference_page(self,frame,key)
        else:
            self.pages[key].pack(fill="both",expand=True)
        self._nav_state()
        self.root.update_idletasks()
        self._size_canvas()
        self.viewport.yview_moveto(self.scroll_positions.get(key,0.0))

    def _home(self, parent):
        head = ttk.Frame(parent)
        head.pack(fill="x", pady=(6, 40))
        title = ttk.Frame(head)
        brand = ttk.Label(title, text="Multiplex-NBS")
        brand.pack(anchor="w")
        subtitle = ttk.Label(title, text="Classic, layer-wise and multiplex network-based statistics in one place",
                             style="Subtitle.TLabel", justify="left")
        subtitle.pack(anchor="w", pady=(10, 0))
        intro = ttk.Frame(head)
        lead = ttk.Label(intro, style="Lead.TLabel", justify="left", text=(
            "Compare connectivity between groups or conditions. Edges above a threshold are grouped into "
            "connected components, and each component receives a family-wise corrected p-value, in one "
            "network or across time points or frequency bands."))
        lead.pack(anchor="w")
        actions = ttk.Frame(intro)
        actions.pack(anchor="w", pady=(24, 0))
        ttk.Button(actions, text="Start analysis  \u203a", style="Primary.TButton",
                   command=lambda: self.show("data")).pack(side="left")
        self.demo_button = ttk.Button(actions, text="Try the demo", command=lambda: self.open_demo("multiplex"))
        self.demo_button.pack(side="left", padx=(12, 0))

        plate = ttk.Frame(parent, style="Hero.TFrame", padding=(44, 34, 44, 34))
        plate.pack(fill="x")
        top = ttk.Frame(plate, style="Hero.TFrame")
        figure_title = ttk.Label(top, text="Connected components", style="HeroTitle.TLabel")
        modes = ttk.Frame(top, style="HeroSegment.TFrame", padding=1)
        for value, label in METHODS.items():
            ttk.Radiobutton(modes, text=label, value=value, variable=self.demo_mode, style="Segment.Toolbutton",
                            command=self.draw_overview).pack(side="left")
        self.figure_note = ttk.Label(plate, style="HeroNote.TLabel", justify="left")
        self.home_figure = tk.Canvas(plate, width=1, height=380, bd=0, highlightthickness=0)
        self.home_figure.bind("<Configure>", lambda _event: self.draw_overview())

        def title_size(available, largest):
            # Largest size at which the title fits; Tk clips a label that is wider than its column.
            size = largest
            while size > 30 and font.Font(family=self.family, size=size, weight="bold").measure("Multiplex-NBS") > available:
                size -= 2
            return size

        def fit(event):
            width = event.width
            lead_width = max(280, min(430, int(width * .34)))
            gap = 48
            size = title_size(width - lead_width - gap - 8, 76)
            wide = size >= 50
            if not wide:
                size = title_size(width - 8, 70)
            title.grid(row=0, column=0, sticky="sw", padx=(0, gap if wide else 0))
            intro.grid(row=0 if wide else 1, column=1 if wide else 0, sticky="sw", pady=(0 if wide else 24, 4))
            head.columnconfigure(0, weight=1)
            brand.configure(font=(self.family, size, "bold"))
            title_width = font.Font(family=self.family, size=size, weight="bold").measure("Multiplex-NBS")
            subtitle.configure(wraplength=max(260, title_width if wide else width - 12))
            lead.configure(wraplength=lead_width if wide else max(260, min(640, width - 12)))
            inner = width - 88
            side_by_side = inner >= 760
            top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 26))
            top.columnconfigure(0, weight=1)
            figure_title.grid(row=0, column=0, sticky="w")
            # The method switch sits beside the heading only when both fit.
            heading = font.Font(family=self.family, size=22, weight="bold").measure("Connected components")
            beside = inner >= heading + modes.winfo_reqwidth() + 40
            modes.grid(row=0 if beside else 1, column=1 if beside else 0, sticky="e" if beside else "w",
                       pady=(0 if beside else 14, 0))
            self.figure_note.grid(row=1, column=0, sticky="nw", padx=(0, 40 if side_by_side else 0),
                                  pady=(0, 0 if side_by_side else 20))
            self.home_figure.grid(row=1 if side_by_side else 2, column=1 if side_by_side else 0, sticky="ew")
            plate.columnconfigure(0, weight=0 if side_by_side else 1, minsize=320 if side_by_side else 0)
            plate.columnconfigure(1, weight=1 if side_by_side else 0)
            note_width = 280 if side_by_side else inner
            self.figure_note.configure(wraplength=note_width)
            figure_width = inner - (320 if side_by_side else 0)
            self.home_figure.configure(height=max(260, min(440, int(figure_width * .56))))
        parent.bind("<Configure>", fit, add=True)
        self.draw_overview()

    def draw_overview(self):
        canvas = self.home_figure
        if not canvas.winfo_exists():
            return
        c = self.colors
        for name, options in (
            ("Hero.TFrame", {"background": c["field"]}),
            ("HeroSegment.TFrame", {"background": c["plate_edge"]}),
            ("HeroTitle.TLabel", {"background": c["field"], "foreground": c["paper"], "font": (self.family, 22, "bold")}),
            ("HeroNote.TLabel", {"background": c["field"], "foreground": c["paper_muted"], "font": (self.family, 13)}),
            ("Subtitle.TLabel", {"foreground": c["muted"], "font": (self.family, 15)}),
            ("Lead.TLabel", {"foreground": c["fg"], "font": (self.family, 14)}),
        ):
            self.style.configure(name, **options)
        self.style.configure("Segment.Toolbutton", background=c["field"], foreground=c["paper"], padding=(14, 8),
                             font=(self.family, 12), relief="flat", borderwidth=0)
        self.style.map("Segment.Toolbutton",
                       background=[("selected", c["wire"]), ("active", c["plate"])],
                       foreground=[("selected", c["field"])],
                       focuscolor=[("selected", c["wire"]), ("!selected", c["field"])])
        mode = self.demo_mode.get()
        self.figure_note.configure(text=CAPTIONS[mode])
        draw_method_figure(canvas, c, self.family, mode)

    def load_data(self,data,name,mode=None):
        description=describe(data)
        self.data,self.description,self.name=data,description,str(name)
        self.result=None
        # "layerwise" is the multiplex engine with layers kept separate.
        engine = "multiplex" if mode == "layerwise" else mode
        # Multiplex-NBS is the default for layered data; researchers can choose another method on the model page.
        layered = description["layer_count"] > 1
        self.config=dict(design=description["suggested_design"] or "",inference_mode=engine or
                         ("multiplex" if layered else "classic"),
                         threshold=3.,tail="right",metric="extent",n_perm=999,alpha=.05,seed=1,method="auto",use_abs=False,
                         layer_adjacency="independent" if mode == "layerwise" else
                         ("consecutive" if layered else description["axis"]["adjacency"]))
        if self.config["inference_mode"]=="classic" and description["layer_count"]==1:
            self.config["classic_layer"]=1
        self._invalidate("data","model","results")
        self.show("data")

    def open_demo(self,mode="multiplex",kind="brain-network"):
        if self.worker is not None: return
        try:
            dataset=validate_dataset(make_brain_demo() if kind=="brain-network" else make_demo(kind))
            if kind!="brain-network":
                dataset["demo_info"]={"title":f"Simulated {kind} study","simulation_note":"All measurements, observations and effects are simulated."}
            self.load_data(dataset,"Structural brain network · simulated study" if kind=="brain-network" else f"Simulated {kind} study",mode)
            self.config["n_perm"] = 99
            if kind=="paired": self.config["design"]="paired"
            if self.config["inference_mode"]=="classic":
                self.config["classic_layer"]=min(3,self.description["layer_count"])
                self.config["metric"]="intensity"
            self.show("model")
        except (OSError,ValueError) as exc:
            self.error(exc)

    def _progress(self,parent):
        ttk.Label(parent,text="Running permutations",style="PageTitle.TLabel").pack(anchor="w")
        paragraph(parent,self.name)
        self.progress_message=ttk.Label(parent)
        self.progress_message.pack(anchor="w",pady=16)
        self.progress_bar=ttk.Progressbar(parent,maximum=self.config["n_perm"])
        self.progress_bar.pack(fill="x",pady=(4,22))
        self.cancel_button=ttk.Button(parent,text="Cancel analysis",command=self.request_cancel)
        self.cancel_button.pack(anchor="w")

    def request_cancel(self):
        self.cancel.set()
        self.cancel_button.configure(text="Cancelling…",state="disabled")

    def start(self,config):
        if self.worker is not None or self.data is None: return
        self.config=dict(config)
        data=self.data
        settings=dict(config)
        self.cancel.clear()
        self.result=None
        self._invalidate("progress","results")
        def calculate():
            last=0.
            def progress(done,total):
                nonlocal last
                if self.cancel.is_set(): raise InterruptedError()
                now=time.monotonic()
                if done==0 or done==total or now-last>=.1:
                    self.events.put(("progress",(done,total)))
                    last=now
            try:
                start=time.monotonic()
                result=run_dataset(data,settings,progress)
                result["dataset_name"]=self.name
                result["elapsed_seconds"]=round(time.monotonic()-start,3)
                self.events.put(("done",result))
            except InterruptedError:
                self.events.put(("cancelled",None))
            except Exception as exc:
                self.events.put(("error",str(exc)))
        self.worker=threading.Thread(target=calculate,daemon=True)
        self.show("progress")
        self.worker.start()
        self.root.after(40,self._poll)

    def _poll(self):
        while not self.events.empty():
            event,value=self.events.get_nowait()
            if event=="progress":
                done,total=value
                self.progress_message.configure(text=f"{done:,} of {total:,} permutations")
                self.progress_bar.configure(value=done)
            else:
                self.worker=None
                if event=="done" and not self.cancel.is_set():
                    self.result=value
                    self.show("results")
                else:
                    self.show("model")
                    if event=="error": self.error(value)
                return
        self.root.after(65,self._poll)

    def quit(self):
        if self.worker is not None:
            if not messagebox.askyesno("Quit Multiplex-NBS","Stop the current analysis and quit?",parent=self.root):
                return
            self.cancel.set()
        self.root.destroy()


def main():
    root=DesktopRoot(className="MultiplexNBS")
    NativeApp(root)
    try:
        # A normal window that fills the screen; the system buttons minimise, zoom or go full screen.
        root.wm_state("zoomed")
    except tk.TclError:
        pass
    root.mainloop()


def native_self_test(progress=lambda message: None):
    """Exercise the actual demo buttons, model forms, results, and reference pages."""
    from .native_results import TABS_SINGLE, TABS_STACK
    progress("Creating the native test window")
    root = DesktopRoot(className="MultiplexNBSTest")
    errors = []
    root.report_callback_exception = lambda kind, exc, tb: errors.append(str(exc))

    def descendants(parent):
        for widget in parent.winfo_children():
            yield widget
            yield from descendants(widget)

    try:
        app = NativeApp(root, full_screen=False)
        root.update_idletasks()
        app.error = lambda message: errors.append(str(message))
        counts = {}
        for mode in ("classic", "layerwise", "multiplex"):
            progress(f"Opening the {mode} demo")
            app.show("home")
            app.demo_mode.set(mode)
            app.draw_overview()
            if mode == "multiplex":
                app.demo_button.invoke()
            else:
                app.open_demo(mode)
            if app.page != "model":
                raise RuntimeError(f"{mode} demo did not reach its model")
            app.show("method")
            app.show(app.return_page)
            form = list(descendants(app.pages["model"]))
            run_button = next(w for w in form if isinstance(w, ttk.Button) and w["text"] == "Run permutations")
            progress(f"Running {mode} permutations")
            run_button.invoke()
            deadline = time.monotonic() + 60
            while app.worker is not None and time.monotonic() < deadline and not errors:
                root.update()
                time.sleep(.008)
            if errors or app.page != "results" or app.result is None:
                raise RuntimeError(f"{mode} desktop analysis did not complete: {errors}")
            result = app.result
            progress(f"Checking {mode} results and exports")
            engine = "multiplex" if mode == "layerwise" else mode
            separate = result["config"]["layer_adjacency"] == "independent"
            if (result["config"]["inference_mode"] != engine or (mode != "classic" and (mode == "layerwise") != separate)
                    or not result["clusters"] or len(result["null_max"]) != 99):
                raise RuntimeError(f"Unexpected {mode} inference result")
            if not result_csv(result) or not result_mat(result):
                raise RuntimeError("Empty result export")
            view = app.results_view
            if not view.component or not view.plot.find_all():
                raise RuntimeError(f"No component figure for the {mode} teaching example")
            for tab in [key for key, _label in (TABS_STACK if view.layers > 1 else TABS_SINGLE)]:
                view.tab.set(tab)
                view.change_tab()
                root.update_idletasks()
                if not view.plot.find_all():
                    raise RuntimeError(f"The {tab} figure is empty for the {mode} teaching example")
            view.alpha.set(".005")
            view.apply_cutoff()
            if view.component is not None or view.tree.get_children():
                raise RuntimeError("Significant-only view displayed a component below permutation resolution")
            view.scope.set("All observed")
            view.refresh()
            if view.component is None:
                raise RuntimeError("All observed components were hidden")
            counts[mode] = len(result["clusters"])
        progress("Opening the data page and reference pages")
        app.show("data")
        for topic in TOPICS:
            app.show(topic)
        root.update_idletasks()
        for theme in ("dark", "mono", "light"):
            app.switch_theme(theme)
            root.update_idletasks()
        forbidden = sorted(set(sys.modules) & {"multiplex_nbs.server", "multiplex_nbs.window", "webview",
                                               "webbrowser", "http.server"})
        if errors or forbidden:
            raise RuntimeError(f"Native self-test: {errors}, unintended modules: {forbidden}")
        # Tcl/Tk 9 can load its scripts from a ZIP filesystem embedded in the toolkit binary.
        from pathlib import Path
        executable = Path(sys.executable).resolve()
        bundle = executable.parents[2] if sys.platform == "darwin" else executable.parent
        toolkit_scripts = {}
        for library, script in (("tcl_library", "init.tcl"), ("tk_library", "tk.tcl")):
            path = str(root.tk.call("file", "join", root.tk.globalgetvar(library), script))
            progress(f"Checking the Tcl filesystem for {script}")
            filesystem = root.tk.splitlist(root.tk.call("file", "system", path))[0].lower()
            if not root.tk.getboolean(root.tk.call("file", "isfile", path)):
                raise RuntimeError(f"Unresolved toolkit resource: {script}")
            if filesystem not in {"native", "zipfs"}:
                raise RuntimeError(f"Unknown filesystem for {script}: {filesystem}")
            if filesystem == "native" and getattr(sys, "frozen", False) and not Path(path).resolve().is_relative_to(bundle):
                raise RuntimeError(f"The native app loaded {script} from outside its distribution.")
            toolkit_scripts[script] = "embedded ZIP filesystem" if filesystem == "zipfs" else "directory"
        return {
            "ok": True, "version": __version__, "build": __build__, "ui": "tkinter",
            "tk": str(root.tk.call("package", "provide", "Tk")),
            "tcl": str(root.tk.call("info", "patchlevel")),
            "toolkit_scripts": toolkit_scripts,
            "shape": list(app.data["W"].shape), "observed_components": counts,
            "permutations_per_mode": 99, "web_modules_loaded": False,
        }
    finally:
        progress("Closing the native test window")
        root.destroy()


if __name__ == "__main__":
    main()
