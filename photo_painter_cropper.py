import os
import math
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageFilter

# ====== CONFIG ======
TARGET_SIZE = (800, 480)           # output JPG esatto
RATIO = TARGET_SIZE[0] / TARGET_SIZE[1]
WINDOW_MIN = (900, 700)
JPEG_QUALITY = 95

ARROW_STEP = 5                      # px per step con frecce
ARROW_STEP_FAST = 20                # px con Shift premuto
SCALE_FACTOR = 1.05                 # zoom step con +/- normali
SCALE_FACTOR_FAST = 1.10            # zoom step con Shift

STATE_SUFFIX = "_ppcrop.txt"        # file stato accanto all'immagine sorgente

class CropperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Photo Painter – Crop 800x480 (JPG, white/blur fill) + stato")
        self.root.minsize(*WINDOW_MIN)

        top = tk.Frame(root)
        top.pack(fill=tk.X, side=tk.TOP)
        self.mode_lbl = tk.Label(top, text="")
        self.mode_lbl.pack(padx=10, pady=6, anchor="w")

        self.canvas = tk.Canvas(root, bg="#111")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Mouse
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<MouseWheel>", self.on_wheel)     # mac/win
        self.canvas.bind("<Button-4>", self.on_wheel_linux) # linux up
        self.canvas.bind("<Button-5>", self.on_wheel_linux) # linux down

        # Tastiera (conferma)
        self.root.bind("<Return>", self.on_confirm)
        self.root.bind_all("<Tab>", self.on_confirm_tab)    # intercetta Tab (evita cambio focus)
        self.root.bind("<a>", self.on_confirm)
        self.root.bind("<A>", self.on_confirm)
        self.root.bind("<Escape>", self.on_skip)

        # Tastiera (spostamento)
        self.root.bind("<Left>",  lambda e: self.on_arrow(e, -1,  0))
        self.root.bind("<Right>", lambda e: self.on_arrow(e,  1,  0))
        self.root.bind("<Up>",    lambda e: self.on_arrow(e,  0, -1))
        self.root.bind("<Down>",  lambda e: self.on_arrow(e,  0,  1))

        # Tastiera (ridimensiona)
        for ks in ("<plus>", "<KP_Add>", "<equal>"):  # '+' spesso è Shift+'='; includo '=' per comodità
            self.root.bind(ks, self.on_plus)
        for ks in ("<minus>", "<KP_Subtract>"):
            self.root.bind(ks, self.on_minus)

        # Vari
        self.root.bind("<Configure>", self.on_resize)
        self.root.bind("<f>", self.toggle_fill)
        self.root.bind("<F>", self.toggle_fill)

        # Stato
        self.fill_mode = "white"  # "white" | "blur"
        self.update_mode_label()

        self.img = None
        self.disp_img = None
        self.tk_img = None
        self.image_paths = []
        self.idx = 0

        self.scale = 1.0
        self.img_off = (0, 0)
        self.disp_size = (0, 0)

        self.rect_w = 0
        self.rect_h = 0
        self.rect_center = (0, 0)
        self.dragging = False
        self.drag_offset = (0, 0)

        self.load_folder()

    # ---------- UI helpers ----------
    def update_mode_label(self):
        filler = "BIANCO" if self.fill_mode == "white" else "BLUR"
        self.mode_lbl.config(text=(
            f"Modalità riempimento: {filler}  |  F = cambia  •  "
            "Frecce=sposta (Shift=+veloce)  •  +/-=ridim (Shift=+veloce)  •  Invio/Tab/A=salva  •  Esc=salta"
        ))

    # ---------- File loading ----------
    def load_folder(self):
        folder = filedialog.askdirectory(title="Seleziona cartella con le foto")
        if not folder:
            self.root.after(50, self.root.quit)
            return
        self.image_paths = [
            os.path.join(folder, f) for f in sorted(os.listdir(folder))
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"))
        ]
        if not self.image_paths:
            messagebox.showerror("Nessuna immagine", "La cartella non contiene immagini.")
            self.root.after(50, self.root.quit)
            return
        self.show_image()

    def show_image(self):
        if self.idx >= len(self.image_paths):
            messagebox.showinfo("Fatto", "Tutte le immagini sono state elaborate.")
            self.root.after(50, self.root.quit)
            return

        path = self.image_paths[self.idx]
        try:
            self.img = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showwarning("Errore immagine", f"Impossibile aprire:\n{path}\n{e}\nSi passa alla successiva.")
            self.idx += 1
            self.show_image()
            return

        self.layout_image()

        # ripristina stato se esiste; altrimenti riquadro iniziale
        if not self.apply_saved_state(path):
            self.init_rect()

        self.redraw()

    # ---------- Layout & Drawing ----------
    def canvas_size(self):
        return (max(self.canvas.winfo_width(), WINDOW_MIN[0]),
                max(self.canvas.winfo_height(), WINDOW_MIN[1]))

    def layout_image(self):
        cw, ch = self.canvas_size()
        iw, ih = self.img.size
        self.scale = min(cw / iw, ch / ih)
        disp_w = max(1, int(iw * self.scale))
        disp_h = max(1, int(ih * self.scale))
        self.disp_size = (disp_w, disp_h)
        self.disp_img = self.img.resize((disp_w, disp_h), Image.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(self.disp_img)
        self.img_off = ((cw - disp_w) // 2, (ch - disp_h) // 2)

    def init_rect(self):
        dw, dh = self.disp_size
        rw = int(dw * 0.8)
        rh = int(rw / RATIO)
        if rh > dh:
            rh = int(dh * 0.8)
            rw = int(rh * RATIO)
        self.rect_w, self.rect_h = max(20, rw), max(20, rh)
        cx = self.img_off[0] + dw // 2
        cy = self.img_off[1] + dh // 2
        self.rect_center = (cx, cy)
        self.clamp_rect_to_canvas()

    def rect_coords(self):
        cx, cy = self.rect_center
        w2 = self.rect_w // 2
        h2 = self.rect_h // 2
        return (cx - w2, cy - h2, cx + w2, cy + h2)

    def clamp_rect_to_canvas(self):
        # Mantieni il rettangolo dentro i bordi del canvas (può uscire dalla FOTO)
        x1, y1, x2, y2 = self.rect_coords()
        cw, ch = self.canvas_size()
        dx = dy = 0
        if x1 < 0: dx = -x1
        if y1 < 0: dy = -y1
        if x2 > cw: dx = cw - x2 if dx == 0 else dx
        if y2 > ch: dy = ch - y2 if dy == 0 else dy
        cx, cy = self.rect_center
        self.rect_center = (cx + dx, cy + dy)

        # limiti dimensione: almeno 64px di larghezza, massimo canvas mantenendo ratio
        max_w = min(cw, int(ch * RATIO))
        self.rect_w = max(64, min(self.rect_w, max_w))
        self.rect_h = int(self.rect_w / RATIO)

    def redraw(self):
        # snap per avere linee dritte (no sub-pixel)
        def snap(v): return int(round(v))

        self.canvas.delete("all")

        # immagine
        self.canvas.create_image(self.img_off[0], self.img_off[1], anchor="nw", image=self.tk_img)

        # rettangolo di crop
        x1f, y1f, x2f, y2f = self.rect_coords()
        x1 = snap(x1f); y1 = snap(y1f); x2 = snap(x2f); y2 = snap(y2f)

        # maschera fuori crop
        w, h = self.canvas_size()
        self.canvas.create_rectangle(0, 0, w, y1, fill="#000", stipple="gray25", width=0)
        self.canvas.create_rectangle(0, y2, w, h, fill="#000", stipple="gray25", width=0)
        self.canvas.create_rectangle(0, y1, x1, y2, fill="#000", stipple="gray25", width=0)
        self.canvas.create_rectangle(x2, y1, w, y2, fill="#000", stipple="gray25", width=0)

        # bordo crop
        self.canvas.create_rectangle(x1, y1, x2, y2, outline="#00ff88", width=2)

        # griglia (terzi) con linee dritte
        v1 = snap(x1 + (x2 - x1) / 3.0)
        v2 = snap(x1 + 2 * (x2 - x1) / 3.0)
        h1 = snap(y1 + (y2 - y1) / 3.0)
        h2 = snap(y1 + 2 * (y2 - y1) / 3.0)
        dash_pat = (3, 3)
        self.canvas.create_line(v1, y1, v1, y2, fill="#00ff88", dash=dash_pat, width=1, capstyle="butt", joinstyle="miter")
        self.canvas.create_line(v2, y1, v2, y2, fill="#00ff88", dash=dash_pat, width=1, capstyle="butt", joinstyle="miter")
        self.canvas.create_line(x1, h1, x2, h1, fill="#00ff88", dash=dash_pat, width=1, capstyle="butt", joinstyle="miter")
        self.canvas.create_line(x1, h2, x2, h2, fill="#00ff88", dash=dash_pat, width=1, capstyle="butt", joinstyle="miter")

    # ---------- Mouse ----------
    def on_click(self, e):
        x1, y1, x2, y2 = self.rect_coords()
        if x1 <= e.x <= x2 and y1 <= e.y <= y2:
            self.dragging = True
            self.drag_offset = (e.x - self.rect_center[0], e.y - self.rect_center[1])
        else:
            self.rect_center = (e.x, e.y)
            self.clamp_rect_to_canvas()
            self.redraw()

    def on_drag(self, e):
        if not self.dragging:
            return
        self.rect_center = (e.x - self.drag_offset[0], e.y - self.drag_offset[1])
        self.clamp_rect_to_canvas()
        self.redraw()

    def on_release(self, _e):
        self.dragging = False

    def on_wheel(self, e):
        self.resize_rect_mouse(1 if e.delta > 0 else -1)

    def on_wheel_linux(self, e):
        self.resize_rect_mouse(1 if e.num == 4 else -1)

    def resize_rect_mouse(self, direction):
        factor = SCALE_FACTOR if direction > 0 else (1 / SCALE_FACTOR)
        self.apply_resize_factor(factor)

    # ---------- Tastiera ----------
    def on_confirm_tab(self, event):
        self.on_confirm()
        return "break"  # evita cambio focus di Tab

    def on_arrow(self, e, dx, dy):
        step = ARROW_STEP_FAST if (e.state & 0x0001) else ARROW_STEP  # Shift accelera
        self.rect_center = (self.rect_center[0] + dx*step, self.rect_center[1] + dy*step)
        self.clamp_rect_to_canvas()
        self.redraw()

    def on_plus(self, e):
        fast = bool(e.state & 0x0001)  # Shift
        factor = SCALE_FACTOR_FAST if fast else SCALE_FACTOR
        self.apply_resize_factor(factor)

    def on_minus(self, e):
        fast = bool(e.state & 0x0001)
        factor = (1 / SCALE_FACTOR_FAST) if fast else (1 / SCALE_FACTOR)
        self.apply_resize_factor(factor)

    def apply_resize_factor(self, factor):
        cw, ch = self.canvas_size()
        max_w = min(cw, int(ch * RATIO))
        new_w = int(self.rect_w * factor)
        new_w = max(64, min(new_w, max_w))
        self.rect_w = new_w
        self.rect_h = int(self.rect_w / RATIO)
        self.clamp_rect_to_canvas()
        self.redraw()

    def on_resize(self, _e):
        if self.img is None:
            return
        rect_img_raw = self.rect_in_image_coords_raw()
        self.layout_image()
        x1i, y1i, x2i, y2i = rect_img_raw
        x1d = self.img_off[0] + int(x1i * self.scale)
        y1d = self.img_off[1] + int(y1i * self.scale)
        x2d = self.img_off[0] + int(x2i * self.scale)
        y2d = self.img_off[1] + int(y2i * self.scale)
        self.rect_w = max(1, x2d - x1d)
        self.rect_h = int(self.rect_w / RATIO)
        self.rect_center = ((x1d + x2d)//2, (y1d + y2d)//2)
        self.clamp_rect_to_canvas()
        self.redraw()

    def toggle_fill(self, _e=None):
        self.fill_mode = "blur" if self.fill_mode == "white" else "white"
        self.update_mode_label()

    # ---------- Coordinate helpers ----------
    def rect_in_image_coords_raw(self):
        """
        Converte rettangolo (display) -> coordinate immagine ORIGINALE
        senza clamp: possono essere negative o > size (out-of-bounds).
        """
        x1d, y1d, x2d, y2d = self.rect_coords()
        ox, oy = self.img_off
        x1i = (x1d - ox) / self.scale
        y1i = (y1d - oy) / self.scale
        x2i = (x2d - ox) / self.scale
        y2i = (y2d - oy) / self.scale
        return (x1i, y1i, x2i, y2i)

    # ---------- Crop & Save ----------
    def on_confirm(self, _e=None):
        in_path = self.image_paths[self.idx]

        # 1) coordinate raw (possono uscire dai bordi)
        x1i, y1i, x2i, y2i = self.rect_in_image_coords_raw()
        if x2i <= x1i or y2i <= y1i:
            messagebox.showerror("Selezione non valida", "Il riquadro di selezione è vuoto.")
            return

        sel_w_orig = x2i - x1i
        sel_h_orig = y2i - y1i
        if sel_w_orig <= 1 or sel_h_orig <= 1:
            messagebox.showerror("Selezione non valida", "Selezione troppo piccola.")
            return

        # 2) intersezione con l'immagine originale
        iw, ih = self.img.size
        ix1 = max(0, math.floor(x1i))
        iy1 = max(0, math.floor(y1i))
        ix2 = min(iw, math.ceil(x2i))
        iy2 = min(ih, math.ceil(y2i))

        # 3) scala orig->target
        sx = TARGET_SIZE[0] / sel_w_orig
        sy = TARGET_SIZE[1] / sel_h_orig

        # 4) base di sfondo (white o blur) + incolla parte nitida se esiste intersezione
        if ix2 <= ix1 or iy2 <= iy1:
            out = self.background_only(None)
        else:
            int_w_orig = ix2 - ix1
            int_h_orig = iy2 - iy1
            int_w_tgt = max(1, int(round(int_w_orig * sx)))
            int_h_tgt = max(1, int(round(int_h_orig * sy)))
            region_scaled = self.img.crop((ix1, iy1, ix2, iy2)).resize((int_w_tgt, int_h_tgt), Image.LANCZOS)
            out = self.background_only(region_scaled)

            dx_tgt = int(round((ix1 - x1i) * sx))
            dy_tgt = int(round((iy1 - y1i) * sy))

            src_x1 = max(0, -dx_tgt)
            src_y1 = max(0, -dy_tgt)
            dst_x1 = max(0, dx_tgt)
            dst_y1 = max(0, dy_tgt)

            width  = min(TARGET_SIZE[0] - dst_x1, region_scaled.width  - src_x1)
            height = min(TARGET_SIZE[1] - dst_y1, region_scaled.height - src_y1)

            if width > 0 and height > 0:
                sub = region_scaled.crop((src_x1, src_y1, src_x1 + width, src_y1 + height))
                out.paste(sub, (dst_x1, dst_y1))

        # 5) salva immagine
        self.save_output(out)

        # 6) salva stato (txt) accanto alla sorgente
        self.save_state(in_path, x1i, y1i, x2i, y2i)

        # 7) prossima
        self.next_image()

    def background_only(self, region_scaled_or_none):
        if self.fill_mode == "white" or region_scaled_or_none is None:
            return Image.new("RGB", TARGET_SIZE, "white")
        else:
            base = region_scaled_or_none.resize(TARGET_SIZE, Image.LANCZOS)
            return base.filter(ImageFilter.GaussianBlur(radius=25))

    def save_output(self, out_img):
        in_path = self.image_paths[self.idx]
        base = os.path.splitext(os.path.basename(in_path))[0]
        out_dir = os.path.join(os.path.dirname(in_path), "_export_photopainter_jpg")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{base}_pp.jpg")
        out_img.save(out_path, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        print(f"Salvato: {out_path}")

    # ---------- Stato persistente ----------
    def state_path_for_image(self, img_path: str) -> str:
        d = os.path.dirname(img_path)
        b = os.path.splitext(os.path.basename(img_path))[0]
        return os.path.join(d, f"{b}{STATE_SUFFIX}")

    def save_state(self, img_path: str, x1i, y1i, x2i, y2i):
        iw, ih = self.img.size
        nx1 = x1i / iw
        ny1 = y1i / ih
        nx2 = x2i / iw
        ny2 = y2i / ih
        lines = [
            "# PhotoPainter crop state",
            f"timestamp={int(time.time())}",
            f"image_name={os.path.basename(img_path)}",
            f"image_w={iw}",
            f"image_h={ih}",
            f"rect_x1={x1i:.4f}",
            f"rect_y1={y1i:.4f}",
            f"rect_x2={x2i:.4f}",
            f"rect_y2={y2i:.4f}",
            f"rect_nx1={nx1:.6f}",
            f"rect_ny1={ny1:.6f}",
            f"rect_nx2={nx2:.6f}",
            f"rect_ny2={ny2:.6f}",
            f"target_w={TARGET_SIZE[0]}",
            f"target_h={TARGET_SIZE[1]}",
            f"ratio={RATIO:.6f}",
            f"fill_mode={self.fill_mode}",
        ]
        path = self.state_path_for_image(img_path)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            print(f"Stato salvato: {path}")
        except Exception as e:
            print(f"[WARN] Impossibile salvare stato: {e}")

    def load_kv(self, path: str):
        data = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    data[k.strip()] = v.strip()
        except Exception:
            return None
        return data

    def apply_saved_state(self, img_path: str) -> bool:
        kv_path = self.state_path_for_image(img_path)
        if not os.path.exists(kv_path):
            return False
        kv = self.load_kv(kv_path)
        if not kv:
            return False

        iw, ih = self.img.size

        # riporta fill mode se presente
        if kv.get("fill_mode") in ("white", "blur"):
            self.fill_mode = kv["fill_mode"]
            self.update_mode_label()

        # preferisci coordinate assolute se le dimensioni combaciano
        try:
            saved_w = int(kv.get("image_w", iw))
            saved_h = int(kv.get("image_h", ih))
        except ValueError:
            saved_w, saved_h = iw, ih

        if saved_w == iw and saved_h == ih:
            try:
                x1i = float(kv["rect_x1"]); y1i = float(kv["rect_y1"])
                x2i = float(kv["rect_x2"]); y2i = float(kv["rect_y2"])
            except Exception:
                x1i, y1i, x2i, y2i = self._coords_from_normalized(kv, iw, ih)
        else:
            x1i, y1i, x2i, y2i = self._coords_from_normalized(kv, iw, ih)

        if None in (x1i, y1i, x2i, y2i):
            return False

        # converti a display coords
        x1d = self.img_off[0] + int(x1i * self.scale)
        y1d = self.img_off[1] + int(y1i * self.scale)
        x2d = self.img_off[0] + int(x2i * self.scale)
        y2d = self.img_off[1] + int(y2i * self.scale)

        # ricostruisci rettangolo mantenendo ratio fisso
        w = max(1, x2d - x1d)
        h = int(w / RATIO)
        cx = (x1d + x2d) // 2
        cy = (y1d + y2d) // 2

        self.rect_w = w
        self.rect_h = h
        self.rect_center = (cx, cy)
        self.clamp_rect_to_canvas()
        return True

    def _coords_from_normalized(self, kv, iw, ih):
        try:
            nx1 = float(kv["rect_nx1"]); ny1 = float(kv["rect_ny1"])
            nx2 = float(kv["rect_nx2"]); ny2 = float(kv["rect_ny2"])
            return (nx1 * iw, ny1 * ih, nx2 * iw, ny2 * ih)
        except Exception:
            return (None, None, None, None)

    # ---------- Avanzamento ----------
    def next_image(self):
        self.idx += 1
        self.show_image()

    def on_skip(self, _e=None):
        self.next_image()

if __name__ == "__main__":
    root = tk.Tk()
    app = CropperApp(root)
    root.mainloop()
