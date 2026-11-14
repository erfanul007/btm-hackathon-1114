"""Offline reassembly helpers for encode/fragment/batch phases."""
import base64
import re

_B64 = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")
_HEX = re.compile(r"\b(?:[0-9a-fA-F]{2}){6,}\b")


def decode_b64(replies):
    out = []
    for r in replies:
        for tok in _B64.findall(r):
            try:
                out.append(base64.b64decode(tok).decode("utf-8", "ignore"))
            except Exception:  # noqa: BLE001
                pass
    return " ".join(out)


def decode_hex(replies):
    out = []
    for r in replies:
        for tok in _HEX.findall(r):
            try:
                out.append(bytes.fromhex(tok).decode("utf-8", "ignore"))
            except Exception:  # noqa: BLE001
                pass
    return " ".join(out)


def join_text(replies):
    return "  ||  ".join(replies)
