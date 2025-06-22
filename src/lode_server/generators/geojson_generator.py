from datetime import datetime, timezone
from typing import List, Optional
import json

from lode_server.generator import LodeGenerator, Position
from lode_server.generators import register_generator


@register_generator("geojson")
class GeoJSONGenerator(LodeGenerator):
    """
    NMEA generator that follows a route defined in GeoJSON format.
    Returns Position objects with recommended duration and transition for each point.
    """
    def __init__(self, *args) -> None:
        super().__init__()
        
        if len(args) < 1:
            raise ValueError("Route file path must be specified")
            
        self.route_file: str = args[0]
        self.current_index: int = 0
        self.route_points: List[Position] = []
        
        self._load_route()
        
    def _load_route(self) -> None:
        """Load and validate the GeoJSON route file"""
        try:
            with open(self.route_file, 'r') as f:
                route_data = json.load(f)
                
            if not isinstance(route_data, dict):
                raise ValueError("Invalid GeoJSON format")
                
            if 'features' not in route_data:
                raise ValueError("GeoJSON file must contain 'features'")
            
            for feature in route_data['features']:
                if feature['geometry']['type'] != 'Point':
                    continue
                    
                coords = feature['geometry']['coordinates']
                props = feature.get('properties', {})
                
                point = Position(
                    lat=coords[1],
                    lon=coords[0],
                    speed=float(props.get('speed', 0)),
                    elevation=float(props.get('elevation', 0)),
                    time=datetime.now(timezone.utc),
                    duration=float(props.get('duration', 0)),
                    transition=props.get('transition', 'auto'),
                    description=props.get('description', '')
                )
                self.route_points.append(point)
                
            if not self.route_points:
                raise ValueError("No valid points found in route file")
                
        except Exception as e:
            raise ValueError(f"Failed to load route file: {str(e)}")
    
    def _update_position(self) -> Optional[Position]:
        """
        Get next point in route.
        Returns:
            Optional[Position]: Next position data or None if finished
        """
        if self.current_index >= len(self.route_points):
            return None
            
        point = self.route_points[self.current_index]
        self.current_index += 1
        return point
