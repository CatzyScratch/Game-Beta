import tkinter as tk
from tkinter import filedialog, messagebox
import os, re, json

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

TILE = 56                    # base tile size at 1x zoom (matches the game)
ICON = 24                    # size of the palette button images
COLS, ROWS = 10, 8           # 480x360 fits 9x7 tiles of 56px, plus one extra column and row
IMGDIR = r"E:\CIS8\Python\Horror Game\assets\map images"
MAPDIR = r"E:\CIS8\Python\Horror Game\assets\map files"
JSON_PATH = os.path.join(IMGDIR, "tiles.json")

FIT = "crop"   # "crop" = fill the tile, trimming edges | "fit" = whole image, with empty space | "stretch" = squash to fit
ZOOMS = [0.5, 1, 2, 3, 4]
VIEW_W, VIEW_H = 720, 540    # max size of the editing area before scrollbars kick in
IMG_TYPES = [("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("All files", "*.*")]

root = tk.Tk()
root.title("TMF Map Editor - untitled")

TILEMAP = {}    # tile number -> image file name inside IMGDIR (None = no image yet)
NEXT = 2        # next new tile number (never reused, even after a tile is deleted)
Tiles = {}      # tile number -> image at the current zoom (drawn on the map)
Icons = {}      # tile number -> small image (used in the palette)
Errors = []
Map = [[0] * COLS for _ in range(ROWS)]
Selected = tk.IntVar(value=1)
CurrentFile = None
ZoomIdx = 1     # index into ZOOMS (1 = 1x)

def T():
    """Tile size in pixels at the current zoom."""
    return int(TILE * ZOOMS[ZoomIdx])

# ---- Tile registry (tiles.json) ----
def save_registry():
    os.makedirs(IMGDIR, exist_ok=True)
    with open(JSON_PATH, "w") as f:
        json.dump({"next": NEXT, "tiles": {str(k): v for k, v in sorted(TILEMAP.items())}}, f, indent=1)

def load_registry():
    global NEXT
    TILEMAP.clear()
    loaded = False
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH) as f:
                data = json.load(f)
            for k, v in data["tiles"].items():
                TILEMAP[int(k)] = v
            NEXT = int(data.get("next", 2))
            loaded = True
        except Exception:
            TILEMAP.clear()
    if not loaded and os.path.isdir(IMGDIR):      # first run: pick up existing T<N>.png files
        for name in os.listdir(IMGDIR):
            m = re.fullmatch(r"T(\d+)\.png", name, re.IGNORECASE)
            if m:
                TILEMAP[int(m.group(1))] = name
    TILEMAP.setdefault(0, None)
    TILEMAP.setdefault(1, None)
    NEXT = max(NEXT, max(TILEMAP) + 1, 2)
    save_registry()

# ---- Layout ----
left = tk.Frame(root)
left.pack(side="left", fill="y", padx=4, pady=4)

right = tk.Frame(root)
right.pack(side="left", fill="both", expand=True)
canvas = tk.Canvas(right, highlightthickness=0, bg="white")
vbar = tk.Scrollbar(right, orient="vertical", command=canvas.yview)
hbar = tk.Scrollbar(right, orient="horizontal", command=canvas.xview)
canvas.config(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
canvas.grid(row=0, column=0, sticky="nsew")
vbar.grid(row=0, column=1, sticky="ns")
hbar.grid(row=1, column=0, sticky="ew")
right.grid_rowconfigure(0, weight=1)
right.grid_columnconfigure(0, weight=1)

tk.Button(left, text="New tile type", command=lambda: new_tile()).pack(fill="x", pady=(0, 4))
tk.Button(left, text="Set image for selected tile...", command=lambda: set_image()).pack(fill="x", pady=(0, 4))
tk.Button(left, text="Import images as new tiles... (Ctrl+I)", command=lambda: import_images()).pack(fill="x", pady=(0, 4))
tk.Button(left, text="Refresh images (F5)", command=lambda: refresh()).pack(fill="x", pady=(0, 6))

zoombar = tk.Frame(left)
zoombar.pack(fill="x", pady=(0, 6))
tk.Button(zoombar, text="Zoom -", command=lambda: set_zoom(ZoomIdx - 1)).pack(side="left", expand=True, fill="x")
zoom_label = tk.Label(zoombar, text="1x", width=5)
zoom_label.pack(side="left")
tk.Button(zoombar, text="Zoom +", command=lambda: set_zoom(ZoomIdx + 1)).pack(side="left", expand=True, fill="x")

status = tk.Label(left, text="", anchor="w", justify="left", wraplength=170)
status.pack(side="bottom", fill="x", pady=4)

sel_label = tk.Label(left, text="", anchor="w", justify="left", wraplength=170)
sel_label.pack(fill="x", pady=(0, 4))

# Scrollable palette (there can be any number of tiles)
pal_outer = tk.Frame(left)
pal_outer.pack(fill="both", expand=True)
pal_canvas = tk.Canvas(pal_outer, width=110, height=260, highlightthickness=0)
pal_scroll = tk.Scrollbar(pal_outer, orient="vertical", command=pal_canvas.yview)
pal_canvas.config(yscrollcommand=pal_scroll.set)
pal_scroll.pack(side="right", fill="y")
pal_canvas.pack(side="left", fill="both", expand=True)
palette = tk.Frame(pal_canvas)
pal_canvas.create_window((0, 0), window=palette, anchor="nw")

def update_sel(*args):
    n = Selected.get()
    f = TILEMAP.get(n)
    sel_label.config(text=f"Tile {n}: {f if f else 'no image yet'}")
Selected.trace_add("write", update_sel)

# ---- Images ----
def fit_image(img, size):
    img = img.convert("RGBA")
    w, h = img.size
    if FIT == "stretch":
        return img.resize((size, size), Image.NEAREST)
    if FIT == "crop":
        s = min(w, h)                      # center square crop
        l, t = (w - s) // 2, (h - s) // 2
        return img.crop((l, t, l + s, t + s)).resize((size, size), Image.NEAREST)
    # "fit": scale to fit inside the tile, centered on a transparent square
    scale = size / max(w, h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img.resize((nw, nh), Image.NEAREST), ((size - nw) // 2, (size - nh) // 2))
    return out

def load_tiles():
    """Load the image for every tile in TILEMAP. None = no image, or file missing/unreadable."""
    Tiles.clear()
    Icons.clear()
    Errors.clear()
    size = T()
    for i, fname in TILEMAP.items():
        Tiles[i] = Icons[i] = None
        if not fname:
            continue
        path = os.path.join(IMGDIR, fname)
        if not os.path.exists(path):
            Errors.append(f"{fname} (tile {i}) is missing")
            continue
        try:
            if HAS_PIL:
                src = Image.open(path)
                Tiles[i] = ImageTk.PhotoImage(fit_image(src, size))
                Icons[i] = ImageTk.PhotoImage(fit_image(src, ICON))
            else:
                base = tk.PhotoImage(file=path)   # must already be tile-sized without Pillow
                Icons[i] = base
                z = ZOOMS[ZoomIdx]
                Tiles[i] = base.subsample(2) if z < 1 else base.zoom(int(z))
        except Exception:
            Errors.append(f"{fname} (tile {i}) can't be read")

def build_palette():
    for child in palette.winfo_children():
        child.destroy()
    for i in sorted(TILEMAP):
        if Icons.get(i) is not None:
            tk.Radiobutton(palette, image=Icons[i], text=f" {i}", compound="left", variable=Selected,
                           value=i, indicatoron=False, padx=4, pady=2, anchor="w").pack(fill="x", pady=1)
        else:
            tk.Radiobutton(palette, text=f"{i}", variable=Selected, value=i,
                           indicatoron=False, width=6, pady=6).pack(fill="x", pady=1)
    palette.update_idletasks()
    pal_canvas.config(scrollregion=pal_canvas.bbox("all"))
    update_sel()

def need_pillow():
    if HAS_PIL:
        return False
    messagebox.showerror("Pillow needed", "Choosing images needs Pillow.\n\nInstall it with:\npip install pillow")
    return True

def ingest(src):
    """Make sure the image lives in IMGDIR and return its file name there. Never overwrites anything."""
    os.makedirs(IMGDIR, exist_ok=True)
    src_dir = os.path.normcase(os.path.abspath(os.path.dirname(src)))
    if src_dir == os.path.normcase(os.path.abspath(IMGDIR)):
        Image.open(src).verify()                       # already in the folder: just use it
        return os.path.basename(src)
    stem = os.path.splitext(os.path.basename(src))[0]
    name, k = stem + ".png", 2
    while os.path.exists(os.path.join(IMGDIR, name)):  # don't overwrite an existing image
        name, k = f"{stem}_{k}.png", k + 1
    Image.open(src).convert("RGBA").save(os.path.join(IMGDIR, name), "PNG")
    return name

# ---- Tile actions ----
def take_number():
    global NEXT
    n = NEXT
    NEXT += 1
    return n

def new_tile(event=None):
    n = take_number()
    TILEMAP[n] = None
    save_registry()
    refresh()
    Selected.set(n)

def set_image(event=None):
    if need_pillow():
        return
    n = Selected.get()
    path = filedialog.askopenfilename(title=f"Choose an image for tile {n}", filetypes=IMG_TYPES)
    if not path:
        return
    try:
        name = ingest(path)
    except Exception as err:
        messagebox.showerror("Can't use that image", str(err))
        return
    TILEMAP[n] = name
    save_registry()
    refresh()

def import_images(event=None):
    if need_pillow():
        return
    paths = filedialog.askopenfilenames(title="Import images as new tiles", filetypes=IMG_TYPES)
    if not paths:
        return
    failed, last = [], None
    for p in paths:
        try:
            name = ingest(p)
        except Exception:
            failed.append(os.path.basename(p))
            continue
        n = take_number()
        TILEMAP[n] = name
        last = n
    save_registry()
    refresh()
    if last is not None:
        Selected.set(last)
    if failed:
        messagebox.showwarning("Import", "Couldn't read: " + ", ".join(failed))

def clear_image(event=None):
    n = Selected.get()
    if not TILEMAP.get(n):
        messagebox.showinfo("No image", f"Tile {n} has no image.")
        return
    TILEMAP[n] = None                                  # the image file itself is left alone
    save_registry()
    refresh()

def delete_tile(event=None):
    n = Selected.get()
    if n in (0, 1):
        messagebox.showinfo("Can't delete", "Tiles 0 and 1 are the default tiles and can't be deleted.\n"
                            "You can still change or clear their image.")
        return
    used = sum(row.count(n) for row in Map)
    msg = f"Delete tile type {n}?\n\nThe image file is NOT deleted."
    if used:
        msg += f"\n\nTile {n} is used {used} time(s) in this map. Those cells will show as plain numbered squares."
    msg += "\nOther maps that use this tile will lose it too."
    if not messagebox.askyesno("Delete tile type", msg):
        return
    TILEMAP.pop(n, None)
    save_registry()
    Selected.set(1)
    refresh()

# ---- Drawing ----
def draw_cell(x, y):
    tag = f"c{x}_{y}"
    canvas.delete(tag)
    t = Map[y][x]
    s = T()
    px, py_ = x * s, y * s
    if Tiles.get(t) is not None:
        canvas.create_image(px, py_, image=Tiles[t], anchor="nw", tags=tag)
    else:
        canvas.create_rectangle(px, py_, px + s, py_ + s, outline="#cccccc", fill="white", tags=tag)
        canvas.create_text(px + s // 2, py_ + s // 2, text=str(t),
                           font=("Arial", max(6, s * 3 // 8)), tags=tag)

def draw_guides():
    canvas.delete("guide")
    s = T()
    h, w = len(Map), len(Map[0])
    z = ZOOMS[ZoomIdx]
    if h * s > 360 * z:
        canvas.create_line(0, 360 * z, w * s, 360 * z, fill="red", dash=(4, 4), tags="guide")   # bottom edge of game window
    if w * s > 480 * z:
        canvas.create_line(480 * z, 0, 480 * z, h * s, fill="red", dash=(4, 4), tags="guide")   # right edge of game window
    canvas.tag_raise("guide")

def rebuild():
    s = T()
    h, w = len(Map), len(Map[0])
    canvas.config(width=min(w * s, VIEW_W), height=min(h * s, VIEW_H), scrollregion=(0, 0, w * s, h * s))
    canvas.delete("all")
    for y in range(h):
        for x in range(w):
            draw_cell(x, y)
    draw_guides()
    zoom_label.config(text=f"{ZOOMS[ZoomIdx]:g}x")
    msg = f"{w} x {h} tiles"
    if Errors:
        msg += "\n" + "\n".join(Errors)
    status.config(text=msg)

def refresh(event=None):
    load_tiles()
    build_palette()
    rebuild()

def set_zoom(idx):
    global ZoomIdx
    idx = max(0, min(len(ZOOMS) - 1, idx))
    if idx == ZoomIdx:
        return
    fx, fy = canvas.xview()[0], canvas.yview()[0]      # remember where we were scrolled to
    ZoomIdx = idx
    refresh()
    canvas.xview_moveto(fx)
    canvas.yview_moveto(fy)

# ---- Painting ----
def paint(event, value):
    s = T()
    x, y = int(canvas.canvasx(event.x)) // s, int(canvas.canvasy(event.y)) // s
    if 0 <= y < len(Map) and 0 <= x < len(Map[0]) and Map[y][x] != value:
        Map[y][x] = value
        draw_cell(x, y)
        canvas.tag_raise("guide")

canvas.bind("<Button-1>", lambda e: paint(e, Selected.get()))
canvas.bind("<B1-Motion>", lambda e: paint(e, Selected.get()))
canvas.bind("<Button-3>", lambda e: paint(e, 0))
canvas.bind("<B3-Motion>", lambda e: paint(e, 0))
canvas.bind("<Button-2>", lambda e: paint(e, 0))     # right click on macOS
canvas.bind("<B2-Motion>", lambda e: paint(e, 0))

# ---- Mouse wheel: over the palette it scrolls the palette; over the map, Ctrl zooms, Shift scrolls sideways ----
def in_palette(w):
    while w is not None:
        if w is pal_outer:
            return True
        w = getattr(w, "master", None)
    return False

def on_wheel(event):
    direction = 1 if (event.num == 4 or getattr(event, "delta", 0) > 0) else -1
    if in_palette(event.widget):
        pal_canvas.yview_scroll(-direction * 2, "units")
    elif event.state & 0x4:                     # Ctrl held
        set_zoom(ZoomIdx + direction)
    elif event.state & 0x1:                     # Shift held
        canvas.xview_scroll(-direction * 2, "units")
    else:
        canvas.yview_scroll(-direction * 2, "units")

root.bind_all("<MouseWheel>", on_wheel)         # Windows / macOS
root.bind_all("<Button-4>", on_wheel)           # Linux
root.bind_all("<Button-5>", on_wheel)

# ---- File actions ----
def parse_map(lines):
    """Space-separated numbers (current format). Older files: commas, or one digit per tile."""
    lines = [l.strip() for l in lines if l.strip()]
    if any("," in l for l in lines):
        return [[int(v) for v in l.split(",") if v.strip() != ""] for l in lines]
    if any(" " in l or "\t" in l for l in lines):
        return [[int(v) for v in l.split()] for l in lines]
    return [[int(c) for c in l] for l in lines]

def new_map():
    global Map, CurrentFile
    Map = [[0] * COLS for _ in range(ROWS)]
    CurrentFile = None
    root.title("TMF Map Editor - untitled")
    rebuild()

def open_map():
    global Map, CurrentFile
    os.makedirs(MAPDIR, exist_ok=True)
    path = filedialog.askopenfilename(initialdir=MAPDIR,
                                      filetypes=[("TMF map", "*.tmf"), ("All files", "*.*")])
    if not path:
        return
    try:
        with open(path) as f:
            rows = parse_map(f.readlines())
    except ValueError:
        messagebox.showerror("Bad map file", "That file has something other than numbers in it.")
        return
    if not rows:
        return
    width = max(len(r) for r in rows)
    Map = [r + [0] * (width - len(r)) for r in rows]     # pad short rows so the map is rectangular
    CurrentFile = path
    root.title(f"TMF Map Editor - {os.path.basename(path)}")
    rebuild()

def write(path):
    global CurrentFile
    with open(path, "w") as f:
        for row in Map:
            f.write(" ".join(str(t) for t in row) + "\n")
    CurrentFile = path
    root.title(f"TMF Map Editor - {os.path.basename(path)}")

def save_as(event=None):
    os.makedirs(MAPDIR, exist_ok=True)
    path = filedialog.asksaveasfilename(initialdir=MAPDIR, defaultextension=".tmf",
                                        filetypes=[("TMF map", "*.tmf")])
    if path:
        write(path)

def save(event=None):
    write(CurrentFile) if CurrentFile else save_as()

def fill_all():
    for y in range(len(Map)):
        for x in range(len(Map[0])):
            Map[y][x] = Selected.get()
    rebuild()

def border():
    v = Selected.get()
    h, w = len(Map), len(Map[0])
    for x in range(w):
        Map[0][x] = Map[h - 1][x] = v
    for y in range(h):
        Map[y][0] = Map[y][w - 1] = v
    rebuild()

menu = tk.Menu(root)
filemenu = tk.Menu(menu, tearoff=0)
filemenu.add_command(label="New", command=new_map)
filemenu.add_command(label="Open...", command=open_map)
filemenu.add_command(label="Save", command=save, accelerator="Ctrl+S")
filemenu.add_command(label="Save As...", command=save_as)
menu.add_cascade(label="File", menu=filemenu)
tilemenu = tk.Menu(menu, tearoff=0)
tilemenu.add_command(label="New tile type", command=new_tile)
tilemenu.add_command(label="Set image for selected tile...", command=set_image)
tilemenu.add_command(label="Import images as new tiles...", command=import_images, accelerator="Ctrl+I")
tilemenu.add_separator()
tilemenu.add_command(label="Clear image from selected tile (file is kept)", command=clear_image, accelerator="Del")
tilemenu.add_command(label="Delete selected tile type (file is kept)", command=delete_tile)
menu.add_cascade(label="Tiles", menu=tilemenu)
tools = tk.Menu(menu, tearoff=0)
tools.add_command(label="Fill with selected tile", command=fill_all)
tools.add_command(label="Border with selected tile", command=border)
tools.add_command(label="Refresh images", command=refresh, accelerator="F5")
menu.add_cascade(label="Tools", menu=tools)
viewmenu = tk.Menu(menu, tearoff=0)
viewmenu.add_command(label="Zoom in", command=lambda: set_zoom(ZoomIdx + 1), accelerator="+")
viewmenu.add_command(label="Zoom out", command=lambda: set_zoom(ZoomIdx - 1), accelerator="-")
viewmenu.add_command(label="Reset zoom (1x)", command=lambda: set_zoom(1))
menu.add_cascade(label="View", menu=viewmenu)
root.config(menu=menu)

root.bind("<Control-s>", save)
root.bind("<Control-i>", import_images)
root.bind("<Delete>", clear_image)
root.bind("<F5>", refresh)
root.bind("<plus>", lambda e: set_zoom(ZoomIdx + 1))
root.bind("<equal>", lambda e: set_zoom(ZoomIdx + 1))
root.bind("<minus>", lambda e: set_zoom(ZoomIdx - 1))
for i in range(10):
    root.bind(str(i), lambda e, i=i: Selected.set(i) if i in TILEMAP else None)   # number keys jump to tiles 0-9

load_registry()
refresh()
root.mainloop()
