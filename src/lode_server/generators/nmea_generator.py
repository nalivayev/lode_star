from typing import List, Optional

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
        self.positions: List[Position] = []
        self._current_index: int = 0
        self._load_file(args[0])

    def _load_file(self, filename: str) -> None:
        """Load NMEA sentences from the specified file and parse them into Position objects."""
        with open(self.filename, 'r') as f:
            for line in f:
                try:
                    pos = NMEADecoder.decode(line)
                    self.positions.append(pos)
                except Exception as e:
                    continue

    def _update_position(self) -> Optional[Position]:
        if self._current_index >= len(self.positions):
            return None
        pos = self.positions[self._current_index]
        self._current_index += 1
        return pos
