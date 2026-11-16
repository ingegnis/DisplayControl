"""Small ctypes binding for the 64-bit NDI receive / frame-sync C API.

No NDI SDK binaries or headers are distributed here. Install a licensed runtime
separately. Buffers returned by NDI are copied before being freed. This module
uses only Python's standard library. See SOURCES.md for the ABI documentation.
"""
from __future__ import annotations
import array
import ctypes as C
import ctypes.util
import os
from pathlib import Path
import platform
import threading
import time


class NDIError(RuntimeError):
    pass


class Source(C.Structure):
    _fields_ = [('name', C.c_char_p), ('url', C.c_char_p)]


class FindSettings(C.Structure):
    _fields_ = [('show_local', C.c_bool), ('groups', C.c_char_p), ('extra_ips', C.c_char_p)]


class RecvSettings(C.Structure):
    _fields_ = [('source', Source), ('color', C.c_int), ('bandwidth', C.c_int),
                ('allow_fields', C.c_bool), ('name', C.c_char_p)]


class VideoFrame(C.Structure):
    _fields_ = [('width', C.c_int), ('height', C.c_int), ('fourcc', C.c_uint32),
                ('fps_n', C.c_int), ('fps_d', C.c_int), ('aspect', C.c_float),
                ('frame_format', C.c_int), ('timecode', C.c_int64), ('data', C.c_void_p),
                ('stride', C.c_int), ('metadata', C.c_char_p), ('timestamp', C.c_int64)]


class AudioFrame(C.Structure):
    _fields_ = [('sample_rate', C.c_int), ('channels', C.c_int), ('samples', C.c_int),
                ('timecode', C.c_int64), ('data', C.c_void_p), ('stride', C.c_int),
                ('metadata', C.c_char_p), ('timestamp', C.c_int64)]


class Performance(C.Structure):
    _fields_ = [('video', C.c_int64), ('audio', C.c_int64), ('metadata', C.c_int64)]


def fourcc(value: str) -> int:
    return int.from_bytes(value.encode('ascii'), 'little')


def copy_video(frame: VideoFrame) -> tuple[bytes, int, int, str]:
    """Copy packed rows. Reject unexpected formats and unsafe buffer dimensions."""
    formats = {fourcc('BGRX'): 'bgr0', fourcc('BGRA'): 'bgra',
               fourcc('RGBX'): 'rgb0', fourcc('RGBA'): 'rgba', fourcc('UYVY'): 'uyvy422'}
    if frame.fourcc not in formats:
        raise NDIError('Formato video NDI non supportato: ' + hex(frame.fourcc))
    if not frame.data or not (2 <= frame.width <= 8192 and 2 <= frame.height <= 4320):
        raise NDIError('Dimensioni o buffer NDI non validi.')
    pixel_bytes = 2 if frame.fourcc == fourcc('UYVY') else 4
    row = frame.width * pixel_bytes
    stride = frame.stride or row
    if stride < row or stride > row + 65536:
        raise NDIError('Stride video NDI non valido.')
    if stride == row:
        data = C.string_at(frame.data, row * frame.height)
    else:
        data = b''.join(C.string_at(frame.data + y * stride, row) for y in range(frame.height))
    return data, frame.width, frame.height, formats[frame.fourcc]


def copy_audio(frame: AudioFrame, requested_samples: int = 960) -> bytes:
    """Planar float -> interleaved stereo float32. No numpy dependency."""
    if not frame.data or not frame.samples:
        return b'\0' * requested_samples * 8
    if frame.sample_rate != 48000 or frame.samples != requested_samples or frame.channels != 2:
        raise NDIError('Frame-sync audio: formato diverso da stereo 48 kHz richiesto.')
    if frame.stride < frame.samples * 4 or frame.stride > 16 * 1024 * 1024:
        raise NDIError('Stride audio NDI non valido.')
    left, right = array.array('f'), array.array('f')
    left.frombytes(C.string_at(frame.data, frame.samples * 4))
    right.frombytes(C.string_at(frame.data + frame.stride, frame.samples * 4))
    out = array.array('f', [0.0]) * (frame.samples * 2)
    out[0::2], out[1::2] = left, right
    if os.sys.byteorder != 'little':
        out.byteswap()
    return out.tobytes()


class Runtime:
    def __init__(self, root: Path, library: str = '', extra_ips: str = ''):
        self.root = Path(root)
        self.explicit_library = library or os.environ.get('CARISMA_NDI_LIBRARY', '')
        self.extra_ips = extra_ips
        self.lib = None
        self.path = ''
        self.finder = None
        self.error = ''
        self.lock = threading.RLock()
        self._dll_dirs = []
        self._loaded = False
        self._find_strings = []

    def candidates(self):
        if self.explicit_library:
            yield self.explicit_library
            return
        if os.name == 'nt':
            name = 'Processing.NDI.Lib.x64.dll'
            yield str(self.root / 'runtime' / name)
            for env in ['NDI_RUNTIME_DIR_V6', 'NDI_RUNTIME_DIR_V5', 'NDI_RUNTIME_DIR_V4']:
                if os.environ.get(env):
                    yield str(Path(os.environ[env]) / name)
            pf = Path(os.environ.get('ProgramFiles', 'C:/Program Files'))
            for base in ['NDI/NDI 6 Runtime', 'NDI/NDI 6 SDK/Bin/x64',
                         'NDI/NDI 6 Tools/Runtime', 'NDI/NDI 5 Runtime']:
                yield str(pf / base / name)
        elif platform.system() == 'Darwin':
            for base in [self.root / 'runtime', Path('/usr/local/lib')]:
                yield str(base / 'libndi.dylib')
        else:
            arch = platform.machine()
            for base in [self.root / 'runtime', Path('/usr/local/lib'),
                         Path('/usr/lib') / (arch + '-linux-gnu')]:
                for name in ['libndi.so.6', 'libndi.so.5', 'libndi.so']:
                    yield str(base / name)
            found = ctypes_find_library('ndi')
            if found:
                yield found

    def load(self):
        with self.lock:
            if self._loaded:
                if self.lib is None:
                    raise NDIError(self.error)
                return self
            self._loaded = True
            if C.sizeof(C.c_void_p) != 8:
                self.error = 'Serve Python a 64 bit per il runtime NDI.'
                raise NDIError(self.error)
            errors = []
            for path in self.candidates():
                if os.path.isabs(path) and not Path(path).is_file():
                    continue
                try:
                    if os.name == 'nt' and os.path.isabs(path) and hasattr(os, 'add_dll_directory'):
                        self._dll_dirs.append(os.add_dll_directory(str(Path(path).parent)))
                    lib = C.CDLL(path)
                    self._bind(lib)
                    if not lib.NDIlib_initialize():
                        raise NDIError('Inizializzazione NDI fallita: verificare CPU e runtime.')
                    self.lib, self.path = lib, path
                    self.error = ''
                    return self
                except (OSError, AttributeError, NDIError) as exc:
                    errors.append(str(exc))
            self.error = ('Runtime NDI non disponibile. Installa il runtime/SDK ufficiale a 64 bit '
                          'e imposta CARISMA_NDI_LIBRARY; poi riavvia il server.')
            if errors:
                self.error += ' Dettaglio: ' + errors[-1][:350]
            raise NDIError(self.error)

    @staticmethod
    def _bind(lib):
        signatures = {
            'NDIlib_initialize': (C.c_bool, []), 'NDIlib_destroy': (None, []),
            'NDIlib_version': (C.c_char_p, []),
            'NDIlib_find_create_v2': (C.c_void_p, [C.POINTER(FindSettings)]),
            'NDIlib_find_get_current_sources': (C.POINTER(Source), [C.c_void_p, C.POINTER(C.c_uint32)]),
            'NDIlib_find_destroy': (None, [C.c_void_p]),
            'NDIlib_recv_create_v3': (C.c_void_p, [C.POINTER(RecvSettings)]),
            'NDIlib_recv_destroy': (None, [C.c_void_p]),
            'NDIlib_recv_get_performance': (None, [C.c_void_p, C.POINTER(Performance), C.POINTER(Performance)]),
            'NDIlib_recv_get_no_connections': (C.c_int, [C.c_void_p, C.c_uint32]),
            'NDIlib_framesync_create': (C.c_void_p, [C.c_void_p]),
            'NDIlib_framesync_destroy': (None, [C.c_void_p]),
            'NDIlib_framesync_capture_video': (None, [C.c_void_p, C.POINTER(VideoFrame), C.c_int]),
            'NDIlib_framesync_free_video': (None, [C.c_void_p, C.POINTER(VideoFrame)]),
            'NDIlib_framesync_capture_audio': (None, [C.c_void_p, C.POINTER(AudioFrame), C.c_int, C.c_int, C.c_int]),
            'NDIlib_framesync_free_audio': (None, [C.c_void_p, C.POINTER(AudioFrame)]),
        }
        for name, (result, args) in signatures.items():
            fn = getattr(lib, name)
            fn.restype, fn.argtypes = result, args

    def sources(self):
        self.load()
        with self.lock:
            if not self.finder:
                ips = self.extra_ips.encode() if self.extra_ips else None
                self._find_strings = [ips]
                settings = FindSettings(True, None, ips)
                self.finder = self.lib.NDIlib_find_create_v2(C.byref(settings))
                if not self.finder:
                    raise NDIError('Impossibile creare il finder NDI. Verifica Avahi su Linux.')
            count = C.c_uint32()
            data = self.lib.NDIlib_find_get_current_sources(self.finder, C.byref(count))
            if count.value > 10000:
                raise NDIError('Lista sorgenti NDI non valida.')
            return [{'name': (data[i].name or b'').decode('utf-8', 'replace'),
                     'address': (data[i].url or b'').decode('utf-8', 'replace')}
                    for i in range(count.value) if data and data[i].name]

    def status(self):
        try:
            self.load()
            version = self.lib.NDIlib_version()
            return {'available': True, 'version': (version or b'').decode('utf-8', 'replace'), 'error': ''}
        except NDIError as exc:
            return {'available': False, 'version': '', 'error': str(exc)}

    def close(self):
        with self.lock:
            if self.lib:
                if self.finder:
                    self.lib.NDIlib_find_destroy(self.finder)
                    self.finder = None
                self.lib.NDIlib_destroy()
                self.lib = None
            for item in self._dll_dirs:
                item.close()
            self._dll_dirs.clear()


# Isolate path lookup for tests.
def ctypes_find_library(name):
    return C.util.find_library(name)


class Receiver:
    """One source; frame-sync pulls video/audio on the gateway's pacing clock."""
    def __init__(self, runtime: Runtime, source_name: str, low_bandwidth: bool = False):
        self.runtime = runtime.load()
        self.lib = runtime.lib
        self.lock = threading.RLock()
        self.name = source_name.encode('utf-8')
        self.receiver_name = b'Carisma Display Control / Gateway'
        # Keep discovery alive for reconnect; do not persist source IPs.
        runtime.sources()
        settings = RecvSettings(Source(self.name, None), 0, 0 if low_bandwidth else 100,
                                False, self.receiver_name)
        self.recv = self.lib.NDIlib_recv_create_v3(C.byref(settings))
        if not self.recv:
            raise NDIError('Creazione ricevitore NDI fallita.')
        self.sync = self.lib.NDIlib_framesync_create(self.recv)
        if not self.sync:
            self.lib.NDIlib_recv_destroy(self.recv)
            self.recv = None
            raise NDIError('Creazione frame-sync NDI fallita.')
        self.last_frame_at = 0.0
        self.last_audio_at = 0.0
        self.total_frames = 0
        self.total_audio = 0
        self.dropped_frames = 0
        self.connections = 0
        self.last_stamp = None

    def video(self):
        with self.lock:
            frame = VideoFrame()
            self.lib.NDIlib_framesync_capture_video(self.sync, C.byref(frame), 1)
            try:
                total, dropped = Performance(), Performance()
                self.lib.NDIlib_recv_get_performance(self.recv, C.byref(total), C.byref(dropped))
                self.connections = self.lib.NDIlib_recv_get_no_connections(self.recv, 0)
                if total.video != self.total_frames:
                    self.last_frame_at = time.monotonic()
                if total.audio != self.total_audio:
                    self.last_audio_at = time.monotonic()
                self.total_frames, self.total_audio = total.video, total.audio
                self.dropped_frames = dropped.video
                if not frame.data:
                    return None
                stamp = (frame.timestamp, frame.timecode)
                if stamp != self.last_stamp:
                    self.last_frame_at = time.monotonic()
                    self.last_stamp = stamp
                return copy_video(frame)
            finally:
                self.lib.NDIlib_framesync_free_video(self.sync, C.byref(frame))

    def audio(self, samples=960):
        with self.lock:
            frame = AudioFrame()
            self.lib.NDIlib_framesync_capture_audio(self.sync, C.byref(frame), 48000, 2, samples)
            try:
                return copy_audio(frame, samples)
            finally:
                self.lib.NDIlib_framesync_free_audio(self.sync, C.byref(frame))

    def close(self):
        with self.lock:
            if self.sync:
                self.lib.NDIlib_framesync_destroy(self.sync)
                self.sync = None
            if self.recv:
                self.lib.NDIlib_recv_destroy(self.recv)
                self.recv = None
