"""C encoder / Python decoder interoperability. Synthetic memory only."""
import ctypes as C
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zlib
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from mesh_csi_wire import Decoder, decode_frame


class Sample(C.Structure):
    _fields_=[('callback_id',C.c_uint32),('queue_drops',C.c_uint32),
              ('topology_epoch',C.c_uint32),('layer',C.c_uint8),
              ('source_mac',C.c_uint8*6),('node_mac',C.c_uint8*6),
              ('parent_mac',C.c_uint8*6),('meta',C.c_int64*19),
              ('len',C.c_uint16),('first_word_invalid',C.c_uint8),('data',C.c_int8*1024)]


class WireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        source=ROOT/'firmware/mesh_csi_experimental/main/wire.c'
        lib=Path(cls.tmp.name)/'wire.so'
        subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-pedantic',
                        '-shared','-fPIC',str(source),'-o',str(lib)],check=True)
        cls.lib=C.CDLL(str(lib))
        cls.lib.tcsi_encode_sample.argtypes=[C.c_void_p,C.c_size_t,C.c_uint8,C.c_uint32,C.POINTER(Sample)]
        cls.lib.tcsi_encode_sample.restype=C.c_size_t
        cls.lib.tcsi_encode_event.argtypes=[C.c_void_p,C.c_size_t,C.c_uint8,C.c_uint32,C.c_char_p,C.c_size_t]
        cls.lib.tcsi_encode_event.restype=C.c_size_t
        cls.lib.tcsi_budget_fits.argtypes=[C.c_uint32,C.c_uint32,C.c_uint16,C.c_uint32]
        cls.lib.tcsi_budget_fits.restype=C.c_bool
        cls.lib.tcsi_crc32.argtypes=[C.c_void_p,C.c_size_t]
        cls.lib.tcsi_crc32.restype=C.c_uint32

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def sample(self,length=256):
        s=Sample(callback_id=0xffffffff,queue_drops=7,topology_epoch=12,layer=3,
                 len=length,first_word_invalid=1)
        s.source_mac[:]=bytes.fromhex('1a0000000000')
        s.node_mac[:]=bytes.fromhex('204050607080')
        s.parent_mac[:]=bytes.fromhex('123456789abc')
        s.meta[:]=[-128,127,1,7,0,0,0,0,0,0,0,-95,255,11,0,0xffffffff,1,65535,0]
        for i in range(min(length,1024)): s.data[i]=(i%256)-128
        return s

    def encode(self,s=None,seq=0,node=1,cap=1230):
        out=C.create_string_buffer(cap)
        n=self.lib.tcsi_encode_sample(out,cap,node,seq,C.byref(s or self.sample()))
        return out.raw[:n]

    def event(self,text=b'STATUS queue_drops=0',seq=1):
        out=C.create_string_buffer(1230)
        n=self.lib.tcsi_encode_event(out,len(out),1,seq,text,len(text))
        return out.raw[:n]

    def fix_crc(self,frame):
        return bytes(frame[:-4])+struct.pack('<I',zlib.crc32(frame[:-4]))

    def test_crc_matches_standard_vector(self):
        self.assertEqual(self.lib.tcsi_crc32(b'123456789',9),0xcbf43926)

    def test_all_csi_bytes_metadata_flags_and_identity_survive(self):
        s=self.sample(); frame=self.encode(s,0xffffffff); r=decode_frame(frame)
        self.assertEqual(len(frame),462)
        self.assertEqual(r['csi_bytes'],bytes(((i-128)%256) for i in range(256)))
        self.assertEqual(r['callback_id'],0xffffffff)
        self.assertEqual((r['queue_drops'],r['topology_epoch'],r['layer']),(7,12,3))
        self.assertEqual((r['source_mac'],r['node_mac'],r['parent_mac']),('1a:00:00:00:00:00','20:40:50:60:70:80','12:34:56:78:9a:bc'))
        self.assertEqual((r['rssi'],r['noise_floor'],r['local_timestamp']),(-128,-95,0xffffffff))
        self.assertTrue(r['first_word_invalid'])
        self.assertEqual(r['model_use'],'not_authorized')
        self.assertEqual(r['acquisition_quality'],'not_evaluated')

    def test_signed_int64_endpoints_survive(self):
        s=self.sample(2); s.meta[0]=-(1<<63); s.meta[1]=(1<<63)-1
        r=decode_frame(self.encode(s)); self.assertEqual((r['rssi'],r['rate']),(-(1<<63),(1<<63)-1))

    def test_variable_csi_lengths_preserved(self):
        for n in (2,128,256,384,1024):
            with self.subTest(n=n): self.assertEqual(decode_frame(self.encode(self.sample(n)))['len'],n)

    def test_encoder_rejects_invalid_length_flag_node_and_capacity(self):
        for n in (0,1,255,1025):
            with self.subTest(n=n): self.assertEqual(self.encode(self.sample(n)),b'')
        s=self.sample(); s.first_word_invalid=2
        self.assertEqual(self.encode(s),b''); self.assertEqual(self.encode(node=3),b'')
        self.assertEqual(self.encode(cap=461),b'')

    def test_every_single_bit_corruption_rejected(self):
        frame=self.encode()
        for i in range(len(frame)):
            for bit in range(8):
                bad=bytearray(frame); bad[i]^=1<<bit
                with self.assertRaises(ValueError): decode_frame(bytes(bad))

    def test_unknown_version_reserved_and_lengths_rejected_even_with_valid_crc(self):
        for index,value in ((4,2),(5,3),(6,3),(7,1),(14,1),(12,255),(201,2)):
            bad=bytearray(self.encode()); bad[index]=value
            with self.subTest(index=index),self.assertRaises(ValueError): decode_frame(self.fix_crc(bad))

    def test_event_roundtrip_and_invalid_text(self):
        self.assertEqual(decode_frame(self.event())['event'],'STATUS queue_drops=0')
        for text in (b'',b'x'*257,b'\x00',b'\n',b'\xff'):
            with self.subTest(text=text[:8]): self.assertEqual(self.event(text),b'')

    def test_incremental_splits_and_consecutive_frames(self):
        blob=self.encode(seq=0)+self.event(seq=1)+self.encode(seq=2)
        for size in (1,2,15,16,19,20,461,462,4096):
            d=Decoder(); out=[]
            for i in range(0,len(blob),size): out.extend(d.feed(blob[i:i+size]))
            d.finish(); self.assertEqual([r['frame_seq'] for r in out],[0,1,2])

    def test_rejected_prefix_tail_and_crc_are_not_silently_resynchronized(self):
        for blob in (b'ROM\n'+self.encode(),self.encode()[:-1],self.encode()[:-4]+b'xxxx'):
            d=Decoder()
            with self.assertRaises(ValueError): d.feed(blob); d.finish()
            with self.assertRaises(ValueError): d.feed(self.encode())

    def test_budget_prevents_115200_and_oversize_100hz(self):
        self.assertFalse(self.lib.tcsi_budget_fits(115200,100,256,20000))
        self.assertTrue(self.lib.tcsi_budget_fits(921600,100,256,20000))
        self.assertFalse(self.lib.tcsi_budget_fits(921600,100,1024,20000))
        for baud,hz,n in ((0,100,256),(921600,0,256),(921600,101,256),(921600,100,0),(921600,100,255)):
            self.assertFalse(self.lib.tcsi_budget_fits(baud,hz,n,20000))

    def test_synthetic_hundred_frames_are_bytes_not_evidence_of_rate(self):
        d=Decoder(); rows=d.feed(b''.join(self.encode(seq=i) for i in range(100))); d.finish()
        self.assertEqual(len(rows),100)
        self.assertEqual({r['acquisition_quality'] for r in rows},{'not_evaluated'})


if __name__=='__main__': unittest.main()
