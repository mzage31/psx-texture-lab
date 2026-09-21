import os
import argparse
import tkinter as tk
from PIL import Image, ImageTk


def convert_to_psx_palette(input_path, output_path, colors, dither, width, height, aspect_ratio, compression_level, preview):
    original = Image.open(input_path).convert("RGB")
    img = original.copy()

    # Resize using explicit dimensions or a target aspect ratio.
    if aspect_ratio:
        try:
            ar_width, ar_height = map(int, aspect_ratio.split(":"))
            if ar_width <= 0 or ar_height <= 0:
                raise ValueError
        except ValueError:
            raise ValueError("--ar must use a positive W:H ratio, e.g. 1:1 or 16:9")

        if width > 0:
            height = max(1, round(width * ar_height / ar_width))
        elif height > 0:
            width = max(1, round(height * ar_width / ar_height))
        else:
            scale = min(original.width / ar_width, original.height / ar_height)
            width = max(1, round(ar_width * scale))
            height = max(1, round(ar_height * scale))
    elif width > 0 or height > 0:
        if width <= 0:
            width = max(1, round(original.width * height / original.height))
        elif height <= 0:
            height = max(1, round(original.height * width / original.width))

    if width > 0 and height > 0:
        img = img.resize((width, height), Image.Resampling.NEAREST)

    extension = os.path.splitext(output_path)[1].lower()

    # Strong PNG compression also reduces palette size, trading color detail
    # for smaller files. The --colors value remains the upper limit.
    effective_colors = colors
    if extension not in (".jpg", ".jpeg") and compression_level is not None:
        palette_limits = (256, 256, 192, 128, 96, 64, 48, 32, 24, 16)
        effective_colors = min(colors, palette_limits[compression_level])

    # Quantize to palette
    palette_img = img.quantize(
        colors=effective_colors,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    )

    # Use the output extension to select safe, format-specific compression.
    if extension in (".jpg", ".jpeg"):
        jpeg_level = 0 if compression_level is None else compression_level
        jpeg_options = {
            "format": "JPEG",
            "quality": max(10, 95 - jpeg_level * 9),
            "subsampling": 2 if jpeg_level >= 3 else 0,
        }
        if jpeg_level > 0:
            jpeg_options["optimize"] = True
        if jpeg_level >= 5:
            jpeg_options["progressive"] = True
        palette_img.convert("RGB").save(output_path, **jpeg_options)
    else:
        png_level = 6 if compression_level is None else compression_level
        png_options = {
            "format": "PNG",
            "optimize": compression_level is not None and compression_level > 0,
            "compress_level": png_level,
        }
        palette_img.save(output_path, **png_options)

    size_kb = os.path.getsize(output_path) // 1024
    print(f"Saved: {output_path} ({size_kb} KB)")

    if preview:
        show_preview(original, palette_img.convert("RGB"))


# ------------------ TKINTER VIEWER ------------------

class SyncViewer:
    def __init__(self, img1, img2):
        self.root = tk.Tk()
        self.root.title("PSX Texture Compare")

        self.img1 = img1
        self.img2 = img2

        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0

        self.canvas1 = tk.Canvas(self.root, bg="black")
        self.canvas2 = tk.Canvas(self.root, bg="black")

        self.canvas1.pack(side="left", fill="both", expand=True)
        self.canvas2.pack(side="right", fill="both", expand=True)

        # Image handles
        self.tk1 = None
        self.tk2 = None
        self.img_item1 = None
        self.img_item2 = None

        self.last_x = 0
        self.last_y = 0

        self.update_zoomed_images()

        # Zoom
        self.root.bind("<MouseWheel>", self.on_zoom)

        # Pan (shared)
        for canvas in (self.canvas1, self.canvas2):
            canvas.bind("<ButtonPress-1>", self.start_pan)
            canvas.bind("<B1-Motion>", self.pan)

        self.root.mainloop()

    def update_zoomed_images(self):
        """Expensive: only when zoom changes"""
        w = int(self.img1.width * self.zoom)
        h = int(self.img1.height * self.zoom)

        resized1 = self.img1.resize((w, h), Image.Resampling.NEAREST)
        resized2 = self.img2.resize((w, h), Image.Resampling.NEAREST)

        self.tk1 = ImageTk.PhotoImage(resized1)
        self.tk2 = ImageTk.PhotoImage(resized2)

        self.canvas1.delete("all")
        self.canvas2.delete("all")

        self.img_item1 = self.canvas1.create_image(
            self.offset_x, self.offset_y, anchor="nw", image=self.tk1
        )
        self.img_item2 = self.canvas2.create_image(
            self.offset_x, self.offset_y, anchor="nw", image=self.tk2
        )

    def update_position(self):
        """Cheap: move images without redraw"""
        w1 = self.canvas1.winfo_width()

        self.canvas1.coords(self.img_item1, self.offset_x, self.offset_y)
        self.canvas2.coords(self.img_item2, self.offset_x - w1, self.offset_y)

    def on_zoom(self, event):
        old_zoom = self.zoom

        scale = 1.1 if event.delta > 0 else 0.9
        self.zoom *= scale
        self.zoom = max(0.1, min(self.zoom, 10))

        if abs(self.zoom - old_zoom) < 1e-5:
            return

        # Zoom towards mouse position (important for UX)
        cx = event.x
        cy = event.y

        self.offset_x = cx - (cx - self.offset_x) * scale
        self.offset_y = cy - (cy - self.offset_y) * scale

        self.update_zoomed_images()

    def start_pan(self, event):
        self.last_x = event.x
        self.last_y = event.y

    def pan(self, event):
        dx = event.x - self.last_x
        dy = event.y - self.last_y

        self.offset_x += dx
        self.offset_y += dy

        self.last_x = event.x
        self.last_y = event.y

        self.update_position()


def show_preview(img1, img2):
    SyncViewer(img1, img2)

# ------------------ CLI ------------------


def main():
    parser = argparse.ArgumentParser(
        description="Convert image to PSX-style 8-bit PNG",
        add_help=False
    )

    parser.add_argument("--help", action="help", help="Show help")

    parser.add_argument("-i", "--input", required=True)
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("-c", "--colors", type=int, default=256)
    parser.add_argument("-d", "--dither", action="store_true")
    parser.add_argument("-w", "--width", type=int, default=0)
    parser.add_argument("-h", "--height", type=int, default=0)
    parser.add_argument("--ar", metavar="W:H", help="Target aspect ratio, e.g. 1:1 or 16:9")
    parser.add_argument(
        "--compression",
        type=int,
        choices=range(10),
        metavar="LEVEL",
        help="Compression level from 0 to 9; higher levels trade image quality for size"
    )
    parser.add_argument("-p", "--preview", action="store_true")

    args = parser.parse_args()

    convert_to_psx_palette(
        args.input,
        args.output,
        args.colors,
        args.dither,
        args.width,
        args.height,
        args.ar,
        args.compression,
        args.preview
    )


if __name__ == "__main__":
    main()
