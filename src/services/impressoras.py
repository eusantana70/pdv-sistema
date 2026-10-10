"""Lista impressoras térmicas do Windows (M1/M6). Sem falhar fora do Windows."""

from __future__ import annotations


def listar_impressoras() -> list:
    try:
        import win32print  # type: ignore
    except ImportError:
        return []
    try:
        flags = 2  # PRINTER_ENUM_LOCAL | CONNECTIONS
        impressoras = win32print.EnumPrinters(flags)
        return sorted({nome for (_, _, nome, _) in impressoras if nome})
    except Exception:
        return []


def impressora_padrao() -> str:
    try:
        import win32print  # type: ignore
        return win32print.GetDefaultPrinter() or ""
    except Exception:
        return ""
