from datetime import datetime
from abc import ABC, abstractmethod
from typing import Optional, Iterator
from dataclasses import dataclass
from datetime import timezone


@dataclass
class Position:
    """
    Container for position and navigation data with timestamp.
    
    Represents a single point in space with associated navigation metrics and timing information.
    Used for both static points and route navigation.

    Attributes:
        lat (float): Latitude in decimal degrees. Range: -90 to +90.
        lon (float): Longitude in decimal degrees. Range: -180 to +180.
        speed (float): Speed over ground in km/h (nautical miles per hour).
        elevation (float): Elevation/altitude above sea level in meters.
        time (datetime): UTC timestamp of the position measurement.
        duration (float): Optional. Suggested duration at this point in seconds (for routes).
                        Default: 0.0 (no pause at point).
        transition (str): Transition mode to next position: 'auto' (default), 'manual', or 'key'.
        description (str): Optional description or comment for this position.
    
    Examples:
        >>> pos = Position(55.7522, 37.6156, 5.0, 120.5, datetime.now(timezone.utc))
        >>> route_point = Position(59.9343, 30.3351, 10.0, 5.5, 
        ...                          datetime.now(timezone.utc), 
        ...                          duration=2.5, transition='manual', description='Start point')
    """
    lat: float          # Latitude in degrees
    lon: float          # Longitude in degrees
    speed: float        # Speed in km/h
    elevation: float    # Elevation in meters
    time: datetime      # Current time
    duration: float = 0.0    # Duration at current point (for routes)
    transition: str = "auto" # Transition mode: 'auto', 'manual'
    description: str = ""    # Optional description or comment


class NMEAEncoder:
    """Handles encoding of Position to NMEA sentences"""
    
    # Constants for GGA sentence
    GGA_FIX_QUALITY = '1'          # 0=invalid, 1=GPS fix, 2=DGPS fix, etc.
    GGA_NUM_SATELLITES = '08'       # Number of satellites in use (00-12)
    GGA_HDOP = '1.0'                # Horizontal dilution of precision
    GGA_GEOID_SEPARATION = '0.0'    # Geoid separation (meters)
    GGA_DGPS_AGE = ''               # Age of DGPS data (empty for no DGPS)
    GGA_DGPS_REF = ''               # DGPS reference station ID
    
    @staticmethod
    def format_coords(lat: float, lon: float) -> tuple[str, str, str, str]:
        """
        Format latitude and longitude for NMEA sentences.
        Returns:
            Tuple[str, str, str, str]: (lat_str, lat_dir, lon_str, lon_dir)
        """
        lat_deg = int(lat)
        lat_min = abs((lat - lat_deg) * 60)
        lat_dir = 'N' if lat >= 0 else 'S'
        lat_str = f"{abs(lat_deg):02d}{lat_min:09.6f}"

        lon_deg = int(lon)
        lon_min = abs((lon - lon_deg) * 60)
        lon_dir = 'E' if lon >= 0 else 'W'
        lon_str = f"{abs(lon_deg):03d}{lon_min:09.6f}"

        return lat_str, lat_dir, lon_str, lon_dir
    
    @staticmethod
    def calculate_checksum(sentence: str) -> str:
        """
        Calculate the NMEA checksum for a sentence.
        Args:
            sentence (str): The NMEA sentence without the starting '$' and checksum.
        Returns:
            str: The checksum as a two-digit hexadecimal string.
        """
        checksum = 0
        for char in sentence:
            checksum ^= ord(char)
        return f"{checksum:02X}"
    
    def encode_gga(self, data: Position) -> str:
        """
        Generate an NMEA GGA sentence from position data.
        Returns:
            str: The generated GGA sentence
        """
        time_str = data.time.strftime("%H%M%S.%f")[:-3]
        lat_str, lat_dir, lon_str, lon_dir = self.format_coords(data.lat, data.lon)

        gga = (
            f"GPGGA,{time_str},{lat_str},{lat_dir},"
            f"{lon_str},{lon_dir},{self.GGA_FIX_QUALITY},{self.GGA_NUM_SATELLITES},"
            f"{self.GGA_HDOP},{data.elevation:.1f},M,{self.GGA_GEOID_SEPARATION},M,"
            f"{self.GGA_DGPS_AGE},{self.GGA_DGPS_REF}"
        )
        return f"${gga}*{self.calculate_checksum(gga)}\r\n"
    
    def encode_rmc(self, data: Position) -> str:
        """
        Generate an NMEA RMC sentence from position data.
        Returns:
            str: The generated RMC sentence
        """
        time_str = data.time.strftime("%H%M%S.%f")[:-3]
        date_str = data.time.strftime("%d%m%y")
        lat_str, lat_dir, lon_str, lon_dir = self.format_coords(data.lat, data.lon)

        speed_knots = data.speed * 0.539957  # Convert speed from km/h to knots

        rmc = (
            f"GPRMC,{time_str},A,{lat_str},{lat_dir},"
            f"{lon_str},{lon_dir},{speed_knots:.1f},0.0,{date_str},,,A"
        )
        return f"${rmc}*{self.calculate_checksum(rmc)}\r\n"


class NMEADecoder:
    """
    Decodes NMEA sentences (GGA, RMC) into Position objects.
    Unsupported or invalid sentences raise exceptions.
    """
    @staticmethod
    def decode(nmea: str) -> Optional[Position]:
        if not nmea.startswith('$'):
            raise ValueError("Not a valid NMEA sentence")
        nmea = nmea.strip()
        if '*' in nmea:
            nmea = nmea[:nmea.index('*')]
        fields = nmea[1:].split(',')

        if fields[0] == 'GPRMC' or fields[0] == 'RMC':
            if len(fields) < 10 or fields[2] != 'A':
                raise ValueError("Invalid RMC sentence")
            time_str = fields[1]
            date_str = fields[9]
            lat = NMEADecoder._parse_lat(fields[3], fields[4])
            lon = NMEADecoder._parse_lon(fields[5], fields[6])
            speed = float(fields[7]) * 1.852 if fields[7] else 0.0  # knots to km/h
            elevation = 0.0  # Not present in RMC
            dt = NMEADecoder._parse_datetime(time_str, date_str)
            if dt is None:
                raise ValueError("No valid datetime in RMC")
            return Position(lat, lon, speed, elevation, dt)
        elif fields[0] == 'GPGGA' or fields[0] == 'GGA':
            if len(fields) < 10:
                raise ValueError("Invalid GGA sentence")
            time_str = fields[1]
            lat = NMEADecoder._parse_lat(fields[2], fields[3])
            lon = NMEADecoder._parse_lon(fields[4], fields[5])
            elevation = float(fields[9]) if fields[9] else 0.0
            speed = 0.0  # Not present in GGA
            dt = NMEADecoder._parse_datetime(time_str)
            if dt is None:
                raise ValueError("No valid datetime in GGA")
            return Position(lat, lon, speed, elevation, dt)
        raise ValueError("Unsupported NMEA sentence type")

    @staticmethod
    def _parse_lat(lat_str, ns):
        if not lat_str or not ns:
            return 0.0
        deg = int(lat_str[:2])
        min = float(lat_str[2:])
        lat = deg + min / 60
        if ns == 'S':
            lat = -lat
        return lat

    @staticmethod
    def _parse_lon(lon_str, ew):
        if not lon_str or not ew:
            return 0.0
        deg = int(lon_str[:3])
        min = float(lon_str[3:])
        lon = deg + min / 60
        if ew == 'W':
            lon = -lon
        return lon

    @staticmethod
    def _parse_datetime(time_str, date_str=None):
        try:
            if not time_str:
                return None
            hour = int(time_str[0:2])
            minute = int(time_str[2:4])
            second = int(time_str[4:6])
            microsecond = int(float('0.' + time_str.split('.')[1]) * 1e6) if '.' in time_str else 0
            if date_str:
                day = int(date_str[0:2])
                month = int(date_str[2:4])
                year = int(date_str[4:6]) + 2000
                return datetime(year, month, day, hour, minute, second, microsecond, tzinfo=timezone.utc)
            else:
                # Если нет даты — используем сегодняшнюю дату
                now = datetime.now(timezone.utc)
                return now.replace(hour=hour, minute=minute, second=second, microsecond=microsecond)
        except Exception:
            return None


class LodeGenerator(ABC, Iterator):
    """
    Abstract base class for data generators.
    Works as an iterator that yields Position objects.
    """
    def __init__(self) -> None:
        """Initialize the generator with default values."""
        pass

    @abstractmethod
    def _update_position(self) -> Optional[Position]:
        """
        Update the current position.
        Returns:
            Optional[Position]: Position data, None if finished
        """
        pass

    def __iter__(self) -> Iterator:
        return self
    
    def __next__(self) -> Position:
        """
        Get next position data.
        Returns:
            Position: Current position and navigation data
        Raises:
            StopIteration: When route is finished or generator stopped
        """
        data = self._update_position()
        if data is None:
            raise StopIteration
        return data
