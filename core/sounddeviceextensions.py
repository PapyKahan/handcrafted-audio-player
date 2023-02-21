import sounddevice as sd

class ExWasapiSettings(sd.WasapiSettings):
    def __init__(self, exclusive=False, polling=False, thread_priority=False):
        flags = 0x0
        if exclusive:
            flags |= sd._lib.paWinWasapiExclusive
        if polling:
            flags |= sd._lib.paWinWasapiPolling
        if thread_priority:
            flags |= sd._lib.paWinWasapiThreadPriority
        self._streaminfo = sd._ffi.new('PaWasapiStreamInfo*', dict(
            size=sd._ffi.sizeof('PaWasapiStreamInfo'),
            hostApiType=sd._lib.paWASAPI,
            version=1,
            flags=flags,
        ))
