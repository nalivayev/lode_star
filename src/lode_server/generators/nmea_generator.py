from typing import Optional

from lode_server.generator import LodeGenerator, Position, NMEADecoder
from lode_server.generators import register_generator


@register_generator("nmea")
class NMEAGenerator(LodeGenerator):
    """
    Generator that reads NMEA sentences from a file and yields Position objects.
    Each line in the file should be a valid NMEA sentence.
    Unsupported or unparsable lines are skipped and logged.
    """
    def __init__(self, *args) -> None:
        super().__init__()
        if len(args) < 1:
            raise ValueError("NMEA file path must be specified")
        for param in args[2:]:
            if isinstance(param, str) and param.startswith("duration="):
                try:
                    self._duration = float(param.split("=", 1)[1])
                except Exception:
                    raise ValueError("Invalid duration value")
        self._positions: list[Position] = []
        self._index: int = 0
        self._load_file(args[0])

    def _load_file(self, filename: str) -> None:
        """Load NMEA sentences from the specified file and parse them into Position objects."""
        with open(filename, 'r') as f:
            for line in f:
                try:
                    pos = NMEADecoder.decode(line)
                    if pos:
                        pos.duration = self._duration
                        self._positions.append(pos)
                except Exception as e:
                    continue

    def _update_position(self) -> Optional[Position]:
        if self._index >= len(self._positions):
            return None
        pos = self._positions[self._index]
        self._index += 1
        return pos
