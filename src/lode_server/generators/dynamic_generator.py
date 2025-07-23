import math
from datetime import datetime, timezone
from typing import Optional

from lode_server.generator import LodeGenerator, Position
from lode_server.generators import register_generator


@register_generator("dynamic")
class DynamicGenerator(LodeGenerator):
    """
    NMEA generator that simulates circular movement starting FROM the initial point.
    Uses great-circle navigation to account for Earth's curvature.
    """
    _EARTH_RADIUS_KM = 6371.0  # Earth's mean radius in km

    def __init__(self, *args) -> None:
        super().__init__()
        if len(args) < 2:
            raise ValueError("For generate method you must specify lat and lon")

        self.speed: float = 10.0  # km/h
        self.angle: float = 0.0  # current angle in circular motion
        self.duration: float = 1.0
        self.transition: str = "auto"
        self.radius: float = 0.1  # radius of circular path in km
        self.center_lat: float = 0.0  # Will be calculated
        self.center_lon: float = 0.0  # Will be calculated

        for param in args[2:]:
            if isinstance(param, str) and param.startswith("speed="):
                try:
                    self.speed = float(param.split("=", 1)[1])
                except Exception:
                    raise ValueError("Invalid speed value")
            elif isinstance(param, str) and param.startswith("duration="):
                try:
                    self.duration = float(param.split("=", 1)[1])
                except Exception:
                    raise ValueError("Invalid duration value")
            elif isinstance(param, str) and param.startswith("transition="):
                self.transition = param.split("=", 1)[1]
            elif isinstance(param, str) and param.startswith("radius="):
                try:
                    self.radius = float(param.split("=", 1)[1])
                except Exception:
                    raise ValueError("Invalid radius value")
        # Calculate center point so that initial point is on the circle
        self._calculate_center(float(args[0]), float(args[1]))


    def _calculate_center(self, initial_lat: float, initial_lon: float):
        """Calculate center point so that initial point is at angle 0 on the circle"""
        # Move from initial point at 180 degrees (south) to find center
        angular_dist = self.radius / self._EARTH_RADIUS_KM
        initial_lat_rad = math.radians(initial_lat)
        initial_lon_rad = math.radians(initial_lon)

        # Calculate center point (180 degrees from initial point)
        self.center_lat = math.degrees(math.asin(
            math.sin(initial_lat_rad) * math.cos(angular_dist) -
            math.cos(initial_lat_rad) * math.sin(angular_dist) * math.cos(math.pi)
        ))

        self.center_lon = math.degrees(initial_lon_rad + math.atan2(
            math.sin(math.pi) * math.sin(angular_dist) * math.cos(initial_lat_rad),
            math.cos(angular_dist) + math.sin(initial_lat_rad) * math.sin(math.radians(self.center_lat))
        ))

    def _calculate_position_on_circle(self, angle: float) -> tuple[float, float]:
        """
        Calculate position on a circle using great-circle navigation.

        Args:
            angle: Current angle in radians (0 = initial point position)

        Returns:
            Tuple[new_lat, new_lon] in degrees
        """
        angular_radius = self.radius / self._EARTH_RADIUS_KM
        center_lat_rad = math.radians(self.center_lat)
        center_lon_rad = math.radians(self.center_lon)

        new_lat_rad = math.asin(
            math.sin(center_lat_rad) * math.cos(angular_radius) +
            math.cos(center_lat_rad) * math.sin(angular_radius) * math.cos(angle)
        )

        new_lon_rad = center_lon_rad + math.atan2(
            math.sin(angle) * math.sin(angular_radius) * math.cos(center_lat_rad),
            math.cos(angular_radius) - math.sin(center_lat_rad) * math.sin(new_lat_rad)
        )

        return math.degrees(new_lat_rad), math.degrees(new_lon_rad)

    def _update_position(self) -> Optional[Position]:
        """
        Update the position moving along a circular path starting from initial point.
        Returns:
            Optional[Position]: Position data, None if finished
        """
        # Calculate angular speed based on circumference and speed
        circumference = 2 * math.pi * self.radius
        if circumference > 0:
            angle_increment = (self.speed * self.duration / 3600) / circumference * 2 * math.pi
        else:
            angle_increment = 0

        self.angle = (self.angle + angle_increment) % (2 * math.pi)

        lat, lon = self._calculate_position_on_circle(self.angle)

        return Position(
            lat=lat,
            lon=lon,
            speed=self.speed,
            elevation=0.0,
            time=datetime.now(timezone.utc),
            duration=self.duration,
            transition=self.transition,
            description=""
        )
