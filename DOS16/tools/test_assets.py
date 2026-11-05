"""Synthetic format fixtures only: no commercial artwork needed by CI."""
import io
from pathlib import Path
import struct
import sys
import unittest
from convert_tank import FileSource, DiscSource, MAGIC, pack_frame, reduce_frame, BODY_SHAPE
from ra_formats import Slice, lcw, xor_delta, shp_decode, mix_hash, mix_member


class Formats(unittest.TestCase):
    def test_lcw(self):
        self.assertEqual(lcw(b'\x83ABC\x00\x03\x80', 6), b'ABCABC')
        self.assertEqual(lcw(b'\x81Q\x00\x01\x80', 4), b'QQQQ')
        self.assertEqual(lcw(b'\xfe\x04\0Z\x80', 4), b'ZZZZ')
        self.assertEqual(lcw(b'\x83ABC\xc0\0\0\x80', 6), b'ABCABC')
        self.assertEqual(lcw(b'\x83ABC\xff\x03\0\0\0\x80', 6), b'ABCABC')
        for stream in (b'', b'\x80', b'\x00\x01\x80', b'\xfe\xff\xffX\x80', b'\x83A'):
            with self.assertRaises(ValueError):
                lcw(stream, 4)

    def test_xor(self):
        stop = b'\x80\0\0'
        self.assertEqual(xor_delta(bytes(6), b'\x02AB\x81\0\x02C' + stop), b'AB\0CC\0')
        self.assertEqual(xor_delta(bytes(6), b'\x80\x02\0\x80\x02\x80AB' + stop), b'\0\0AB\0\0')
        self.assertEqual(xor_delta(bytes(3), b'\x80\x03\xc0Z' + stop), b'ZZZ')
        self.assertEqual(xor_delta(b'A', b'\x01\x01' + stop), b'@')
        for stream in (b'', b'\x82', b'\x02AB', b'\0\x02A'):
            with self.assertRaises(ValueError):
                xor_delta(bytes(1), stream)

    def test_shp_delta_chain_and_validation(self):
        offset = 14 + 5 * 8
        key = b'\x84ABCD\x80'
        delta = b'\x81\x01\x01\x80\0\0'
        chain = b'\x82\x01\x01\x80\0\0'
        header = struct.pack('<7H', 3, 0, 0, 2, 2, 6, 0)
        entries = [(0x80000000 | offset, 0),
                   (0x40000000 | (offset + len(key)), 0x80000000 | offset),
                   (0x20000000 | (offset + len(key) + len(delta)), 0x48000001), (0, 0), (0, 0)]
        data = header + b''.join(struct.pack('<II', *e) for e in entries) + key + delta + chain
        self.assertEqual(shp_decode(data), (2, 2, [b'ABCD', b'ACCD', b'ACBD']))
        broken = bytearray(data)
        struct.pack_into('<I', broken, 14 + 8 + 4, 0x40000000 | (offset + len(key)))
        with self.assertRaises(ValueError):
            shp_decode(broken)
        for bad in (b'', data[:25], data[:-3]):
            with self.assertRaises(ValueError):
                shp_decode(bad)

    def test_mix(self):
        self.assertEqual(mix_hash('abcd'), 0x44434241)
        self.assertEqual(mix_hash('a'), 65)
        payload = b'demo'
        raw = struct.pack('<HI', 1, 4) + struct.pack('<III', mix_hash('tank.shp'), 0, 4) + payload
        for data in (raw, b'\0\0\0\0' + raw):
            source = FileSource(io.BytesIO(data))
            entry = mix_member(source, 'TANK.SHP')
            self.assertEqual(entry.read(0, entry.size), payload)
            with self.assertRaises(ValueError):
                mix_member(source, 'absent')
            with self.assertRaises(ValueError):
                entry.read(3, 2)
        with self.assertRaises(ValueError):
            mix_member(FileSource(io.BytesIO(raw[:-1])), 'TANK.SHP')

    def test_disc_sector_read(self):
        iso = bytearray(20 * 2048)
        iso[16 * 2048:16 * 2048 + 7] = b'\1CD001\1'
        iso[17 * 2048 - 2:17 * 2048 + 2] = b'ABCD'
        raw = b''.join(bytes(16) + iso[i:i + 2048] + bytes(288) for i in range(0, len(iso), 2048))
        for data in (iso, raw):
            disc = DiscSource(FileSource(io.BytesIO(data)))
            self.assertEqual(disc.read(17 * 2048 - 2, 4), b'ABCD')
        with self.assertRaises(ValueError):
            Slice(FileSource(io.BytesIO(b'ab')), 1, 2)

    def test_palette_mask_and_facing(self):
        # Opaque black must remain distinguishable from transparency.
        self.assertEqual(pack_frame([None, 0, 15, None, None, None, None, None]), b'\0\xf0\0\0\x60')
        palette = bytes(768)
        self.assertEqual(reduce_frame(bytes([0, 12, 4, 12]), 2, 2, 2, 2, palette, unit=True),
                         [None, 0, None, 0])
        self.assertEqual([BODY_SHAPE[i * 4] for i in range(8)], [0, 28, 24, 20, 16, 12, 8, 4])


def fixture(path):
    frames = []
    for f in range(9):
        width, height = (32, 24) if f == 8 else (16, 16)
        frames.append(pack_frame([None if (x + y) % 5 == 0 else (x + y + f) % 16
                                  for y in range(height) for x in range(width)]))
    Path(path).write_bytes(MAGIC + b''.join(frames))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--fixture':
        fixture(sys.argv[2])
    else:
        unittest.main()
