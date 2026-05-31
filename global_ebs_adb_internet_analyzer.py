# -*- coding: utf-8 -*-
"""
EBS Elite ADB Internet Analyzer v3 - Gold FX Edition

Mobil veri / Wi‑Fi kullanımını ADB üzerinden analiz eden modern görsel GUI.

Özellikler:
- Altın / siyah premium tema
- Canvas tabanlı dekoratif arka plan
- Hover efektli butonlar
- Glow çizgili başlık alanı
- Özet kartları
- Mobil Veri / Wi‑Fi / Tümü filtresi
- Saatlik / günlük / aylık / yıllık / toplam analiz
- Göreceli / Gerçek Tarih zaman modu
- Uygulama adı / UID arama
- CSV dışa aktarma

"""

import subprocess
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from collections import defaultdict
import csv
import threading


TYPE_NAMES = {
    "0": "Mobil Veri",
    "1": "Wi‑Fi",
}

BG = "#07080B"
BG_2 = "#0D1118"
PANEL = "#121722"
PANEL_2 = "#191F2B"
PANEL_3 = "#202838"
TEXT = "#F7F1DF"
MUTED = "#AFA991"
GOLD = "#D4AF37"
GOLD_LIGHT = "#F6D76B"
GOLD_DARK = "#8C6912"
BORDER = "#34303A"
DANGER = "#FF6B6B"
GREEN = "#2ECC71"


def run_cmd(cmd):
    return subprocess.check_output(cmd, shell=True, text=True, encoding="utf-8", errors="ignore")


def bytes_to_mb(value):
    return value / 1024 / 1024


def bytes_to_gb(value):
    return value / 1024 / 1024 / 1024


def safe_dt(ts):
    try:
        return datetime.fromtimestamp(int(ts))
    except Exception:
        return None


def real_period_key(dt, mode):
    if mode == "Saatlik":
        return dt.strftime("%Y-%m-%d %H:00")
    if mode == "Günlük":
        return dt.strftime("%Y-%m-%d")
    if mode == "Aylık":
        return dt.strftime("%Y-%m")
    if mode == "Yıllık":
        return dt.strftime("%Y")
    return "Toplam"


def relative_period_key(timestamp, first_timestamp, mode):
    diff = max(0, int(timestamp) - int(first_timestamp))

    if mode == "Saatlik":
        return f"Saat {diff // 3600 + 1}"
    if mode == "Günlük":
        return f"Gün {diff // 86400 + 1}"
    if mode == "Aylık":
        return f"Ay {diff // (86400 * 30) + 1}"
    if mode == "Yıllık":
        return f"Yıl {diff // (86400 * 365) + 1}"

    return "Toplam"


class NetStatsAnalyzer:
    def __init__(self):
        self.uid_to_package = {}
        self.records = []
        self.first_timestamp = None
        self.last_timestamp = None

    def load_packages(self):
        output = run_cmd("adb shell cmd package list packages -U")
        uid_map = {}

        for line in output.splitlines():
            m = re.search(r"package:(.+?)\s+uid:(\d+)", line)
            if m:
                package, uid = m.group(1), m.group(2)
                uid_map[uid] = package

        self.uid_to_package = uid_map

    def load_netstats(self):
        output = run_cmd("adb shell dumpsys netstats detail")
        self.records = self.parse_netstats(output)

        timestamps = [r["timestamp"] for r in self.records]
        self.first_timestamp = min(timestamps) if timestamps else None
        self.last_timestamp = max(timestamps) if timestamps else None

    def parse_netstats(self, text):
        records = []
        current_type = None
        current_uid = None
        current_set = None
        in_uid_stats = False

        for raw in text.splitlines():
            line = raw.strip()

            if line.startswith("UID stats:"):
                in_uid_stats = True
                continue

            if line.startswith("UID tag stats:"):
                in_uid_stats = False
                continue

            if not in_uid_stats:
                continue

            ident = re.search(r"ident=\[\{type=(\d+).*?defaultNetwork=(true|false)", line)
            if ident:
                current_type = ident.group(1)
                uid_match = re.search(r"uid=(-?\d+)", line)
                set_match = re.search(r"set=([A-Z_]+)", line)
                current_uid = uid_match.group(1) if uid_match else None
                current_set = set_match.group(1) if set_match else None
                continue

            bucket = re.search(r"st=(\d+)\s+rb=(\d+)\s+rp=(\d+)\s+tb=(\d+)\s+tp=(\d+)", line)

            if bucket and current_uid:
                st = int(bucket.group(1))
                rb = int(bucket.group(2))
                tb = int(bucket.group(4))

                records.append({
                    "uid": current_uid,
                    "package": self.uid_to_package.get(current_uid, f"UID {current_uid}"),
                    "type": TYPE_NAMES.get(current_type, f"type={current_type}"),
                    "set": current_set or "",
                    "timestamp": st,
                    "datetime": safe_dt(st),
                    "rx": rb,
                    "tx": tb,
                    "total": rb + tb,
                })

        return records

    def summarize(self, network_filter="Tümü", period_mode="Günlük", time_mode="Göreceli"):
        grouped = defaultdict(lambda: {"rx": 0, "tx": 0, "total": 0})
        first_ts = self.first_timestamp or 0

        for r in self.records:
            if network_filter != "Tümü" and r["type"] != network_filter:
                continue

            if time_mode == "Gerçek Tarih":
                key_period = real_period_key(r["datetime"], period_mode) if r["datetime"] else "Bilinmeyen Tarih"
            else:
                key_period = relative_period_key(r["timestamp"], first_ts, period_mode)

            key = (key_period, r["uid"], r["package"], r["type"])
            grouped[key]["rx"] += r["rx"]
            grouped[key]["tx"] += r["tx"]
            grouped[key]["total"] += r["total"]

        rows = []
        for (period, uid, package, ntype), vals in grouped.items():
            rows.append({
                "period": period,
                "uid": uid,
                "package": package,
                "network": ntype,
                "rx": vals["rx"],
                "tx": vals["tx"],
                "total": vals["total"],
                "mb": bytes_to_mb(vals["total"]),
                "gb": bytes_to_gb(vals["total"]),
            })

        rows.sort(key=lambda x: x["total"], reverse=True)
        return rows


class FXButton(tk.Canvas):
    def __init__(self, master, text, command, kind="gold", width=170, height=42):
        super().__init__(master, width=width, height=height, highlightthickness=0, bg=BG)
        self.command = command
        self.text = text
        self.kind = kind
        self.width = width
        self.height = height
        self.hover = False
        self.draw()

        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", lambda e: self.command())

    def draw(self):
        self.delete("all")
        if self.kind == "gold":
            fill = GOLD_LIGHT if self.hover else GOLD
            outline = "#FFE28A" if self.hover else GOLD_DARK
            txt = "#111111"
        else:
            fill = PANEL_3 if self.hover else PANEL_2
            outline = GOLD if self.hover else BORDER
            txt = TEXT

        self.create_round_rect(2, 2, self.width - 2, self.height - 2, 16, fill=fill, outline=outline, width=2)
        if self.hover:
            self.create_round_rect(6, 6, self.width - 6, self.height - 6, 13, fill="", outline="#FFF1B0", width=1)
        self.create_text(self.width / 2, self.height / 2, text=self.text, fill=txt, font=("Segoe UI Semibold", 10))

    def on_enter(self, _):
        self.hover = True
        self.draw()
        self.config(cursor="hand2")

    def on_leave(self, _):
        self.hover = False
        self.draw()

    def create_round_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)


class GoldFXApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("EBS Elite ADB Internet Analyzer - Gold FX")
        self.geometry("1380x820")
        self.minsize(1120, 680)
        self.configure(bg=BG)

        self.analyzer = NetStatsAnalyzer()
        self.current_rows = []

        self.setup_style()
        self.create_layout()
        self.animate_bg()

    def setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL, font=("Segoe UI", 10))
        style.configure("Root.TFrame", background=BG)
        style.configure("Glass.TFrame", background=PANEL)
        style.configure("Card.TFrame", background=PANEL_2)
        style.configure("Title.TLabel", background=BG, foreground=GOLD_LIGHT, font=("Segoe UI Semibold", 24))
        style.configure("Sub.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("PanelText.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI Semibold", 9))
        style.configure("CardTitle.TLabel", background=PANEL_2, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("CardValue.TLabel", background=PANEL_2, foreground=GOLD_LIGHT, font=("Segoe UI Semibold", 19))
        style.configure("Tiny.TLabel", background=PANEL_2, foreground=MUTED, font=("Segoe UI", 8))

        # Windows'ta ttk Combobox bazı temalarda beyaz görünebilir.
        # Bu ayarlar kutu gövdesini koyu yapar; açılan liste rengi ayrıca option_add ile aşağıda ayarlanır.
        style.configure(
            "TCombobox",
            fieldbackground=PANEL_2,
            background=PANEL_2,
            foreground=TEXT,
            selectbackground=PANEL_3,
            selectforeground=GOLD_LIGHT,
            arrowcolor=GOLD,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=6
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", PANEL_2), ("focus", PANEL_2)],
            background=[("readonly", PANEL_2), ("active", PANEL_3)],
            foreground=[("readonly", TEXT)],
            selectbackground=[("readonly", PANEL_3)],
            selectforeground=[("readonly", GOLD_LIGHT)]
        )

        style.configure(
            "TEntry",
            fieldbackground=PANEL_2,
            background=PANEL_2,
            foreground=TEXT,
            insertcolor=GOLD_LIGHT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=9
        )

        self.option_add("*TCombobox*Listbox.background", PANEL_2)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", GOLD_DARK)
        self.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=34, bordercolor=BORDER, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#0F131B", foreground=GOLD_LIGHT, font=("Segoe UI Semibold", 10), relief="flat")
        style.map("Treeview", background=[("selected", GOLD_DARK)], foreground=[("selected", "#FFFFFF")])

    def create_layout(self):
        self.bg_canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.root_frame = ttk.Frame(self, style="Root.TFrame", padding=20)
        self.root_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        header = ttk.Frame(self.root_frame, style="Root.TFrame")
        header.pack(fill=tk.X)

        title_area = ttk.Frame(header, style="Root.TFrame")
        title_area.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(title_area, text="EBS Elite ADB Internet Analyzer", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(title_area, text="Gold FX Edition • Mobil veri, Wi‑Fi, uygulama bazlı GB/MB analiz paneli", style="Sub.TLabel").pack(anchor=tk.W, pady=(4, 0))

        self.status_badge = tk.Canvas(header, width=190, height=42, bg=BG, highlightthickness=0)
        self.status_badge.pack(side=tk.RIGHT, padx=(12, 0))
        self.draw_badge("ADB BEKLENİYOR", GOLD_DARK)

        FXButton(header, "Verileri Çek", self.load_data_thread, kind="gold", width=150).pack(side=tk.RIGHT)

        glow = tk.Canvas(self.root_frame, height=18, bg=BG, highlightthickness=0)
        glow.pack(fill=tk.X, pady=(12, 4))
        glow.create_line(0, 8, 1600, 8, fill=GOLD_DARK, width=1)
        glow.create_line(0, 9, 420, 9, fill=GOLD_LIGHT, width=2)
        glow.create_oval(390, 3, 420, 15, outline=GOLD_LIGHT)

        controls = tk.Frame(self.root_frame, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        controls.pack(fill=tk.X, pady=(8, 14), ipady=12, ipadx=12)

        self.network_var = tk.StringVar(value="Tümü")
        self.period_var = tk.StringVar(value="Günlük")
        self.time_mode_var = tk.StringVar(value="Göreceli")
        self.search_var = tk.StringVar()

        self.add_control(controls, "AĞ", self.network_var, ["Tümü", "Mobil Veri", "Wi‑Fi"], 0)
        self.add_control(controls, "DÖNEM", self.period_var, ["Saatlik", "Günlük", "Aylık", "Yıllık", "Toplam"], 1)
        self.add_control(controls, "ZAMAN MODU", self.time_mode_var, ["Göreceli", "Gerçek Tarih"], 2)

        search_box = tk.Frame(controls, bg=PANEL)
        search_box.grid(row=0, column=3, sticky="ew", padx=8)
        ttk.Label(search_box, text="UYGULAMA / UID ARA", style="PanelText.TLabel").pack(anchor=tk.W)
        self.search_entry = tk.Entry(
            search_box,
            textvariable=self.search_var,
            bg=PANEL_2,
            fg=TEXT,
            insertbackground=GOLD_LIGHT,
            selectbackground=GOLD_DARK,
            selectforeground="#FFFFFF",
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=GOLD,
            font=("Segoe UI", 10)
        )
        self.search_entry.pack(fill=tk.X, pady=(6, 0), ipady=8)

        btns = tk.Frame(controls, bg=PANEL)
        btns.grid(row=0, column=4, sticky="e", padx=(10, 0))
        FXButton(btns, "Filtrele", self.refresh_table, kind="dark", width=120, height=40).pack(side=tk.LEFT, padx=4)
        FXButton(btns, "CSV Aktar", self.export_csv, kind="dark", width=125, height=40).pack(side=tk.LEFT, padx=4)

        controls.columnconfigure(3, weight=1)

        cards = tk.Frame(self.root_frame, bg=BG)
        cards.pack(fill=tk.X, pady=(0, 14))

        self.total_value = self.create_fx_card(cards, "TOPLAM KULLANIM", "-", "◆")
        self.rx_value = self.create_fx_card(cards, "İNDİRİLEN", "-", "↓")
        self.tx_value = self.create_fx_card(cards, "YÜKLENEN", "-", "↑")
        self.row_value = self.create_fx_card(cards, "SATIR", "-", "≡")
        self.range_value = self.create_fx_card(cards, "KAYIT ARALIĞI", "-", "◷")

        table_outer = tk.Frame(self.root_frame, bg=GOLD_DARK, padx=1, pady=1)
        table_outer.pack(fill=tk.BOTH, expand=True)

        table_wrap = tk.Frame(table_outer, bg=PANEL)
        table_wrap.pack(fill=tk.BOTH, expand=True)

        columns = ("period", "network", "package", "uid", "download", "upload", "total_mb", "total_gb")
        self.tree = ttk.Treeview(table_wrap, columns=columns, show="headings")

        headings = {
            "period": "Dönem",
            "network": "Ağ",
            "package": "Uygulama / Paket",
            "uid": "UID",
            "download": "İndirilen MB",
            "upload": "Yüklenen MB",
            "total_mb": "Toplam MB",
            "total_gb": "Toplam GB",
        }

        widths = {
            "period": 150,
            "network": 110,
            "package": 410,
            "uid": 80,
            "download": 125,
            "upload": 125,
            "total_mb": 125,
            "total_gb": 115,
        }

        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor=tk.W, stretch=True)

        yscroll = ttk.Scrollbar(table_wrap, orient=tk.VERTICAL, command=self.tree.yview)
        xscroll = ttk.Scrollbar(table_wrap, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscroll=yscroll.set, xscroll=xscroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)

        footer = tk.Frame(self.root_frame, bg=BG)
        footer.pack(fill=tk.X, pady=(10, 0))

        self.status_var = tk.StringVar(value="Hazır. USB hata ayıklamayı açıp Verileri Çek butonuna basın.")
        ttk.Label(footer, textvariable=self.status_var, style="Sub.TLabel").pack(side=tk.LEFT)
        ttk.Label(footer, text="Gold FX • Local ADB Analyzer", style="Sub.TLabel").pack(side=tk.RIGHT)

        self.search_var.trace_add("write", lambda *_: self.refresh_table())
        self.network_var.trace_add("write", lambda *_: self.refresh_table())
        self.period_var.trace_add("write", lambda *_: self.refresh_table())
        self.time_mode_var.trace_add("write", lambda *_: self.refresh_table())

    def add_control(self, parent, label, variable, values, col):
        box = tk.Frame(parent, bg=PANEL)
        box.grid(row=0, column=col, sticky="ew", padx=8)
        ttk.Label(box, text=label, style="PanelText.TLabel").pack(anchor=tk.W)
        combo = ttk.Combobox(box, textvariable=variable, values=values, state="readonly", width=16)
        combo.pack(fill=tk.X, pady=(6, 0))
        # Bazı Windows sürümlerinde focus alınca beyazlamayı azaltır.
        combo.bind("<FocusIn>", lambda e: self.after(1, lambda: e.widget.selection_clear()))
        return combo

    def create_fx_card(self, parent, title, value, icon):
        outer = tk.Frame(parent, bg=GOLD_DARK, padx=1, pady=1)
        outer.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        card = tk.Frame(outer, bg=PANEL_2, padx=14, pady=12)
        card.pack(fill=tk.BOTH, expand=True)

        top = tk.Frame(card, bg=PANEL_2)
        top.pack(fill=tk.X)

        icon_canvas = tk.Canvas(top, width=30, height=30, bg=PANEL_2, highlightthickness=0)
        icon_canvas.pack(side=tk.LEFT)
        icon_canvas.create_oval(2, 2, 28, 28, fill="#2A2210", outline=GOLD_DARK)
        icon_canvas.create_text(15, 15, text=icon, fill=GOLD_LIGHT, font=("Segoe UI Semibold", 13))

        ttk.Label(top, text=title, style="CardTitle.TLabel").pack(side=tk.LEFT, padx=(8, 0))

        label = ttk.Label(card, text=value, style="CardValue.TLabel")
        label.pack(anchor=tk.W, pady=(8, 0))

        ttk.Label(card, text="NetworkStats", style="Tiny.TLabel").pack(anchor=tk.W, pady=(3, 0))
        return label

    def draw_badge(self, text, color):
        self.status_badge.delete("all")
        self.round_rect(self.status_badge, 2, 4, 188, 38, 18, fill="#17120A", outline=color, width=2)
        self.status_badge.create_oval(14, 17, 24, 27, fill=color, outline="")
        self.status_badge.create_text(105, 22, text=text, fill=TEXT, font=("Segoe UI Semibold", 9))

    def round_rect(self, canvas, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def animate_bg(self):
        self.bg_canvas.delete("all")
        w = max(self.winfo_width(), 1000)
        h = max(self.winfo_height(), 700)

        self.bg_canvas.create_rectangle(0, 0, w, h, fill=BG, outline="")
        self.bg_canvas.create_oval(-180, -140, 420, 330, fill="#171100", outline="")
        self.bg_canvas.create_oval(w - 360, 60, w + 180, 540, fill="#101725", outline="")
        self.bg_canvas.create_oval(w * 0.35, h - 160, w * 0.35 + 520, h + 180, fill="#130F06", outline="")

        for i in range(0, int(w), 90):
            self.bg_canvas.create_line(i, 0, i - 180, h, fill="#0F1219", width=1)

        for i in range(0, int(w), 240):
            self.bg_canvas.create_line(i, 0, i + 260, h, fill="#151009", width=1)

        self.bg_canvas.create_line(30, 92, w - 30, 92, fill="#19150A", width=1)
        self.bg_canvas.create_line(30, 93, 430, 93, fill=GOLD_DARK, width=2)

        self.after(3000, self.animate_bg)

    def load_data_thread(self):
        threading.Thread(target=self.load_data, daemon=True).start()

    def load_data(self):
        try:
            self.status_var.set("ADB cihaz kontrol ediliyor...")
            self.draw_badge("TARANIYOR", GOLD)

            devices = run_cmd("adb devices")
            if "\tdevice" not in devices:
                self.draw_badge("CİHAZ YOK", DANGER)
                messagebox.showerror(
                    "Cihaz bulunamadı",
                    "ADB cihaz bulunamadı.\n\nKontrol edin:\n- USB hata ayıklama açık mı?\n- Telefonda izin verdiniz mi?\n- adb devices cihazı görüyor mu?"
                )
                self.status_var.set("Cihaz bulunamadı.")
                return

            self.status_var.set("Paket listesi alınıyor...")
            self.analyzer.load_packages()

            self.status_var.set("NetworkStats verileri analiz ediliyor...")
            self.analyzer.load_netstats()

            self.draw_badge("BAĞLANDI", GREEN)
            self.status_var.set(f"Veri yüklendi. Ham kayıt: {len(self.analyzer.records)}")
            self.refresh_table()

        except subprocess.CalledProcessError as e:
            self.draw_badge("ADB HATASI", DANGER)
            messagebox.showerror("ADB Hatası", str(e))
            self.status_var.set("ADB hatası oluştu.")
        except Exception as e:
            self.draw_badge("HATA", DANGER)
            messagebox.showerror("Hata", str(e))
            self.status_var.set("Hata oluştu.")

    def refresh_table(self):
        if not self.analyzer.records:
            return

        network = self.network_var.get()
        period = self.period_var.get()
        time_mode = self.time_mode_var.get()
        query = self.search_var.get().lower().strip()

        rows = self.analyzer.summarize(network, period, time_mode)

        if query:
            rows = [r for r in rows if query in r["package"].lower() or query in r["uid"]]

        self.current_rows = rows

        for item in self.tree.get_children():
            self.tree.delete(item)

        total_rx = 0
        total_tx = 0
        total_all = 0

        for index, r in enumerate(rows):
            total_rx += r["rx"]
            total_tx += r["tx"]
            total_all += r["total"]

            tag = "even" if index % 2 == 0 else "odd"
            self.tree.insert("", tk.END, values=(
                r["period"],
                r["network"],
                r["package"],
                r["uid"],
                f"{bytes_to_mb(r['rx']):.2f}",
                f"{bytes_to_mb(r['tx']):.2f}",
                f"{r['mb']:.2f}",
                f"{r['gb']:.3f}",
            ), tags=(tag,))

        self.tree.tag_configure("even", background=PANEL)
        self.tree.tag_configure("odd", background="#0E131C")

        self.total_value.config(text=f"{bytes_to_gb(total_all):.3f} GB")
        self.rx_value.config(text=f"{bytes_to_gb(total_rx):.3f} GB")
        self.tx_value.config(text=f"{bytes_to_gb(total_tx):.3f} GB")
        self.row_value.config(text=str(len(rows)))

        if self.analyzer.first_timestamp and self.analyzer.last_timestamp:
            seconds = self.analyzer.last_timestamp - self.analyzer.first_timestamp
            days = seconds / 86400
            if days < 1:
                self.range_value.config(text=f"{seconds / 3600:.1f} saat")
            else:
                self.range_value.config(text=f"{days:.1f} gün")

    def export_csv(self):
        if not self.current_rows:
            messagebox.showwarning("Veri yok", "Dışa aktarılacak veri yok.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Dosyası", "*.csv")]
        )

        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Dönem", "Ağ", "Uygulama", "UID",
                "İndirilen Byte", "Yüklenen Byte", "Toplam Byte",
                "Toplam MB", "Toplam GB"
            ])

            for r in self.current_rows:
                writer.writerow([
                    r["period"], r["network"], r["package"], r["uid"],
                    r["rx"], r["tx"], r["total"],
                    f"{r['mb']:.2f}", f"{r['gb']:.3f}"
                ])

        messagebox.showinfo("Tamamlandı", f"CSV kaydedildi:\n{path}")


if __name__ == "__main__":
    app = GoldFXApp()
    app.mainloop()
