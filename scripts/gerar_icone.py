"""Gera o ícone do PDV Lumina (.ico) para o executável e os atalhos."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

DESTINO = Path(__file__).resolve().parents[1] / "build_assets" / "pdv_lumina.ico"
TAMANHOS = [16, 24, 32, 48, 64, 128, 256]

VERDE_ESCURO = (17, 48, 34)
VERDE = (44, 122, 75)
LIMA = (159, 232, 112)


def _base(tam: int) -> Image.Image:
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # fundo arredondado
    d.rounded_rectangle([0, 0, tam - 1, tam - 1], radius=int(tam * 0.22), fill=VERDE_ESCURO)
    d.rounded_rectangle(
        [int(tam * 0.06), int(tam * 0.06), int(tam * 0.94), int(tam * 0.94)],
        radius=int(tam * 0.18), fill=VERDE,
    )
    # "telhado" da loja
    d.polygon(
        [(int(tam * 0.17), int(tam * 0.44)), (int(tam * 0.83), int(tam * 0.44)),
         (int(tam * 0.5), int(tam * 0.20))],
        fill=LIMA,
    )
    # corpo
    d.rectangle([int(tam * 0.22), int(tam * 0.45), int(tam * 0.78), int(tam * 0.78)], fill=(240, 255, 246))
    # porta
    d.rectangle([int(tam * 0.43), int(tam * 0.58), int(tam * 0.57), int(tam * 0.78)], fill=VERDE)
    # vitrines
    for x in (0.27, 0.63):
        d.rectangle(
            [int(tam * x), int(tam * 0.51), int(tam * (x + 0.10)), int(tam * 0.63)],
            fill=LIMA,
        )
    return img


def main() -> int:
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    # o .ico guarda as imagens já redesenhadas no tamanho exato de cada entrada
    _base(256).save(
        DESTINO, format="ICO",
        sizes=[(t, t) for t in TAMANHOS],
        append_images=[_base(t) for t in TAMANHOS if t != 256],
    )
    # PNG grande para o instalador
    png = DESTINO.with_suffix(".png")
    _base(256).save(png, format="PNG")
    print(f"icone gerado: {DESTINO}")
    print(f"preview:      {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())