"""Bounded readers adapted from the original Red Alert format implementations.

Copyright 2025 Electronic Arts Inc. Adaptations 2026.
GPL-3.0-or-later with repository LICENSE.md additional terms.
See CODE/{LCWUNCMP,2KEYFRAM,PK,CONST,CRC,MIXFILE}.CPP and
WWFLAT32/WSA/XORDELTA.ASM. No game artwork is included here.
"""
import base64
import struct


def need(ok, message):
    if not ok:
        raise ValueError(message)


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, n):
        need(0 <= n <= len(self.data) - self.pos, "Truncated compressed data")
        result = self.data[self.pos:self.pos + n]
        self.pos += n
        return result

    def byte(self):
        return self.take(1)[0]

    def word(self):
        return int.from_bytes(self.take(2), 'little')


def lcw(data, size):
    """CODE/LCWUNCMP.CPP operation semantics, with added bounds checks."""
    r, out = Reader(data), bytearray()
    while True:
        op = r.byte()
        if op == 0x80:
            need(len(out) == size, "Wrong LCW output size")
            return bytes(out)
        if not op & 0x80:
            count = (op >> 4) + 3
            offset = len(out) - (((op & 15) << 8) | r.byte())
        elif not op & 0x40:
            count = op & 63
            need(len(out) + count <= size, "LCW literal overflow")
            out.extend(r.take(count))
            continue
        elif op == 0xfe:
            count, value = r.word(), r.byte()
            need(len(out) + count <= size, "LCW fill overflow")
            out.extend(bytes([value]) * count)
            continue
        else:
            count = r.word() if op == 0xff else (op & 63) + 3
            offset = r.word()
        need(0 <= offset < len(out) and len(out) + count <= size, "Invalid LCW copy")
        for j in range(count):
            out.append(out[offset + j])  # Copies may overlap.


def xor_delta(base, data):
    """WWFLAT32/WSA/XORDELTA.ASM operation semantics, bounded to base."""
    r, out, pos = Reader(data), bytearray(base), 0
    while True:
        op = r.byte()
        if op == 0:
            count, value, kind = r.byte(), r.byte(), 'run'
        elif op < 0x80:
            count, kind = op, 'dump'
        elif op > 0x80:
            count, kind = op & 127, 'skip'
        else:
            word = r.word()
            if word == 0:
                return bytes(out)
            if word < 0x8000:
                count, kind = word, 'skip'
            elif word & 0x4000:
                count, value, kind = word & 0x3fff, r.byte(), 'run'
            else:
                count, kind = word & 0x3fff, 'dump'
        need(pos + count <= len(out), "XOR delta overflow")
        if kind == 'dump':
            values = r.take(count)
            for j, v in enumerate(values):
                out[pos + j] ^= v
        elif kind == 'run':
            for j in range(count):
                out[pos + j] ^= value
        pos += count


def shp_decode(data):
    """TD/RA SHP, not TS/RA2 SHP. Decode keyframes and both delta forms."""
    need(len(data) >= 14, "Truncated SHP header")
    count, _, _, width, height, _, flags = struct.unpack_from('<7H', data)
    need(0 < count <= 1024 and 0 < width * height <= 65535, "Invalid SHP dimensions")
    need(len(data) >= 14 + (count + 2) * 8, "Truncated SHP directory")
    entries = [struct.unpack_from('<II', data, 14 + i * 8) for i in range(count)]
    by_offset = {a & 0xffffff: i for i, (a, _) in enumerate(entries)}
    cache, active = {}, set()

    def decode(i):
        need(0 <= i < count, "Invalid SHP reference")
        if i in cache:
            return cache[i]
        need(i not in active and len(active) < 128, "Cyclic/deep SHP references")
        active.add(i)
        a, b = entries[i]
        offset, kind = a & 0xffffff, a >> 24
        end = min([v for v in by_offset if v > offset] + [len(data)])
        need(14 + (count + 2) * 8 <= offset < end <= len(data), "Invalid SHP offset")
        if kind == 0x80:
            start = offset + (768 if flags & 1 else 0)
            pixels = lcw(data[start:end], width * height)
        elif kind == 0x40:
            ref = b & 0xffffff
            need(ref in by_offset, "Missing SHP keyframe")
            pixels = xor_delta(decode(by_offset[ref]), data[offset:end])
        elif kind == 0x20:
            # b identifies the initial key-delta frame, not the previous frame.
            need((b & 0xffff) < i, "Invalid SHP delta chain")
            pixels = xor_delta(decode(i - 1), data[offset:end])
        else:
            raise ValueError(f"Unsupported SHP compression {kind:#x}")
        active.remove(i)
        cache[i] = pixels
        return pixels

    return width, height, [decode(i) for i in range(count)]


def mix_hash(name):
    """Original rotate/add filename hash; uppercase, zero-padded DWORDs."""
    data = name.upper().encode('ascii')
    data += b'\0' * (-len(data) % 4)
    result = 0
    for i in range(0, len(data), 4):
        result = (((result << 1) | (result >> 31)) + int.from_bytes(data[i:i + 4], 'little')) & 0xffffffff
    return result


class Slice:
    def __init__(self, parent, offset, size):
        need(0 <= offset <= parent.size and 0 <= size <= parent.size - offset, "Invalid archive extent")
        self.parent, self.offset, self.size = parent, offset, size

    def read(self, offset, size):
        need(0 <= offset <= self.size and 0 <= size <= self.size - offset, "Archive read outside extent")
        return self.parent.read(self.offset + offset, size)


def mix_member(source, name):
    head = source.read(0, 6)
    count = int.from_bytes(head[:2], 'little')
    start = 0 if count else 4
    flags = int.from_bytes(head[:4], 'little') if not count else 0
    if flags & 0x20000:
        from Crypto.Cipher import Blowfish
        # DER integer from CODE/CONST.CPP, public modulus; exponent from PK.H.
        modulus = int.from_bytes(base64.b64decode(
            'AihRvNoIbTn85FZRYNZRcT+i6KpU+maCsEqr3Q5q+LDB5tH7Tz2qQ38V')[2:], 'big')
        block = source.read(4, 80)
        key = b''.join(pow(int.from_bytes(block[i:i + 40], 'little'), 65537, modulus)
                       .to_bytes(40, 'little')[:39] for i in (0, 40))[:56]
        fish = Blowfish.new(key, Blowfish.MODE_ECB)
        count = int.from_bytes(fish.decrypt(source.read(84, 8))[:2], 'little')
        length = ((6 + count * 12 + 7) // 8) * 8
        directory = fish.decrypt(source.read(84, length))
        start = 84 + length
    else:
        count = int.from_bytes(source.read(start, 2), 'little')
        directory = source.read(start, 6 + count * 12)
        start += len(directory)
    data_size = int.from_bytes(directory[2:6], 'little')
    need(start + data_size <= source.size, "Truncated MIX payload")
    wanted = mix_hash(name)
    for i in range(count):
        key, offset, size = struct.unpack_from('<III', directory, 6 + i * 12)
        need(offset + size <= data_size, "Invalid MIX entry")
        if key == wanted:
            return Slice(source, start + offset, size)
    raise ValueError(f"MIX member not found: {name}")
