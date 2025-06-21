from datetime import datetime, timezone
from typing import List, Optional
import csv

from lode_server.generator import NMEAGenerator, Position
from lode_server.generators import register_generator


@register_generator("csv")
class CSVGenerator(NMEAGenerator):
    """
    NMEA generator that reads position data from a CSV file.
    
    CSV format:
    point_number,latitude,longitude,speed,elevation,duration,transition,description
    
    Example row:
    1,55.7522,37.6156,10.0,120.5,2.0,auto,"Moscow center"
    """
    
    def __init__(self, *args) -> None:
        """
        Args:
            args: [filename] - path to CSV file
        """
        super().__init__()
        
        if len(args) < 1:
            raise ValueError("CSV file path must be specified")
            
        self.filename: str = args[0]
        self.current_index: int = 0
        self.route_points: List[Position] = []
        
        self._load_csv()
        
    def _load_csv(self) -> None:
        """Load and validate the CSV file"""
        try:
            with open(self.filename, 'r', newline='') as f:
                reader = csv.reader(f)
                for row in reader:
                    # Skip empty or comment lines
                    if not row or row[0].startswith('#'):
                        continue
                        
                    if len(row) < 5:
                        raise ValueError(f"Invalid CSV format in row: {row}. Need at least 5 columns")
                    
                    # Parse required fields
                    lat = float(row[1])
                    lon = float(row[2])
                    speed = float(row[3]) if len(row) > 3 else 0.0
                    elevation = float(row[4]) if len(row) > 4 else 0.0
                    
                    # Parse optional fields
                    duration = float(row[5]) if len(row) > 5 else 0.0
                    transition = row[6] if len(row) > 6 else "auto"
                    description = row[7] if len(row) > 7 else ""
                    
                    point = Position(
                        lat=lat,
                        lon=lon,
                        speed=speed,
                        elevation=elevation,
                        time=datetime.now(timezone.utc),
                        duration=duration,
                        transition=transition,
                        description=description
                    )
                    self.route_points.append(point)
                
            if not self.route_points:
                raise ValueError("No valid points found in CSV file")
                
        except Exception as e:
            raise ValueError(f"Failed to load CSV file: {str(e)}")
    
    def _update_position(self) -> Optional[Position]:
        """
        Get next point from CSV.
        Returns:
            Optional[Position]: Next position data or None if finished
        """
        if self.current_index >= len(self.route_points):
            return None
            
        point = self.route_points[self.current_index]
        self.current_index += 1
        return point
