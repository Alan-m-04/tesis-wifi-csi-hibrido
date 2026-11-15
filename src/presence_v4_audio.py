"""Distinct laptop sounds; playback completion never claims human audibility."""
import array
import math
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import wave

PATTERNS = {'establish_condition': (2, .12, 880),
            'window_finished_connection_open': (1, .12, 660),
            'both_ports_closed_confirmed': (3, .45, 1100),
            'failure': (8, .08, 330)}


def create_wav(path, kind):
    count, duration, frequency = PATTERNS[kind]
    rate = 16000
    samples = array.array('h')
    for _ in range(count):
        samples.extend(int(12000*math.sin(2*math.pi*frequency*i/rate)) for i in range(int(duration*rate)))
        samples.extend([0]*int(.15*rate))
    if sys.byteorder != 'little':
        samples.byteswap()
    with Path(path).open('xb') as f:
        with wave.open(f, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate)
            wav.writeframes(samples.tobytes())


class RecordingNotifier:
    """Synthetic acknowledgements only. No audio has been emitted or heard."""
    name = 'synthetic_recording_only_no_audio'

    def __init__(self):
        self.results = []

    def start(self, cue):
        self.results.append((cue['id'], True))

    def poll(self):
        result, self.results = self.results, []
        return result

    def finish(self):
        pass


class LaptopNotifier:
    """One audio worker keeps playback from blocking acquisition or close checks."""
    name = 'laptop_aplay_human_audibility_unverified'

    def __init__(self, output, player=None):
        self.output = Path(output)
        self.output.mkdir(exist_ok=False)
        self.player = player or shutil.which('aplay')
        if not self.player:
            raise ValueError('aplay unavailable; audible operation cannot be prepared as successful')
        self.requests, self.results = queue.Queue(), queue.Queue()
        self.thread = threading.Thread(target=self._work, daemon=True)
        self.thread.start()

    def start(self, cue):
        self.requests.put(dict(cue))

    def _work(self):
        while True:
            cue = self.requests.get()
            if cue is None:
                return
            try:
                path = self.output/(str(cue['id'])+'-'+cue['kind']+'.wav')
                create_wav(path, cue['kind'])
                result = subprocess.run([self.player, '--quiet', str(path)],
                                        timeout=10, capture_output=True, check=False)
                ok = result.returncode == 0
            except (OSError, ValueError, subprocess.SubprocessError):
                ok = False
            self.results.put((cue['id'], ok))

    def poll(self):
        found = []
        while True:
            try:
                found.append(self.results.get_nowait())
            except queue.Empty:
                return found

    def finish(self):
        self.requests.put(None)
        self.thread.join(timeout=12)
        if self.thread.is_alive():
            raise RuntimeError('Audio worker has not stopped')
