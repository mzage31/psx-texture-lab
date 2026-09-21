import base64
import json
import os
import re
import tempfile
import uuid
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image

from PSXTexture import convert_to_psx_palette


HOST = "127.0.0.1"
PORT = 8765
ROOT = Path(__file__).resolve().parent
TEMP_DIR = Path(tempfile.gettempdir()) / "psx_texture_playground"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


class PlaygroundHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        request_path = urlsplit(self.path).path
        if request_path == "/":
            self.path = "/PSXTexture.html"
        if request_path.startswith("/result/") or request_path.startswith("/download/"):
            return self.serve_result(request_path, request_path.startswith("/download/"))
        return super().do_GET()

    def do_POST(self):
        if self.path != "/convert":
            return self.send_json({"error": "Not found"}, 404)

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 35 * 1024 * 1024:
                raise ValueError("Upload must be between 1 byte and 35 MB")

            data = json.loads(self.rfile.read(length))
            image_data = data.get("image", "")
            if "," not in image_data:
                raise ValueError("Please select an image")

            width = bounded_int(data.get("width"), 0, 16384, "Width", 0)
            height = bounded_int(data.get("height"), 0, 16384, "Height", 0)
            colors = bounded_int(data.get("colors"), 2, 256, "Colors", 256)
            compression = bounded_int(data.get("compression"), 0, 9, "Compression", 6)
            aspect_ratio = str(data.get("aspectRatio", "")).strip() or None
            if aspect_ratio and not re.fullmatch(r"[1-9]\d*:[1-9]\d*", aspect_ratio):
                raise ValueError("Aspect ratio must look like 1:1 or 16:9")

            output_format = str(data.get("format", "png")).lower()
            if output_format not in ("png", "jpg"):
                raise ValueError("Output format must be PNG or JPG")

            raw = base64.b64decode(image_data.split(",", 1)[1], validate=True)
            token = uuid.uuid4().hex
            input_path = TEMP_DIR / f"{token}.input"
            output_path = TEMP_DIR / f"{token}.{output_format}"
            input_path.write_bytes(raw)

            convert_to_psx_palette(
                str(input_path),
                str(output_path),
                colors,
                bool(data.get("dither")),
                width,
                height,
                aspect_ratio,
                compression,
                False,
            )

            with Image.open(output_path) as result:
                result_width, result_height = result.size

            self.send_json({
                "url": f"/result/{output_path.name}",
                "downloadUrl": f"/download/{output_path.name}",
                "inputBytes": len(raw),
                "outputBytes": output_path.stat().st_size,
                "width": result_width,
                "height": result_height,
            })
        except Exception as error:
            self.send_json({"error": str(error)}, 400)

    def serve_result(self, request_path, download):
        name = request_path.rsplit("/", 1)[-1]
        if not re.fullmatch(r"[a-f0-9]{32}\.(png|jpg)", name):
            return self.send_error(404)
        path = TEMP_DIR / name
        if not path.is_file():
            return self.send_error(404)

        content_type = "image/png" if path.suffix == ".png" else "image/jpeg"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="psx-texture{path.suffix}"')
        self.end_headers()
        with path.open("rb") as file:
            self.wfile.write(file.read())

    def send_json(self, value, status=200):
        payload = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def bounded_int(value, minimum, maximum, label, default):
    if value in (None, ""):
        return default
    number = int(value)
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    print(f"PSX Texture Playground: {url}")
    print(f"Temporary results: {TEMP_DIR}")
    print("Press Ctrl+C to stop.")
    webbrowser.open(url)
    ThreadingHTTPServer((HOST, PORT), PlaygroundHandler).serve_forever()
