from lode_server.generator import FileGenerator, NMEADecoder
from lode_server.generators import register_generator


@register_generator("nmea")
class NMEAGenerator(FileGenerator):
    """
    Generator that reads NMEA sentences from a file and yields Position objects.
    Each line in the file should be a valid NMEA sentence.
    Unsupported or unparsable lines are skipped and logged.
    """
    def __init__(self, *args) -> None:
        super().__init__()
        if len(args) < 1:
            raise ValueError("NMEA file path must be specified")

        for param in args[1:]:
            if isinstance(param, str) and param.startswith("duration="):
                try:
                    self._duration = float(param.split("=", 1)[1])
                except Exception:
                    raise ValueError("Invalid duration value")
            elif isinstance(param, str) and param.startswith("index="):
                try:
                    self._index = int(param.split("=", 1)[1])
                except Exception:
                    raise ValueError("Invalid duration value")
        
        self._load_file(args[0])

    def _load_file(self, filename: str) -> None:
        """Load NMEA sentences from the specified file and parse them into Position objects."""
        with open(filename, 'r') as f:
            index = 1
            for line in f:
                try:
                    pos = NMEADecoder.decode(line)
                    if pos:
                        pos.index = index
                        pos.duration = self._duration
                        self._positions.append(pos)
                        index += 1
                except Exception as e:
                    continue
