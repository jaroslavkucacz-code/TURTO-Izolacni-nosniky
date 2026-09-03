from __future__ import annotations

import ctypes
import json
import logging
import os
import subprocess
import sys
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Iterable

import tkinter as tk
from tkinter import messagebox, ttk

from catalog_engine import (
    CatalogDatabase,
    CatalogError,
    QueryResult,
    SelectionError,
    concrete_label,
    format_moment,
    format_shear,
    natural_key,
)
from project_ui import ProjectWorkspaceMixin
from autocomplete import DesignationAutocomplete
from project_model import selection_from_result

APP_NAME = "TURTO – Databáze izolačních nosníků"
APP_VERSION = "0.6.0"
CREATOR = "Vytvořil Ing. Jaroslav Kučera"


def enable_high_dpi() -> None:
    """Zapne rozumné škálování na Windows; na ostatních systémech nic nemění."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def app_root() -> Path:
    """Kořen aplikace při běhu ze zdrojů i z PyInstaller onedir balíčku."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundled_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return app_root()


def choose_data_directory(name: str) -> Path:
    """Upřednostní editovatelný adresář vedle EXE, jinak přibalená data."""
    external = app_root() / name
    if external.exists():
        return external
    return bundled_root() / name


def user_data_directory() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    result = base / "TURTO" / "Izolacni_nosniky"
    result.mkdir(parents=True, exist_ok=True)
    return result


def open_path(path: Path) -> None:
    path = path.resolve()
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("turto_izolacni_nosniky")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    handler = RotatingFileHandler(
        user_data_directory() / "app.log",
        maxBytes=500_000,
        backupCount=2,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    return logger


LOGGER = setup_logging()


LIGHT = {
    "bg": "#F3F6F9",
    "panel": "#FFFFFF",
    "panel_alt": "#F8FAFC",
    "header": "#17324D",
    "header_text": "#FFFFFF",
    "text": "#172230",
    "muted": "#5C6878",
    "border": "#D8E0E8",
    "accent": "#0E6E8E",
    "accent_hover": "#0A5D79",
    "accent_soft": "#E7F3F7",
    "warning_bg": "#FFF7E6",
    "warning_text": "#6B4D12",
    "metric_bg": "#EFF7FA",
    "metric_value": "#0A5D79",
    "success": "#2C7A54",
    "danger": "#A63D40",
    "select": "#DCEEF4",
}

DARK = {
    "bg": "#151B22",
    "panel": "#202832",
    "panel_alt": "#26303B",
    "header": "#101820",
    "header_text": "#F4F7FA",
    "text": "#EFF3F7",
    "muted": "#AAB5C1",
    "border": "#3B4652",
    "accent": "#55AFCC",
    "accent_hover": "#73C2DB",
    "accent_soft": "#233D47",
    "warning_bg": "#42361F",
    "warning_text": "#F6D995",
    "metric_bg": "#203A44",
    "metric_value": "#79D0EA",
    "success": "#7BC7A0",
    "danger": "#F19A9C",
    "select": "#345463",
}


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self.window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, _event: tk.Event[Any] | None = None) -> None:
        if self.window or not self.text:
            return
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 7
        top = tk.Toplevel(self.widget)
        top.wm_overrideredirect(True)
        top.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            top,
            text=self.text,
            justify="left",
            relief="solid",
            borderwidth=1,
            font=("Calibri", 9),
            padx=7,
            pady=4,
            background="#FFFBEA",
            foreground="#2A2A2A",
        )
        label.pack()
        self.window = top

    def _hide(self, _event: tk.Event[Any] | None = None) -> None:
        if self.window is not None:
            self.window.destroy()
            self.window = None


class HeightTableDialog(tk.Toplevel):
    """Přehled všech katalogových variant pro právě zvolenou hlavní třídu."""
    def __init__(self, parent: "ThermalConnectorApp", family: dict[str, Any], moment_class: str,
                 concrete_min: str, current_shear: str, current_cover: str, current_height: str):
        super().__init__(parent)
        self.parent_app=parent; self.family=family; self.moment_class=moment_class; self.concrete_min=concrete_min
        self.title(f"Katalogové varianty – {family['model']} typ {family['type']} {moment_class}")
        self.geometry("980x600"); self.minsize(760,440); self.transient(parent); self.configure(background=parent.colors["bg"])
        outer=ttk.Frame(self,style="App.TFrame",padding=18); outer.pack(fill="both",expand=True); outer.columnconfigure(0,weight=1); outer.rowconfigure(2,weight=1)
        ttk.Label(outer,text=f"{family['manufacturer']} {family.get('brand','')} {family['model']} typ {family['type']} – {moment_class}, beton {concrete_label(concrete_min)}",style="DialogTitle.TLabel",wraplength=900).grid(row=0,column=0,sticky="ew")
        ttk.Label(outer,text="Všechny dostupné kombinace vedlejší třídy, varianty a rozměru pro zvolenou hlavní třídu. Dvojklikem kombinaci použijete.",style="Muted.TLabel",wraplength=900).grid(row=1,column=0,sticky="ew",pady=(3,12))
        frame=ttk.Frame(outer,style="Card.TFrame",padding=1); frame.grid(row=2,column=0,sticky="nsew"); frame.columnconfigure(0,weight=1); frame.rowconfigure(0,weight=1)
        self.tree=ttk.Treeview(frame,columns=("secondary","variant","dimension","values","pages"),show="headings",selectmode="browse",style="Data.Treeview")
        headings=("Třída / varianta 2","Krytí / varianta","Rozměr","Statické hodnoty","Str.")
        widths=(150,190,110,430,70)
        for c,h,w in zip(self.tree["columns"],headings,widths): self.tree.heading(c,text=h); self.tree.column(c,width=w,anchor="w" if c=="values" else "center",stretch=c=="values")
        y=ttk.Scrollbar(frame,orient="vertical",command=self.tree.yview); self.tree.configure(yscrollcommand=y.set); self.tree.grid(row=0,column=0,sticky="nsew"); y.grid(row=0,column=1,sticky="ns")
        self._records={}; current_iid=None
        records=[r for r in family.get("records",[]) if str(r.get("moment_class"))==str(moment_class) and str(r.get("concrete_min"))==str(concrete_min)]
        records.sort(key=lambda r:(natural_key(str(r.get("shear_class",""))),natural_key(str(r.get("cover",""))),natural_key(str(r.get("height_mm","")))))
        for i,r in enumerate(records):
            iid=f"r{i}"; self._records[iid]=r
            values="; ".join(__import__('catalog_engine').format_result(x) for x in r.get("results",[]))
            self.tree.insert("","end",iid=iid,values=(r.get("shear_class","—"),r.get("cover","—"),r.get("height_mm","—"),values,", ".join(map(str,r.get("source_pages",[])))))
            if str(r.get("shear_class"))==str(current_shear) and str(r.get("cover"))==str(current_cover) and str(r.get("height_mm"))==str(current_height): current_iid=iid
        if current_iid: self.tree.selection_set(current_iid); self.tree.focus(current_iid); self.tree.see(current_iid)
        self.tree.bind("<Double-1>",self._use_selected); self.tree.bind("<Return>",self._use_selected)
        actions=ttk.Frame(outer,style="App.TFrame"); actions.grid(row=3,column=0,sticky="ew",pady=(14,0)); actions.columnconfigure(0,weight=1)
        ttk.Button(actions,text="Zkopírovat tabulku",command=self._copy_table).grid(row=0,column=0,sticky="w")
        ttk.Button(actions,text="Použít kombinaci",style="Accent.TButton",command=self._use_selected).grid(row=0,column=1,padx=(8,0)); ttk.Button(actions,text="Zavřít",command=self.destroy).grid(row=0,column=2,padx=(8,0))
    def _use_selected(self,_event=None):
        sel=self.tree.selection()
        if not sel:return
        r=self._records[sel[0]]; app=self.parent_app
        app._updating=True
        try:
            app.shear_var.set(str(r["shear_class"])); app._cascade_from_shear(preferred_cover=str(r["cover"])); app.cover_var.set(str(r["cover"])); app._cascade_from_cover(str(r["height_mm"])); app.height_var.set(str(r["height_mm"]))
        finally: app._updating=False
        app.refresh_result(); self.destroy()
    def _copy_table(self):
        lines=["Třída 2\tVarianta\tRozměr\tStatické hodnoty\tStrana"]
        for iid in self.tree.get_children(""): lines.append("\t".join(str(v) for v in self.tree.item(iid,"values")))
        self.clipboard_clear(); self.clipboard_append("\n".join(lines))


class ThermalConnectorApp(ProjectWorkspaceMixin, tk.Tk):
    def __init__(self):
        super().__init__()
        self.root_dir = app_root()
        self.catalog_dir = choose_data_directory("catalogs")
        self.source_dir = choose_data_directory("sources")
        self.asset_dir = choose_data_directory("assets")
        self.settings_path = user_data_directory() / "settings.json"
        self.settings = self._load_settings()
        self.theme_name = str(self.settings.get("theme", "light"))
        if self.theme_name not in {"light", "dark"}:
            self.theme_name = "light"
        self.colors = LIGHT if self.theme_name == "light" else DARK
        self.database = CatalogDatabase(self.catalog_dir)
        self.base_window_title = f"{APP_NAME} {APP_VERSION}"
        self._init_project_workspace()
        self.current_result: QueryResult | None = None
        self.catalog_display_to_id: dict[str, str] = {}
        self.catalog_id_to_display: dict[str, str] = {}
        self._updating = False
        self._icon_image: tk.PhotoImage | None = None

        self.title(self.base_window_title)
        self.minsize(1180, 720)
        geometry = self.settings.get("geometry")
        self.geometry(str(geometry) if geometry else "1480x900")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.configure(background=self.colors["bg"])

        self._set_icon()
        self._configure_fonts()
        self.style = ttk.Style(self)
        self._configure_theme()
        self._create_variables()
        self._build_ui()
        self._populate_initial_data()
        self._restore_selections()
        self.refresh_result()
        self.finalize_project_workspace()
        self.after(100, self._apply_initial_sash)
        LOGGER.info("Aplikace spuštěna, katalogy=%s, families=%s", len(self.database.catalogs), len(self.database.families))

    # ---------- základní nastavení ----------

    def _set_icon(self) -> None:
        icon_path = self.asset_dir / "app_icon.png"
        if not icon_path.exists():
            return
        try:
            self._icon_image = tk.PhotoImage(file=str(icon_path))
            self.iconphoto(True, self._icon_image)
        except Exception as exc:
            LOGGER.warning("Ikonu se nepodařilo načíst: %s", exc)

    def _configure_fonts(self) -> None:
        try:
            import tkinter.font as tkfont

            for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
                font = tkfont.nametofont(name)
                font.configure(family="Calibri", size=10)
        except Exception as exc:
            LOGGER.warning("Výchozí fonty se nepodařilo nastavit: %s", exc)

    def _configure_theme(self) -> None:
        c = self.colors
        self.style.theme_use("clam")

        self.style.configure("App.TFrame", background=c["bg"])
        self.style.configure("Card.TFrame", background=c["panel"], relief="flat")
        self.style.configure("CardAlt.TFrame", background=c["panel_alt"], relief="flat")
        self.style.configure("Header.TFrame", background=c["header"])
        self.style.configure("Metric.TFrame", background=c["metric_bg"], relief="flat")
        self.style.configure("Warning.TFrame", background=c["warning_bg"], relief="flat")

        self.style.configure("TLabel", background=c["bg"], foreground=c["text"], font=("Calibri", 10))
        self.style.configure("Card.TLabel", background=c["panel"], foreground=c["text"], font=("Calibri", 10))
        self.style.configure("CardAlt.TLabel", background=c["panel_alt"], foreground=c["text"], font=("Calibri", 10))
        self.style.configure("HeaderTitle.TLabel", background=c["header"], foreground=c["header_text"], font=("Calibri", 17, "bold"))
        self.style.configure("HeaderSubtitle.TLabel", background=c["header"], foreground="#D7E3ED", font=("Calibri", 10))
        self.style.configure("Section.TLabel", background=c["panel"], foreground=c["text"], font=("Calibri", 12, "bold"))
        self.style.configure("SectionApp.TLabel", background=c["bg"], foreground=c["text"], font=("Calibri", 12, "bold"))
        self.style.configure("DialogTitle.TLabel", background=c["bg"], foreground=c["text"], font=("Calibri", 13, "bold"))
        self.style.configure("Designation.TLabel", background=c["panel"], foreground=c["text"], font=("Calibri", 15, "bold"))
        self.style.configure("Muted.TLabel", background=c["bg"], foreground=c["muted"], font=("Calibri", 9))
        self.style.configure("MutedCard.TLabel", background=c["panel"], foreground=c["muted"], font=("Calibri", 9))
        self.style.configure("SmallCard.TLabel", background=c["panel"], foreground=c["muted"], font=("Calibri", 9))
        self.style.configure("MetricTitle.TLabel", background=c["metric_bg"], foreground=c["muted"], font=("Calibri", 10, "bold"))
        self.style.configure("MetricValue.TLabel", background=c["metric_bg"], foreground=c["metric_value"], font=("Calibri", 23, "bold"))
        self.style.configure("MetricInfo.TLabel", background=c["metric_bg"], foreground=c["muted"], font=("Calibri", 9))
        self.style.configure("Warning.TLabel", background=c["warning_bg"], foreground=c["warning_text"], font=("Calibri", 9))
        self.style.configure("Status.TLabel", background=c["header"], foreground="#D7E3ED", font=("Calibri", 9))
        self.style.configure("Good.TLabel", background=c["panel"], foreground=c["success"], font=("Calibri", 9, "bold"))
        self.style.configure("Bad.TLabel", background=c["panel"], foreground=c["danger"], font=("Calibri", 9, "bold"))

        self.style.configure(
            "TButton",
            font=("Calibri", 10),
            padding=(10, 7),
            background=c["panel_alt"],
            foreground=c["text"],
            bordercolor=c["border"],
            focusthickness=1,
            focuscolor=c["accent"],
        )
        self.style.map(
            "TButton",
            background=[("active", c["select"]), ("pressed", c["accent_soft"])],
            foreground=[("disabled", c["muted"])],
        )
        self.style.configure(
            "Accent.TButton",
            font=("Calibri", 10, "bold"),
            padding=(12, 8),
            background=c["accent"],
            foreground="#FFFFFF" if self.theme_name == "light" else "#0D171C",
            bordercolor=c["accent"],
        )
        self.style.map(
            "Accent.TButton",
            background=[("active", c["accent_hover"]), ("pressed", c["accent_hover"])],
        )
        self.style.configure(
            "Header.TButton",
            font=("Calibri", 10),
            padding=(10, 7),
            background=c["header"],
            foreground=c["header_text"],
            bordercolor="#496176",
        )
        self.style.map("Header.TButton", background=[("active", "#274762")])

        self.style.configure(
            "TEntry",
            fieldbackground=c["panel_alt"],
            foreground=c["text"],
            insertcolor=c["text"],
            bordercolor=c["border"],
            lightcolor=c["border"],
            darkcolor=c["border"],
            padding=7,
            font=("Calibri", 10),
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=c["panel_alt"],
            background=c["panel_alt"],
            foreground=c["text"],
            arrowcolor=c["text"],
            bordercolor=c["border"],
            lightcolor=c["border"],
            darkcolor=c["border"],
            padding=6,
            font=("Calibri", 10),
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", c["panel_alt"])],
            foreground=[("readonly", c["text"])],
            selectbackground=[("readonly", c["panel_alt"])],
            selectforeground=[("readonly", c["text"])],
        )

        self.option_add("*TCombobox*Listbox.font", ("Calibri", 10))
        self.option_add("*TCombobox*Listbox.background", c["panel"])
        self.option_add("*TCombobox*Listbox.foreground", c["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", c["accent"])
        self.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")

        self.style.configure(
            "Data.Treeview",
            font=("Calibri", 10),
            rowheight=29,
            background=c["panel"],
            fieldbackground=c["panel"],
            foreground=c["text"],
            bordercolor=c["border"],
        )
        self.style.map("Data.Treeview", background=[("selected", c["accent"])] , foreground=[("selected", "#FFFFFF")])
        self.style.configure(
            "Data.Treeview.Heading",
            font=("Calibri", 10, "bold"),
            background=c["panel_alt"],
            foreground=c["text"],
            relief="flat",
            padding=(6, 7),
        )
        self.style.map("Data.Treeview.Heading", background=[("active", c["select"])])

        self.style.configure("TPanedwindow", background=c["bg"])
        self.style.configure("TSeparator", background=c["border"])
        self._configure_project_styles()

    def _create_variables(self) -> None:
        self.quick_var = tk.StringVar()
        self.manufacturer_var = tk.StringVar()
        self.catalog_var = tk.StringVar()
        self.model_var = tk.StringVar()
        self.type_var = tk.StringVar()
        self.generation_var = tk.StringVar()
        self.moment_var = tk.StringVar()
        self.shear_var = tk.StringVar()
        self.concrete_var = tk.StringVar()
        self.cover_var = tk.StringVar()
        self.height_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Připraveno.")
        self.catalog_badge_var = tk.StringVar()
        self.designation_var = tk.StringVar(value="—")
        self.moment_value_var = tk.StringVar(value="—")
        self.shear_value_var = tk.StringVar(value="—")
        self.moment_info_var = tk.StringVar(value="mRd,y podle zvolené výšky a krytí")
        self.shear_info_var = tk.StringVar(value="vRd,z podle zvolené smykové třídy")
        self.detail_var = tk.StringVar(value="—")
        self.source_var = tk.StringVar(value="—")
        self.integrity_var = tk.StringVar(value="Databáze nebyla zkontrolována")
        self._create_project_variables()

    # ---------- sestavení UI ----------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_header()
        self._build_body()
        self._build_statusbar()

    def _build_header(self) -> None:
        header = ttk.Frame(self, style="Header.TFrame", padding=(22, 14))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        if self._icon_image is not None:
            icon = ttk.Label(header, image=self._icon_image, style="HeaderSubtitle.TLabel")
            icon.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 14))

        ttk.Label(header, text="TURTO | Databáze izolačních nosníků", style="HeaderTitle.TLabel").grid(
            row=0, column=1, sticky="w"
        )
        ttk.Label(
            header,
            text=f"Projektový soupis a rychlé vyhledání statických hodnot podle výrobce, generace a úplného typu • {CREATOR}",
            style="HeaderSubtitle.TLabel",
        ).grid(row=1, column=1, sticky="w", pady=(2, 0))

        theme_text = "Světlý režim" if self.theme_name == "dark" else "Tmavý režim"
        self.theme_button = ttk.Button(header, text=theme_text, style="Header.TButton", command=self.toggle_theme)
        self.theme_button.grid(row=0, column=2, rowspan=2, padx=(8, 0))
        folder_button = ttk.Button(header, text="Složka databáze", style="Header.TButton", command=self.open_catalog_folder)
        folder_button.grid(row=0, column=3, rowspan=2, padx=(8, 0))
        Tooltip(folder_button, "Otevře adresář s katalogovými daty JSON. Nová vydání se přidávají jako samostatné soubory.")
        check_button = ttk.Button(header, text="Kontrola databáze", style="Header.TButton", command=self.show_integrity_report)
        check_button.grid(row=0, column=4, rowspan=2, padx=(8, 0))
        Tooltip(check_button, "Zkontroluje duplicity, formát a návaznost momentových a smykových záznamů.")

    def _build_body(self) -> None:
        body = ttk.Frame(self, style="App.TFrame", padding=(18, 12, 18, 12))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.main_notebook = ttk.Notebook(body, style="Workspace.TNotebook")
        self.main_notebook.grid(row=0, column=0, sticky="nsew")

        self.project_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))
        self.lookup_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))
        self.main_notebook.add(self.project_tab, text="Projektové řádky")
        self.main_notebook.add(self.lookup_tab, text="Databáze / detail nosníku")

        self._build_project_tab(self.project_tab)
        self._build_lookup_body(self.lookup_tab)
        self.main_notebook.select(self.project_tab)

    def _build_lookup_body(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        self.paned = ttk.Panedwindow(parent, orient="horizontal")
        self.paned.grid(row=0, column=0, sticky="nsew")

        left = ttk.Frame(self.paned, style="Card.TFrame", padding=18, width=390)
        right = ttk.Frame(self.paned, style="App.TFrame", padding=(14, 0, 0, 0))
        self.paned.add(left, weight=0)
        self.paned.add(right, weight=1)
        self.left_panel = left
        self.right_panel = right

        self._build_controls(left)
        self._build_results(right)

    def _build_controls(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        ttk.Label(parent, text="Rychlé načtení označení", style="Section.TLabel").grid(row=0, column=0, sticky="ew")
        ttk.Label(
            parent,
            text="Pište i neúplně – např. „xt kl m8 v2 220“, „isopro aipq 60“, „vm 130“ nebo „mxl50 v2 c35 h220“. Nabídka se průběžně zpřesňuje.",
            style="MutedCard.TLabel",
        ).grid(row=1, column=0, sticky="ew", pady=(2, 8))

        quick = ttk.Frame(parent, style="Card.TFrame")
        quick.grid(row=2, column=0, sticky="ew")
        quick.columnconfigure(0, weight=1)
        self.quick_entry = ttk.Entry(quick, textvariable=self.quick_var)
        self.quick_entry.grid(row=0, column=0, sticky="ew")
        self.quick_entry.bind("<Control-a>", lambda e: (self.quick_entry.selection_range(0, "end"), "break")[-1])
        ttk.Button(quick, text="Načíst", style="Accent.TButton", command=self.apply_quick_designation).grid(
            row=0, column=1, padx=(8, 0)
        )
        self.lookup_autocomplete = DesignationAutocomplete(
            entry=self.quick_entry,
            variable=self.quick_var,
            database=self.database,
            colors=self.colors,
            submit_callback=self.apply_quick_designation,
            on_choose=self._on_lookup_suggestion_chosen,
            preferred_catalog_getter=self._autocomplete_preferred_catalog,
            limit=10,
        )

        ttk.Separator(parent).grid(row=3, column=0, sticky="ew", pady=17)
        ttk.Label(parent, text="Výběr prvku", style="Section.TLabel").grid(row=4, column=0, sticky="ew", pady=(0, 10))

        fields = ttk.Frame(parent, style="Card.TFrame")
        fields.grid(row=5, column=0, sticky="ew")
        fields.columnconfigure(1, weight=1)
        self.combos: dict[str, ttk.Combobox] = {}

        def add_combo(row: int, key: str, label: str, variable: tk.StringVar, callback: Callable[..., None]) -> None:
            ttk.Label(fields, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
            combo = ttk.Combobox(fields, textvariable=variable, state="readonly", width=24)
            combo.grid(row=row, column=1, sticky="ew", pady=4)
            combo.bind("<<ComboboxSelected>>", callback)
            self.combos[key] = combo

        add_combo(0, "manufacturer", "Výrobce", self.manufacturer_var, self.on_manufacturer_changed)
        add_combo(1, "catalog", "Vydání katalogu", self.catalog_var, self.on_catalog_changed)
        add_combo(2, "model", "Řada", self.model_var, self.on_model_changed)
        add_combo(3, "type", "Typ", self.type_var, self.on_type_changed)
        add_combo(4, "generation", "Generace", self.generation_var, self.on_generation_changed)
        add_combo(5, "moment", "Hlavní třída / varianta", self.moment_var, self.on_moment_changed)
        add_combo(6, "shear", "Vedlejší třída / varianta", self.shear_var, self.on_shear_changed)
        add_combo(7, "concrete", "Min. třída betonu", self.concrete_var, self.on_concrete_changed)
        add_combo(8, "cover", "Krytí / varianta", self.cover_var, self.on_cover_changed)
        add_combo(9, "height", "Výška / rozměr", self.height_var, self.on_height_changed)

        controls = ttk.Frame(parent, style="Card.TFrame")
        controls.grid(row=6, column=0, sticky="ew", pady=(16, 0))
        controls.columnconfigure(0, weight=1)
        ttk.Button(controls, text="Výchozí výběr", command=self.reset_selection).grid(row=0, column=0, sticky="w")
        self.height_table_button = ttk.Button(controls, text="Tabulka výšek", command=self.show_height_table)
        self.height_table_button.grid(row=0, column=1, padx=(8, 0))


    def _build_results(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)

        catalog_card = ttk.Frame(parent, style="Card.TFrame", padding=(18, 12))
        catalog_card.grid(row=0, column=0, sticky="ew")
        catalog_card.columnconfigure(0, weight=1)
        ttk.Label(catalog_card, textvariable=self.catalog_badge_var, style="SmallCard.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(catalog_card, textvariable=self.source_var, style="SmallCard.TLabel").grid(row=0, column=1, sticky="e")

        designation_card = ttk.Frame(parent, style="Card.TFrame", padding=18)
        designation_card.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        designation_card.columnconfigure(0, weight=1)
        ttk.Label(designation_card, text="Vybrané označení", style="MutedCard.TLabel").grid(row=0, column=0, sticky="w")
        self.designation_label = ttk.Label(
            designation_card,
            textvariable=self.designation_var,
            style="Designation.TLabel",
            wraplength=760,
            justify="left",
        )
        self.designation_label.grid(row=1, column=0, sticky="ew", pady=(4, 10))
        actions = ttk.Frame(designation_card, style="Card.TFrame")
        actions.grid(row=2, column=0, sticky="ew")
        self.project_detail_button = ttk.Button(
            actions,
            textvariable=self.project_detail_action_var,
            style="Accent.TButton",
            command=self.add_or_update_project_from_lookup,
        )
        self.project_detail_button.pack(side="left")
        self.cancel_project_edit_button = ttk.Button(
            actions,
            text="Zrušit úpravu řádku",
            command=self.cancel_project_row_edit,
            state="disabled",
        )
        self.cancel_project_edit_button.pack(side="left", padx=(8, 0))
        ttk.Label(actions, textvariable=self.project_edit_info_var, style="MutedCard.TLabel").pack(
            side="left", padx=(10, 0)
        )
        self.copy_button = ttk.Button(actions, text="Kopírovat hodnoty", command=self.copy_result)
        self.copy_button.pack(side="left", padx=(16, 0))
        self.copy_designation_button = ttk.Button(actions, text="Kopírovat označení", command=self.copy_designation)
        self.copy_designation_button.pack(side="left", padx=(8, 0))
        self.open_pdf_button = ttk.Button(actions, text="Otevřít zdrojovou stranu PDF", command=self.open_current_source)
        self.open_pdf_button.pack(side="left", padx=(8, 0))

        metrics = ttk.Frame(parent, style="App.TFrame")
        metrics.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        metrics.columnconfigure(0, weight=1)
        metrics.columnconfigure(1, weight=1)

        moment_card = ttk.Frame(metrics, style="Metric.TFrame", padding=18)
        moment_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ttk.Label(moment_card, text="MOMENT / HLAVNÍ HODNOTA", style="MetricTitle.TLabel").pack(anchor="w")
        ttk.Label(moment_card, textvariable=self.moment_value_var, style="MetricValue.TLabel").pack(anchor="w", pady=(4, 2))
        ttk.Label(moment_card, textvariable=self.moment_info_var, style="MetricInfo.TLabel").pack(anchor="w")

        shear_card = ttk.Frame(metrics, style="Metric.TFrame", padding=18)
        shear_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ttk.Label(shear_card, text="SMYK / SÍLA", style="MetricTitle.TLabel").pack(anchor="w")
        ttk.Label(shear_card, textvariable=self.shear_value_var, style="MetricValue.TLabel").pack(anchor="w", pady=(4, 2))
        ttk.Label(shear_card, textvariable=self.shear_info_var, style="MetricInfo.TLabel").pack(anchor="w")


        lower = ttk.Frame(parent, style="App.TFrame")
        lower.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        lower.columnconfigure(0, weight=3)
        lower.columnconfigure(1, weight=2)
        lower.rowconfigure(0, weight=1)

        detail_card = ttk.Frame(lower, style="Card.TFrame", padding=18)
        detail_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        detail_card.columnconfigure(0, weight=1)
        ttk.Label(detail_card, text="Podrobnosti výběru", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            detail_card,
            textvariable=self.detail_var,
            style="Card.TLabel",
            justify="left",
            wraplength=520,
        ).grid(row=1, column=0, sticky="nw", pady=(10, 0))

        warning = ttk.Frame(detail_card, style="Warning.TFrame", padding=12)
        warning.grid(row=2, column=0, sticky="ew", pady=(18, 0))
        ttk.Label(
            warning,
            text="Upozornění: Program přepisuje tabulkové hodnoty z konkrétního vydání katalogu. Nenahrazuje úplné statické posouzení, kontrolu statického systému ani ověření aktuálních technických informací výrobce.",
            style="Warning.TLabel",
            wraplength=450,
            justify="left",
        ).pack(anchor="w")

        shear_list_card = ttk.Frame(lower, style="Card.TFrame", padding=18)
        shear_list_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        shear_list_card.columnconfigure(0, weight=1)
        shear_list_card.rowconfigure(2, weight=1)
        ttk.Label(shear_list_card, text="Dostupné vedlejší varianty", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            shear_list_card,
            text="Kliknutím na řádek změníte vedlejší třídu / variantu.",
            style="MutedCard.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 8))

        tree_frame = ttk.Frame(shear_list_card, style="Card.TFrame")
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.shear_tree = ttk.Treeview(
            tree_frame,
            columns=("class", "value"),
            show="headings",
            selectmode="browse",
            height=7,
            style="Data.Treeview",
        )
        self.shear_tree.heading("class", text="Třída")
        self.shear_tree.heading("value", text="Katalogová hodnota")
        self.shear_tree.column("class", width=58, anchor="center", stretch=False)
        self.shear_tree.column("value", width=165, anchor="center")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.shear_tree.yview)
        self.shear_tree.configure(yscrollcommand=scrollbar.set)
        self.shear_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.shear_tree.bind("<<TreeviewSelect>>", self.on_shear_tree_selected)

    def _build_statusbar(self) -> None:
        bar = ttk.Frame(self, style="Header.TFrame", padding=(18, 6))
        bar.grid(row=2, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)
        ttk.Label(bar, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(bar, text="Aktualizace", command=self._check_updates).grid(row=0, column=1, padx=(12, 12))
        errors, warnings, stats = self.database.validation_report()
        right = (
            f"v{APP_VERSION}  •  {stats['catalogs']} katalogy  •  {stats['families']} produktových řad  •  {stats.get('records',0)} kombinací"
        )
        ttk.Label(bar, text=right, style="Status.TLabel").grid(row=0, column=2, sticky="e")
        self._update_integrity_summary(errors, warnings, stats)


    def _check_updates(self) -> None:
        try:
            from updater import check_and_update
            check_and_update(self, APP_VERSION)
        except Exception as exc:
            messagebox.showerror("Aktualizace", f"Kontrolu aktualizace se nepodařilo spustit:\n{exc}")

    def _apply_initial_sash(self) -> None:
        try:
            self.paned.sashpos(0, 405)
        except Exception:
            pass

    # ---------- práce s daty a kaskádami ----------

    @staticmethod
    def _set_combo_values(combo: ttk.Combobox, variable: tk.StringVar, values: Iterable[Any], preferred: str | None = None) -> None:
        text_values = [str(value) for value in values]
        combo.configure(values=text_values)
        if preferred is not None and preferred in text_values:
            variable.set(preferred)
        elif variable.get() in text_values:
            pass
        elif text_values:
            variable.set(text_values[0])
        else:
            variable.set("")

    def _populate_initial_data(self) -> None:
        self._updating = True
        try:
            self._set_combo_values(
                self.combos["manufacturer"],
                self.manufacturer_var,
                self.database.manufacturers(),
                "Schöck",
            )
            self._cascade_from_manufacturer()
        finally:
            self._updating = False

    def current_catalog_id(self) -> str:
        display = self.catalog_var.get()
        catalog_id = self.catalog_display_to_id.get(display)
        if not catalog_id:
            raise SelectionError("Není vybráno platné vydání katalogu.")
        return catalog_id

    def current_family(self) -> dict[str, Any]:
        return self.database.get_family(
            self.current_catalog_id(),
            self.manufacturer_var.get(),
            self.model_var.get(),
            self.type_var.get(),
            self.generation_var.get(),
        )

    def _cascade_from_manufacturer(self, preferred_catalog_id: str | None = None) -> None:
        manufacturer = self.manufacturer_var.get()
        catalogs = self.database.catalogs_for(manufacturer)
        self.catalog_display_to_id.clear()
        self.catalog_id_to_display.clear()
        displays: list[str] = []
        newest_id = self.database.newest_catalog_id(manufacturer)
        for catalog in catalogs:
            suffix = " • nejnovější" if str(catalog["id"]) == newest_id else ""
            display = f"{catalog['edition']} – {catalog['publication_label']}{suffix}"
            self.catalog_display_to_id[display] = str(catalog["id"])
            self.catalog_id_to_display[str(catalog["id"])] = display
            displays.append(display)
        preferred_display = self.catalog_id_to_display.get(preferred_catalog_id or "")
        self._set_combo_values(self.combos["catalog"], self.catalog_var, displays, preferred_display)
        self._cascade_from_catalog()

    def _cascade_from_catalog(self, preferred_model: str | None = None) -> None:
        catalog_id = self.current_catalog_id() if self.catalog_var.get() else ""
        values = self.database.models(catalog_id, self.manufacturer_var.get()) if catalog_id else []
        self._set_combo_values(self.combos["model"], self.model_var, values, preferred_model)
        self._cascade_from_model()

    def _cascade_from_model(self, preferred_type: str | None = None) -> None:
        try:
            values = self.database.types(self.current_catalog_id(), self.manufacturer_var.get(), self.model_var.get())
        except SelectionError:
            values = []
        self._set_combo_values(self.combos["type"], self.type_var, values, preferred_type)
        self._cascade_from_type()

    def _cascade_from_type(self, preferred_generation: str | None = None) -> None:
        try:
            values = self.database.generations(
                self.current_catalog_id(),
                self.manufacturer_var.get(),
                self.model_var.get(),
                self.type_var.get(),
            )
        except SelectionError:
            values = []
        self._set_combo_values(self.combos["generation"], self.generation_var, values, preferred_generation)
        self._cascade_from_generation()

    def _cascade_from_generation(self, preferred_moment: str | None = None) -> None:
        try:
            family = self.current_family()
            values = self.database.moment_classes(family)
        except (SelectionError, KeyError):
            values = []
        self._set_combo_values(self.combos["moment"], self.moment_var, values, preferred_moment)
        self._cascade_from_moment()

    def _cascade_from_moment(self, preferred_concrete: str | None = None, preferred_shear: str | None = None) -> None:
        try:
            family = self.current_family()
            concrete_values = self.database.concrete_classes(family, self.moment_var.get())
        except (SelectionError, KeyError):
            concrete_values = []
        self._set_combo_values(self.combos["concrete"], self.concrete_var, concrete_values, preferred_concrete)
        self._cascade_from_concrete(preferred_shear=preferred_shear)

    def _cascade_from_concrete(self, preferred_shear: str | None = None, preferred_cover: str | None = None) -> None:
        try:
            family=self.current_family(); shear_values=self.database.shear_classes(family,self.moment_var.get(),self.concrete_var.get())
        except (SelectionError,KeyError): shear_values=[]
        self._set_combo_values(self.combos["shear"],self.shear_var,shear_values,preferred_shear)
        self._cascade_from_shear(preferred_cover=preferred_cover)

    def _cascade_from_shear(self, preferred_cover: str | None = None) -> None:
        try:
            family=self.current_family(); cover_values=self.database.covers(family,self.moment_var.get(),self.concrete_var.get(),self.shear_var.get())
        except (SelectionError,KeyError): cover_values=[]
        self._set_combo_values(self.combos["cover"],self.cover_var,cover_values,preferred_cover)
        self._cascade_from_cover()

    def _cascade_from_cover(self, preferred_height: int | str | None = None) -> None:
        try:
            family=self.current_family(); heights=self.database.heights(family,self.moment_var.get(),self.concrete_var.get(),self.cover_var.get(),self.shear_var.get())
        except (SelectionError,KeyError): heights=[]
        preferred=str(preferred_height) if preferred_height is not None else None
        self._set_combo_values(self.combos["height"],self.height_var,heights,preferred)

    # ---------- události komboboxů ----------

    def _run_cascade(self, function: Callable[[], None]) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            function()
        finally:
            self._updating = False
        self.refresh_result()

    def on_manufacturer_changed(self, _event: tk.Event[Any] | None = None) -> None:
        self._run_cascade(self._cascade_from_manufacturer)

    def on_catalog_changed(self, _event: tk.Event[Any] | None = None) -> None:
        self._run_cascade(self._cascade_from_catalog)

    def on_model_changed(self, _event: tk.Event[Any] | None = None) -> None:
        self._run_cascade(self._cascade_from_model)

    def on_type_changed(self, _event: tk.Event[Any] | None = None) -> None:
        self._run_cascade(self._cascade_from_type)

    def on_generation_changed(self, _event: tk.Event[Any] | None = None) -> None:
        self._run_cascade(self._cascade_from_generation)

    def on_moment_changed(self, _event: tk.Event[Any] | None = None) -> None:
        self._run_cascade(self._cascade_from_moment)

    def on_shear_changed(self, _event: tk.Event[Any] | None = None) -> None:
        self._run_cascade(self._cascade_from_shear)

    def on_concrete_changed(self, _event: tk.Event[Any] | None = None) -> None:
        self._run_cascade(self._cascade_from_concrete)

    def on_cover_changed(self, _event: tk.Event[Any] | None = None) -> None:
        self._run_cascade(self._cascade_from_cover)

    def on_height_changed(self, _event: tk.Event[Any] | None = None) -> None:
        if not self._updating:
            self.refresh_result()

    # ---------- výsledek ----------

    def refresh_result(self) -> None:
        try:
            height=self.height_var.get()
            result=self.database.query(catalog_id=self.current_catalog_id(),manufacturer=self.manufacturer_var.get(),model=self.model_var.get(),type_name=self.type_var.get(),generation=self.generation_var.get(),moment_class=self.moment_var.get(),concrete_min=self.concrete_var.get(),shear_class=self.shear_var.get(),cover=self.cover_var.get(),height_mm=height)
        except (SelectionError,KeyError) as exc:
            self.current_result=None
            if hasattr(self,"project_detail_button"): self.project_detail_button.configure(state="disabled")
            self.designation_var.set("Výběr není úplný"); self.moment_value_var.set("—"); self.shear_value_var.set("—"); self.detail_var.set(str(exc)); self.source_var.set("—"); self.catalog_badge_var.set("—"); self._fill_shear_tree(None); return
        self.current_result=result
        if hasattr(self,"project_detail_button"): self.project_detail_button.configure(state="normal")
        family=result.family; catalog=result.catalog; pages=", ".join(str(p) for p in result.source_pages)
        newest=self.database.newest_catalog_id(family["manufacturer"])==str(catalog["id"]); newest_text="nejnovější vydání uložené v databázi" if newest else "historické vydání uložené v databázi"
        self.designation_var.set(result.designation); self.moment_value_var.set(result.moment_text); self.shear_value_var.set(result.shear_text)
        self.moment_info_var.set(f"{self.moment_var.get()} • {self.cover_var.get()} • {height} • izolant {result.insulation_text}")
        self.shear_info_var.set(f"{self.shear_var.get()} • {result.compression_transfer}")
        self.catalog_badge_var.set(f"{str(family['manufacturer']).upper()} • {catalog.get('edition','')} • {catalog.get('publication_label','')} • {newest_text}")
        self.source_var.set(f"Zdrojové strany: {pages or '—'}")
        labels=family.get("selector_labels",{})
        notes=[]; notes.extend(family.get("notes",[]) or []); notes.extend(result.record.get("notes",[]) or [])
        self.detail_var.set(
            f"Výrobce: {family['manufacturer']}\nModel / typ: {family['model']} / {family['type']}\nGenerace: {family['generation']}\n"
            f"{labels.get('moment','Hlavní třída')}: {self.moment_var.get()}\n{labels.get('shear','Vedlejší třída')}: {self.shear_var.get()}\n"
            f"{labels.get('concrete','Beton')}: {concrete_label(self.concrete_var.get())}\n{labels.get('cover','Varianta')}: {self.cover_var.get()}\n{labels.get('height','Rozměr')}: {height}\n"
            f"Tloušťka izolantu: {result.insulation_text}\nTlakový přenos: {result.compression_transfer}\n\n"
            f"STATICKÉ HODNOTY:\n{result.all_results_text}\n\nZáklad hodnot: {family.get('basis','—')}\nZdroj: strana {pages or '—'}"
            + (("\n\nPoznámky:\n• "+"\n• ".join(notes)) if notes else "")
        )
        self._fill_shear_tree(result); self.set_status(f"Načteno: {result.designation}")

    def _fill_shear_tree(self, result: QueryResult | None) -> None:
        previous=self._updating; self._updating=True
        try:
            self.shear_tree.delete(*self.shear_tree.get_children(""))
            if result is None:return
            classes=self.database.shear_classes(result.family,self.moment_var.get(),self.concrete_var.get())
            selected=None
            for i,sc in enumerate(classes):
                try:
                    qr=self.database.query(
                        catalog_id=str(result.family["catalog_id"]), manufacturer=str(result.family["manufacturer"]),
                        model=str(result.family["model"]), type_name=str(result.family["type"]), generation=str(result.family["generation"]),
                        moment_class=self.moment_var.get(), concrete_min=self.concrete_var.get(), shear_class=sc,
                        cover=self.cover_var.get(), height_mm=self.height_var.get(),
                    )
                    value=qr.shear_text
                    if value=="—" and qr.results: value=__import__('catalog_engine').format_result_value(qr.results[0])
                except Exception:
                    value="—"
                iid=f"v{i}"; self.shear_tree.insert("","end",iid=iid,values=(sc,value));
                if sc==self.shear_var.get(): selected=iid
            if selected:self.shear_tree.selection_set(selected); self.shear_tree.focus(selected)
        finally:self._updating=previous

    def on_shear_tree_selected(self, _event: tk.Event[Any] | None = None) -> None:
        if self._updating:return
        selection=self.shear_tree.selection()
        if not selection:return
        values=self.shear_tree.item(selection[0],"values")
        if not values:return
        shear_class=str(values[0])
        if shear_class==self.shear_var.get():return
        if shear_class in tuple(self.combos["shear"].cget("values")):
            self.shear_var.set(shear_class); self._run_cascade(self._cascade_from_shear)

    # ---------- rychlé označení ----------

    def _autocomplete_preferred_catalog(self) -> str | None:
        try:
            return self.current_catalog_id()
        except Exception:
            return None

    def _on_lookup_suggestion_chosen(self, result: QueryResult) -> None:
        self._apply_project_selection_to_lookup(selection_from_result(result))
        self.set_status(f"Doplněno z našeptávače: {result.designation}")

    def apply_quick_designation(self, _event: tk.Event[Any] | None = None) -> str | None:
        text=self.quick_var.get().strip()
        if not text:self.set_status("Vložte označení prvku."); return "break"
        try:
            preferred=None
            try: preferred=self.current_catalog_id()
            except Exception: pass
            result=self.database.resolve_designation(text,preferred_catalog_id=preferred)
            self._apply_project_selection_to_lookup(selection_from_result(result))
            self.set_status("Označení bylo rozpoznáno a načteno.")
        except Exception as exc:
            messagebox.showwarning("Označení nebylo jednoznačně rozpoznáno",str(exc),parent=self)
        return "break"

    # ---------- akce ----------

    def copy_result(self) -> None:
        if self.current_result is None:
            return
        self.clipboard_clear()
        self.clipboard_append(self.current_result.clipboard_text())
        self.set_status("Označení a statické hodnoty byly zkopírovány do schránky.")

    def copy_designation(self) -> None:
        if self.current_result is None:
            return
        self.clipboard_clear()
        self.clipboard_append(self.current_result.designation)
        self.set_status("Označení prvku bylo zkopírováno do schránky.")

    def source_path_for(self, result: QueryResult) -> Path:
        return self.source_dir / str(result.catalog["source_filename"])

    def open_current_source(self) -> None:
        if self.current_result is None:
            return
        page = int(self.current_result.source_pages[0]) if self.current_result.source_pages else 1
        path = self.source_path_for(self.current_result)
        if not path.exists():
            messagebox.showerror(
                "Zdrojový soubor nebyl nalezen",
                f"Program očekává zdrojový katalog zde:\n{path}",
                parent=self,
            )
            return
        try:
            uri = path.resolve().as_uri() + f"#page={page}"
            opened = webbrowser.open(uri, new=2)
            if not opened:
                open_path(path)
            self.set_status(f"Otevřen zdrojový katalog na straně {page}.")
        except Exception as exc:
            LOGGER.exception("Chyba při otevření PDF")
            messagebox.showerror("PDF se nepodařilo otevřít", str(exc), parent=self)

    def open_catalog_folder(self) -> None:
        try:
            open_path(self.catalog_dir)
        except Exception as exc:
            LOGGER.exception("Chyba při otevření katalogové složky")
            messagebox.showerror("Složku se nepodařilo otevřít", str(exc), parent=self)

    def show_height_table(self) -> None:
        if self.current_result is None:
            return
        HeightTableDialog(
            self,
            self.current_result.family,
            self.moment_var.get(),
            self.concrete_var.get(),
            self.shear_var.get(),
            self.cover_var.get(),
            self.height_var.get(),
        )

    def reset_selection(self) -> None:
        self.settings.pop("selections", None)
        self._populate_initial_data()
        self.refresh_result()
        self.set_status("Výběr byl nastaven na první dostupnou kombinaci.")

    def show_integrity_report(self) -> None:
        errors, warnings, stats = self.database.validation_report()
        self._update_integrity_summary(errors, warnings, stats)
        lines = [
            "KONTROLA DATABÁZE",
            "",
            f"Katalogové balíčky: {stats['catalogs']}",
            f"Produktové řady: {stats['families']}",
            f"Momentové výsledky: {stats['moment_records']}",
            f"Smykové výsledky: {stats['shear_records']}",
            "",
        ]
        if not errors and not warnings:
            lines.append("Výsledek: Bez nalezených chyb a upozornění.")
        if errors:
            lines.append(f"Chyby ({len(errors)}):")
            lines.extend(f"• {item}" for item in errors[:20])
            if len(errors) > 20:
                lines.append(f"• … a dalších {len(errors) - 20}")
        if warnings:
            lines.append("")
            lines.append(f"Upozornění ({len(warnings)}):")
            lines.extend(f"• {item}" for item in warnings[:20])
            if len(warnings) > 20:
                lines.append(f"• … a dalších {len(warnings) - 20}")
        messagebox.showinfo("Kontrola databáze", "\n".join(lines), parent=self)

    def _update_integrity_summary(self, errors: list[str], warnings: list[str], stats: dict[str, int]) -> None:
        if errors:
            self.integrity_var.set(f"Kontrola databáze: {len(errors)} chyb, {len(warnings)} upozornění.")
        elif warnings:
            self.integrity_var.set(f"Kontrola databáze: bez chyb, {len(warnings)} upozornění.")
        else:
            self.integrity_var.set(
                f"Kontrola databáze: v pořádku • {stats['moment_records']} momentových • {stats['shear_records']} smykových záznamů"
            )

    def toggle_theme(self) -> None:
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.settings["theme"] = self.theme_name
        self._save_settings()
        messagebox.showinfo(
            "Změna vzhledu",
            "Vzhled bude změněn po novém spuštění programu.",
            parent=self,
        )

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    # ---------- nastavení ----------

    def _load_settings(self) -> dict[str, Any]:
        try:
            if self.settings_path.exists():
                data = json.loads(self.settings_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception as exc:
            LOGGER.warning("Nastavení se nepodařilo načíst: %s", exc)
        return {}

    def _save_settings(self) -> None:
        try:
            temp = self.settings_path.with_suffix(".tmp")
            temp.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.settings_path)
        except Exception as exc:
            LOGGER.warning("Nastavení se nepodařilo uložit: %s", exc)

    def _restore_selections(self) -> None:
        selections = self.settings.get("selections")
        if not isinstance(selections, dict):
            return
        self._updating = True
        try:
            manufacturer = str(selections.get("manufacturer", self.manufacturer_var.get()))
            if manufacturer in self.combos["manufacturer"].cget("values"):
                self.manufacturer_var.set(manufacturer)
            self._cascade_from_manufacturer(str(selections.get("catalog_id", "")) or None)

            model = str(selections.get("model", ""))
            if model in self.combos["model"].cget("values"):
                self.model_var.set(model)
            self._cascade_from_model(str(selections.get("type", "")) or None)

            type_name = str(selections.get("type", ""))
            if type_name in self.combos["type"].cget("values"):
                self.type_var.set(type_name)
            self._cascade_from_type(str(selections.get("generation", "")) or None)

            generation = str(selections.get("generation", ""))
            if generation in self.combos["generation"].cget("values"):
                self.generation_var.set(generation)
            self._cascade_from_generation(str(selections.get("moment_class", "")) or None)

            moment = str(selections.get("moment_class", ""))
            if moment in self.combos["moment"].cget("values"):
                self.moment_var.set(moment)
            self._cascade_from_moment(
                str(selections.get("concrete_min", "")) or None,
                str(selections.get("shear_class", "")) or None,
            )

            concrete = str(selections.get("concrete_min", ""))
            if concrete in self.combos["concrete"].cget("values"):
                self.concrete_var.set(concrete)
            self._cascade_from_concrete(
                preferred_shear=str(selections.get("shear_class", "")) or None,
                preferred_cover=str(selections.get("cover", "")) or None,
            )

            shear = str(selections.get("shear_class", ""))
            if shear in self.combos["shear"].cget("values"):
                self.shear_var.set(shear)
            cover = str(selections.get("cover", ""))
            if cover in self.combos["cover"].cget("values"):
                self.cover_var.set(cover)
            self._cascade_from_cover(selections.get("height_mm"))

            height = str(selections.get("height_mm", ""))
            if height in self.combos["height"].cget("values"):
                self.height_var.set(height)
        except Exception as exc:
            LOGGER.warning("Poslední výběr se nepodařilo obnovit: %s", exc)
        finally:
            self._updating = False

    def on_close(self) -> None:
        if not self.confirm_project_close():
            return
        selections: dict[str, Any] = {
            "manufacturer": self.manufacturer_var.get(),
            "catalog_id": self.catalog_display_to_id.get(self.catalog_var.get(), ""),
            "model": self.model_var.get(),
            "type": self.type_var.get(),
            "generation": self.generation_var.get(),
            "moment_class": self.moment_var.get(),
            "shear_class": self.shear_var.get(),
            "concrete_min": self.concrete_var.get(),
            "cover": self.cover_var.get(),
            "height_mm": self.height_var.get(),
        }
        self.settings["theme"] = self.theme_name
        self.settings["geometry"] = self.geometry()
        self.settings["selections"] = selections
        self._save_settings()
        self.destroy()


def main() -> int:
    enable_high_dpi()
    try:
        app = ThermalConnectorApp()
        app.mainloop()
        return 0
    except CatalogError as exc:
        LOGGER.exception("Databáze se nepodařila načíst")
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Databáze se nepodařila načíst",
            f"{exc}\n\nZkontrolujte obsah složky 'catalogs' vedle programu.",
            parent=root,
        )
        root.destroy()
        return 2
    except Exception as exc:
        LOGGER.exception("Neočekávaná chyba aplikace")
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Neočekávaná chyba",
                f"Program narazil na neočekávanou chybu:\n\n{exc}\n\n"
                f"Podrobnosti jsou v souboru:\n{user_data_directory() / 'app.log'}",
                parent=root,
            )
            root.destroy()
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
