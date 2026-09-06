"""
Regenera un PDF de docs/ a partir de su HTML.

Uso:   python docs/generar_pdf.py                          → documentacion-proyecto.html
       python docs/generar_pdf.py informe-sesgo-muestreo.html

Sin argumentos imprime el documento integral, que es el caso de siempre.
Con un nombre de archivo imprime ese, dejando el PDF al lado con el mismo
nombre. Sirve para los informes puntuales que viven aparte del documento
integral sin mezclarse con él.

No hace falta instalar nada: imprime con el Chrome o el Edge que ya está
en la máquina, en modo headless. Se eligió esa vía en lugar de pandoc,
wkhtmltopdf o LaTeX justamente para que cualquier integrante del grupo
pueda regenerar el PDF sin instalar un toolchain.

El documento es VIVO: cada avance relevante del proyecto se edita en
documentacion-proyecto.html —agregando lo nuevo y borrando lo que dejó de
ser cierto— y después se corre este script.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
FUENTE = AQUI / (sys.argv[1] if len(sys.argv) > 1
                 else "documentacion-proyecto.html")
DESTINO = FUENTE.with_suffix(".pdf")

# Rutas habituales en Windows. El primero que exista es el que se usa.
NAVEGADORES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def buscar_navegador() -> str:
    for ruta in NAVEGADORES:
        if Path(ruta).exists():
            return ruta
    raise SystemExit(
        "No se encontró Chrome ni Edge. Instalá uno de los dos, o agregá su "
        "ruta a la lista NAVEGADORES de este script.")


def main() -> None:
    if not FUENTE.exists():
        raise SystemExit(f"No existe {FUENTE}")

    navegador = buscar_navegador()
    print(f"Navegador : {navegador}")
    print(f"Fuente    : {FUENTE.name} ({FUENTE.stat().st_size // 1024} KB)")

    cmd = [
        navegador,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        f"--print-to-pdf={DESTINO}",
        FUENTE.as_uri(),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    if not DESTINO.exists():
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        raise SystemExit("El navegador no generó el PDF.")

    print(f"PDF       : {DESTINO.name} "
          f"({DESTINO.stat().st_size // 1024} KB)  OK")


if __name__ == "__main__":
    main()
