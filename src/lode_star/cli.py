import argparse
import math
import socket
import threading
import time
from datetime import datetime, timezone
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
import json
from pathlib import Path


class NMEAGenerator(ABC):
    """
    Abstract base class for NMEA sentence generators.
    Provides thread safety and methods for generating RMC and GGA sentences.
    """
    def __init__(self) -> None:
        """Initialize the generator with default values."""
        self.lock: threading.Lock = threading.Lock()
        self.interval_sec: float = 1.0
        self.running: bool = True
        self.transmitting: bool = False
        self.time: datetime = datetime.now(timezone.utc)
        self.lat: float = 0.0
        self.lon: float = 0.0

    def stop(self) -> None:
        """Stop the generator."""
        with self.lock:
            self.running = False

    def start_transmission(self) -> None:
        """Start transmitting coordinates."""
        with self.lock:
            self.transmitting = True

    @abstractmethod
    def update_position(self) -> None:
        """
        Update the current position.
        Must be implemented by subclasses.
        """
        pass

    def get_speed_knots(self) -> float:
        """
        Return current speed in knots for NMEA output.
        Should be implemented in subclass if speed is dynamic.
        """
        return 0.0

    def get_elevation(self) -> float:
        """
        Return current elevation in meters for NMEA output.
        Should be implemented in subclass if elevation is dynamic.
        """
        return 0.0

    def _format_nmea_coords(self) -> Tuple[str, str, str, str]:
        """
        Format latitude and longitude for NMEA sentences.
        Returns:
            Tuple[str, str, str, str]: (lat_str, lat_dir, lon_str, lon_dir)
        """
        lat_deg: int = int(self.lat)
        lat_min: float = abs((self.lat - lat_deg) * 60)
        lat_dir: str = 'N' if self.lat >= 0 else 'S'
        lat_str: str = f"{abs(lat_deg):02d}{lat_min:09.6f}"

        lon_deg: int = int(self.lon)
        lon_min: float = abs((self.lon - lon_deg) * 60)
        lon_dir: str = 'E' if self.lon >= 0 else 'W'
        lon_str: str = f"{abs(lon_deg):03d}{lon_min:09.6f}"

        return lat_str, lat_dir, lon_str, lon_dir

    def generate_rmc(self) -> str:
        """
        Generate an NMEA RMC sentence.
        Returns:
            str: The generated RMC sentence or an empty string if not transmitting.
        """
        with self.lock:
            if not self.transmitting:
                return ""
                
            time_str: str = self.time.strftime("%H%M%S.%f")[:-3]
            date_str: str = self.time.strftime("%d%m%y")
            speed_knots: float = self.get_speed_knots()
            lat_str, lat_dir, lon_str, lon_dir = self._format_nmea_coords()

            rmc: str = (
                f"GPRMC,{time_str},A,{lat_str},{lat_dir},"
                f"{lon_str},{lon_dir},{speed_knots:.1f},0.0,{date_str},,,A"
            )
            return f"${rmc}*{self.calculate_checksum(rmc)}\r\n"

    def generate_gga(self) -> str:
        """
        Generate an NMEA GGA sentence.
        Returns:
            str: The generated GGA sentence or an empty string if not transmitting.
        """
        with self.lock:
            if not self.transmitting:
                return ""
                
            time_str: str = self.time.strftime("%H%M%S.%f")[:-3]
            lat_str, lat_dir, lon_str, lon_dir = self._format_nmea_coords()
            elevation: float = self.get_elevation()

            gga: str = (
                f"GPGGA,{time_str},{lat_str},{lat_dir},"
                f"{lon_str},{lon_dir},1,08,1.0,{elevation:.1f},M,0.0,M,,"
            )
            return f"${gga}*{self.calculate_checksum(gga)}\r\n"
    
    @staticmethod
    def calculate_checksum(sentence: str) -> str:
        """
        Calculate the NMEA checksum for a sentence.
        Args:
            sentence (str): The NMEA sentence without the starting '$' and checksum.
        Returns:
            str: The checksum as a two-digit hexadecimal string.
        """
        checksum: int = 0
        for char in sentence:
            checksum ^= ord(char)
        return f"{checksum:02X}"


class DynamicNMEAGenerator(NMEAGenerator):
    """
    NMEA generator that simulates movement along a course with a given speed.
    Speed is provided in kilometers per hour, but NMEA output is in knots.
    """
    def __init__(self, *args) -> None:
        """
        Args:
            args: [lat, lon, ...] where ... may include speed=... and interval=...
        """
        super().__init__()
        if len(args) < 2:
            raise ValueError("For generate method you must specify lat and lon")
        self.lat: float = float(args[0])
        self.lon: float = float(args[1])
        self.speed: float = 10.0
        self.heading: int = 0
        self.interval_sec: float = 1.0

        for param in args[2:]:
            if isinstance(param, str) and param.startswith("speed="):
                try:
                    self.speed = float(param.split("=", 1)[1])
                except Exception:
                    raise ValueError("Invalid speed value")
            elif isinstance(param, str) and param.startswith("interval="):
                try:
                    self.interval_sec = float(param.split("=", 1)[1])
                except Exception:
                    raise ValueError("Invalid interval value")


class GeoJSONRouteNMEAGenerator(NMEAGenerator):
    """
    NMEA generator that follows a route defined in GeoJSON format.
    Supports automatic/manual transitions between points and timed stops.
    """
    def __init__(self, *args) -> None:
        """
        Args:
            args: [geojson_path]
        """
        super().__init__()
        if not args or len(args) < 1:
            raise ValueError("For route method you must specify GeoJSON file path")
        geojson_path = args[0]
        self.route_points: List[Dict] = []
        self.current_point_index: int = 0
        self.current_stop_start: Optional[float] = None
        self.manual_waiting: bool = False
        self.load_route(geojson_path)
        
        if self.route_points:
            self._set_position_from_point(self.route_points[0])

    def load_route(self, file_path: str) -> None:
        """Load and validate GeoJSON route file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if not isinstance(data, dict) or data.get('type') != 'FeatureCollection':
                raise ValueError("Invalid GeoJSON - must be FeatureCollection")
                
            self.route_points = []
            for feature in data.get('features', []):
                if feature['geometry']['type'] == 'Point':
                    point = {
                        'coords': feature['geometry']['coordinates'],
                        'properties': feature.get('properties', {})
                    }
                    self.route_points.append(point)
            
            if not self.route_points:
                raise ValueError("No valid route points found in GeoJSON")
                
            print(f"\nLoaded {len(self.route_points)} route points from {file_path}")
            print("=" * 50)
            
        except Exception as e:
            raise ValueError(f"Failed to load GeoJSON route: {str(e)}")

    def _set_position_from_point(self, point: Dict) -> None:
        """Update current position from GeoJSON point"""
        with self.lock:
            self.lon, self.lat = point['coords']
            props = point.get('properties', {})
            self.time = datetime.now(timezone.utc)
            point_name = props.get('name', f"Point {self.current_point_index + 1}")
            print(f"\n📍 Current position: {point_name}")
            print(f"   Coordinates: {self.lat:.6f}° N, {self.lon:.6f}° E")
            print(f"   Speed: {props.get('speed', 0.0)} knots")
            print(f"   Elevation: {props.get('elevation', 0.0)} m")
            if 'duration' in props:
                print(f"   Stop duration: {props['duration']} sec")

    def get_speed_knots(self) -> float:
        """Get current speed from point properties"""
        if not self.route_points or self.current_point_index >= len(self.route_points):
            return 0.0
            
        props = self.route_points[self.current_point_index].get('properties', {})
        return float(props.get('speed', 0.0))

    def get_elevation(self) -> float:
        """Get current elevation for GGA sentence"""
        if not self.route_points or self.current_point_index >= len(self.route_points):
            return 0.0
            
        props = self.route_points[self.current_point_index].get('properties', {})
        return float(props.get('elevation', 0.0))

    def update_position(self) -> None:
        """Handle route progression with stops and transitions"""
        while self.running:
            with self.lock:
                if not self.transmitting or not self.route_points:
                    time.sleep(self.interval_sec)
                    continue
                    
                current_point = self.route_points[self.current_point_index]
                props = current_point.get('properties', {})
                duration = float(props.get('duration', 0))
                transition_mode = props.get('transition_mode', 'auto')
                point_name = props.get('name', f"Point {self.current_point_index + 1}")
                
                # Handle stop duration
                if duration > 0 and self.current_stop_start is None:
                    self.current_stop_start = time.time()
                    print(f"\n🛑 STOP at {point_name} for {duration} seconds")
                
                # Check if should move to next point
                move_to_next = False
                
                if transition_mode == 'auto':
                    if duration > 0 and self.current_stop_start:
                        elapsed = time.time() - self.current_stop_start
                        if elapsed >= duration:
                            move_to_next = True
                            print(f"\n⏱️ Auto-proceeding from {point_name} after {duration}s stop")
                    else:
                        move_to_next = True
                else:  # manual transition
                    if self.current_stop_start is None:
                        self.current_stop_start = time.time()
                        self.manual_waiting = True
                        print(f"\n⏳ Waiting at {point_name} (manual transition)")
                        print("   Press [Enter] to continue to next point...")
                    
                    # В ручном режиме move_to_next остается False
                
                if move_to_next and self.current_point_index < len(self.route_points) - 1:
                    self.current_point_index += 1
                    self._set_position_from_point(self.route_points[self.current_point_index])
                    self.current_stop_start = None
                    self.manual_waiting = False
            
            time.sleep(self.interval_sec)

    def advance_to_next_point(self) -> None:
        """Manually advance to next route point"""
        with self.lock:
            if self.manual_waiting and self.current_point_index < len(self.route_points) - 1:
                next_point = self.route_points[self.current_point_index + 1]
                next_name = next_point.get('properties', {}).get('name', 
                           f"Point {self.current_point_index + 2}")
                
                print(f"\n✅ Manual transition approved, moving to {next_name}")
                self.current_point_index += 1
                self._set_position_from_point(self.route_points[self.current_point_index])
                self.current_stop_start = None
                self.manual_waiting = False
            elif self.manual_waiting:
                print("\n⚠️ Already at the last route point, cannot advance further")
            else:
                print("\n⚠️ Not currently waiting for manual transition")

    def get_current_point_info(self) -> Dict:
        """Get information about current route point"""
        with self.lock:
            if not self.route_points or self.current_point_index >= len(self.route_points):
                return {}
                
            point = self.route_points[self.current_point_index]
            props = point.get('properties', {})
            return {
                'index': self.current_point_index,
                'name': props.get('name', f"Point {self.current_point_index + 1}"),
                'total_points': len(self.route_points),
                'coordinates': point['coords'],
                'speed': float(props.get('speed', 0.0)),
                'elevation': float(props.get('elevation', 0.0)),
                'duration': float(props.get('duration', 0)),
                'transition_mode': props.get('transition_mode', 'auto'),
                'is_stopped': self.current_stop_start is not None,
                'waiting_input': self.manual_waiting,
                'stop_elapsed': time.time() - self.current_stop_start if self.current_stop_start else 0
            }


def create_generator(method_type: str, *method_params: Any) -> NMEAGenerator:
    """
    Factory function to create an NMEA generator.
    Args:
        method_type (str): The generation method ('generate' or 'route').
        *method_params: Parameters for the generator.
    Returns:
        NMEAGenerator: An instance of a generator.
    Raises:
        ValueError: If parameters are invalid or method is unknown.
    """
    if method_type == 'generate':
        return DynamicNMEAGenerator(*method_params)
    elif method_type == 'route':
        return GeoJSONRouteNMEAGenerator(*method_params)
    else:
        raise ValueError(f"Unknown method: {method_type}")


def handle_client(conn: socket.socket, addr: Tuple[str, int], generator: NMEAGenerator) -> None:
    """
    Handle a client connection: send NMEA sentences to the client.
    Args:
        conn (socket.socket): The client socket.
        addr (tuple): The client address.
        generator (NMEAGenerator): The NMEA generator instance.
    """
    print(f"Client connected: {addr}")
    try:
        with conn:
            while generator.running:
                rmc: str = generator.generate_rmc()
                gga: str = generator.generate_gga()
                if rmc:
                    conn.sendall(rmc.encode('ascii'))
                if gga:
                    conn.sendall(gga.encode('ascii'))
                time.sleep(generator.interval_sec)
    except (ConnectionResetError, BrokenPipeError):
        print(f"Client disconnected: {addr}")
    except Exception as e:
        print(f"Client error ({addr}): {e}")


def handle_user_input(generator: NMEAGenerator) -> None:
    """Handle user input for manual route progression"""
    while generator.running:
        try:
            input()  # Wait for Enter key
            if isinstance(generator, GeoJSONRouteNMEAGenerator):
                generator.advance_to_next_point()
        except EOFError:
            break
        except Exception as e:
            print(f"Input error: {e}")


def run_server(
    port: int,
    method_type: str,
    method_params: List[Any],
    wait_for_keypress: bool
) -> None:
    """
    Start the NMEA TCP server.
    Args:
        port (int): TCP port to listen on.
        method_type (str): Generation method.
        method_params (list): Parameters for the generator.
        wait_for_keypress (bool): Wait for ENTER before starting transmission.
    """
    try:
        generator: NMEAGenerator = create_generator(method_type, *method_params)
        
        if not wait_for_keypress:
            generator.start_transmission()
        
        update_thread = threading.Thread(target=generator.update_position)
        update_thread.daemon = True
        update_thread.start()
        
        # Start user input thread for route generator
        if isinstance(generator, GeoJSONRouteNMEAGenerator):
            input_thread = threading.Thread(target=handle_user_input, args=(generator,))
            input_thread.daemon = True
            input_thread.start()
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('0.0.0.0', port))
            s.listen(5)
            s.settimeout(1)
            
            print(f"\nNMEA TCP Server started on port {port}")
            print("=" * 40)
            print(f"Generation method: {method_type}")
            if method_type == 'generate':
                print(f"Initial position: {method_params[0]}° N, {method_params[1]}° E")
                # Speed and interval are parsed and printed by the generator if needed
            elif method_type == 'route':
                print(f"Route file: {method_params[0]}")
            print(f"Wait for keypress: {'Yes' if wait_for_keypress else 'No'}")
            print("=" * 40)
            
            if wait_for_keypress:
                print("\nServer is waiting for ENTER to start transmission...")
                print("Clients can connect now, but won't receive data until you press ENTER")
                input("Press ENTER to start transmission...")
                generator.start_transmission()
                print("Transmission started!")
            else:
                print("\nTransmission started automatically")
                print("Press Ctrl+C to stop the server\n")
            
            while generator.running:
                try:
                    conn, addr = s.accept()
                    client_thread = threading.Thread(
                        target=handle_client,
                        args=(conn, addr, generator)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if generator.running:
                        print(f"Server accept error: {str(e)}")
    
    except KeyboardInterrupt:
        print("\nServer shutdown requested...")
    finally:
        generator.stop()
        update_thread.join(timeout=2)
        print("Server stopped gracefully")


if __name__ == "__main__":
    """
    Entry point for the NMEA TCP server CLI.
    Parses command-line arguments and starts the server.
    """
    parser = argparse.ArgumentParser(
        description="NMEA TCP Server - Simulates GPS data transmission",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("port", type=int, help="TCP port to listen on")
    parser.add_argument("--method", type=str, required=True, nargs='+',
                      help="Generation method and parameters\n"
                           "Format: <method> [params...]\n"
                           "Examples:\n"
                           "  generate 55.7522 37.6156 [speed=10.0] [interval=1.0]\n"
                           "  route path/to/route.json")
    parser.add_argument("--wait-for-keypress", action="store_true",
                      help="Wait for keypress before starting transmission")
    
    args = parser.parse_args()
    
    if not args.method:
        print("Error: Method must be specified")
        sys.exit(1)
    
    method_type: str = args.method[0]
    method_params: List[Any] = args.method[1:] if len(args.method) > 1 else []

    try:
        run_server(
            port=args.port,
            method_type=method_type,
            method_params=method_params,
            wait_for_keypress=args.wait_for_keypress
        )
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
