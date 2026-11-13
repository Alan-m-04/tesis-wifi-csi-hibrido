"""Local adapter for audited pySerial 3.5 POSIX open, without input flushing.

No device is opened by import or by constructing the class with port=None.
"""
def preserving_serial_type(base):
    class PreservingSerial(base):
        def __init__(self, *args, **kwargs):
            if kwargs.get('port') is not None or args:
                raise ValueError('Construct unopened with port=None')
            self.open_flush_suppressed = 0
            self._opening_without_flush = False
            super().__init__(*args, **kwargs)
        def open(self):
            self._opening_without_flush = True
            try:
                return super().open()
            finally:
                self._opening_without_flush = False
        def _reset_input_buffer(self):
            if not self._opening_without_flush:
                raise RuntimeError('Input flush forbidden by capture policy')
            self.open_flush_suppressed += 1
        def reset_input_buffer(self):
            raise RuntimeError('Input flush forbidden by capture policy')
        def reset_output_buffer(self):
            raise RuntimeError('Output flush forbidden by capture policy')
    return PreservingSerial
