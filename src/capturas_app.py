"""Capturas de la aplicación para el informe (entrenamiento y revisión).

Usa PrintWindow de Windows: copia solo la ventana del programa, aunque otras ventanas
estén encima, de modo que no se captura nada más de la pantalla.
"""
import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

from PIL import Image

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))
import app as A
import modelo as M

DEST = Path("informe/tesis/figuras")
user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32


def foto(ventana, archivo):
    ventana.update_idletasks(); ventana.update()
    hwnd = user32.GetParent(ventana.winfo_id()) or ventana.winfo_id()
    r = wintypes.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc_v = user32.GetWindowDC(hwnd)
    hdc = gdi32.CreateCompatibleDC(hdc_v)
    bmp = gdi32.CreateCompatibleBitmap(hdc_v, w, h)
    gdi32.SelectObject(hdc, bmp)
    user32.PrintWindow(hwnd, hdc, 2)                       # 2 = PW_RENDERFULLCONTENT

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]
    bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(hdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1).save(DEST / archivo)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(hdc); user32.ReleaseDC(hwnd, hdc_v)


w = A.App()
w.geometry("1420x600")
w.update()
w._mostrar_entrenamiento(M.entrenar("exportBIMBO.XLSX", "salidas/03_marcado.xlsx"))
w.ventana_entrenamiento.geometry("900x640")
foto(w.ventana_entrenamiento, "app_entrenar.png")
w.ventana_entrenamiento.destroy()
w._mostrar_alertas(M.revisar("exportBIMBO.XLSX"))
foto(w, "app_revisar.png")
w.destroy()
print("ok")
