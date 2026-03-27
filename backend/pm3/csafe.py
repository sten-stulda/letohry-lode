from __future__ import annotations

from dataclasses import dataclass


FRAME_START = 0xF1
FRAME_END = 0xF2
FRAME_ESCAPE = 0xF3


@dataclass(slots=True)
class CSAFECommand:
    command_id: int
    payload: bytes = b""


def checksum(payload: bytes) -> int:
    value = 0
    for byte in payload:
        value ^= byte
    return value


def _escape(payload: bytes) -> bytes:
    escaped = bytearray()
    for byte in payload:
        if byte in {FRAME_START, FRAME_END, FRAME_ESCAPE}:
            escaped.extend((FRAME_ESCAPE, byte ^ 0x20))
        else:
            escaped.append(byte)
    return bytes(escaped)


def _unescape(payload: bytes) -> bytes:
    unescaped = bytearray()
    escaped = False
    for byte in payload:
        if escaped:
            unescaped.append(byte ^ 0x20)
            escaped = False
            continue
        if byte == FRAME_ESCAPE:
            escaped = True
            continue
        unescaped.append(byte)
    return bytes(unescaped)


def build_frame(*commands: CSAFECommand) -> bytes:
    payload = bytearray()
    for command in commands:
        payload.extend((command.command_id, len(command.payload)))
        payload.extend(command.payload)
    framed_payload = _escape(bytes(payload) + bytes((checksum(payload),)))
    return bytes((FRAME_START,)) + framed_payload + bytes((FRAME_END,))


def parse_frame(frame: bytes) -> bytes:
    if len(frame) < 3 or frame[0] != FRAME_START or frame[-1] != FRAME_END:
        raise ValueError("Invalid CSAFE frame markers.")

    payload = _unescape(frame[1:-1])
    message, received_checksum = payload[:-1], payload[-1]
    if checksum(message) != received_checksum:
        raise ValueError("CSAFE checksum mismatch.")
    return message