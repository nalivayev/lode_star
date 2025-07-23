from datetime import datetime, timezone
from json import load

from lode_server.generator import FileGenerator, Position
from lode_server.generators import register_generator


@register_generator("geojson")
class GeoJSONGenerator(FileGenerator):
    """
    NMEA generator that follows a route defined in GeoJSON format.
    Returns Position objects with recommended duration and transition for each point.
    """
    def __init__(self, *args) -> None:
        super().__init__()
        
        if len(args) < 1:
            raise ValueError("Route file path must be specified")
            
        self._load_file(args[0])
        
    def _load_file(self, filename: str) -> None:
        """Load and validate the GeoJSON route file"""
        try:
            with open(filename, 'r') as f:
                route_data = load(f)
                
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
                self._positions.append(point)
                
            if not self._positions:
                raise ValueError("No valid points found in route file")
                
        except Exception as e:
            raise ValueError(f"Failed to load route file: {str(e)}")
