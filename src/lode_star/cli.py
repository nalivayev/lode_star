import argparse
import math
import socket
import threading
import time
from datetime import datetime, timezone
import sys
from abc import ABC, abstractmethod
from typing import Any, List, Tuple


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
            
            lat_deg: int = int(self.lat)
            lat_min: float = abs((self.lat - lat_deg) * 60)
            lat_dir: str = 'N' if self.lat >= 0 else 'S'
            
            lon_deg: int = int(self.lon)
            lon_min: float = abs((self.lon - lon_deg) * 60)
            lon_dir: str = 'E' if self.lon >= 0 else 'W'
            
            rmc: str = (
                f"GPRMC,{time_str},A,{abs(lat_deg):02d}{lat_min:09.6f},{lat_dir},"
                f"{abs(lon_deg):03d}{lon_min:09.6f},{lon_dir},0.0,0.0,{date_str},,,A"
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
            
            lat_deg: int = int(self.lat)
            lat_min: float = abs((self.lat - lat_deg) * 60)
            lat_dir: str = 'N' if self.lat >= 0 else 'S'
            
            lon_deg: int = int(self.lon)
            lon_min: float = abs((self.lon - lon_deg) * 60)
            lon_dir: str = 'E' if self.lon >= 0 else 'W'
            
            gga: str = (
                f"GPGGA,{time_str},{abs(lat_deg):02d}{lat_min:09.6f},{lat_dir},"
                f"{abs(lon_deg):03d}{lon_min:09.6f},{lon_dir},1,08,1.0,0.0,M,0.0,M,,"
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
    """
    def __init__(self, initial_lat: float, initial_lon: float, speed_knots: float = 5.0) -> None:
        """
        Initialize the dynamic generator.
        Args:
            initial_lat (float): Initial latitude.
            initial_lon (float): Initial longitude.
            speed_knots (float): Speed in knots.
        """
        super().__init__()
        self.lat: float = initial_lat
        self.lon: float = initial_lon
        self.speed_knots: float = speed_knots
        self.heading: int = 0

    def update_position(self) -> None:
        """
        Update the position based on current heading and speed.
        Simulates circular movement by incrementing the heading.
        """
        while self.running:
            with self.lock:
                if self.transmitting:
                    speed_deg_per_sec: float = self.speed_knots * 1.852 / 111.32 / 3600
                    distance: float = speed_deg_per_sec * self.interval_sec
                    rad: float = math.radians(self.heading)
                    
                    self.lat += distance * math.cos(rad)
                    self.lon += distance * math.sin(rad)
                    self.heading = (self.heading + 2) % 360
                
                self.time = datetime.now(timezone.utc)
            
            time.sleep(self.interval_sec)


def create_generator(method_type: str, *method_params: Any) -> NMEAGenerator:
    """
    Factory function to create an NMEA generator.
    Args:
        method_type (str): The generation method ('generate').
        *method_params: Parameters for the generator.
    Returns:
        NMEAGeneratorBase: An instance of a generator.
    Raises:
        ValueError: If parameters are invalid or method is unknown.
    """
    if method_type == 'generate':
        if len(method_params) < 2:
            raise ValueError("For generate method you must specify lat and lon")
        speed: float = float(method_params[2]) if len(method_params) > 2 else 5.0
        return DynamicNMEAGenerator(
            initial_lat=float(method_params[0]),
            initial_lon=float(method_params[1]),
            speed_knots=speed
        )
    else:
        raise ValueError(f"Unknown method: {method_type}")

def handle_client(conn: socket.socket, addr: Tuple[str, int], generator: NMEAGenerator) -> None:
    """
    Handle a client connection: send NMEA sentences to the client.
    Args:
        conn (socket.socket): The client socket.
        addr (tuple): The client address.
        generator (NMEAGeneratorBase): The NMEA generator instance.
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

def run_server(
    port: int,
    interval_sec: float,
    method_type: str,
    method_params: List[Any],
    wait_for_keypress: bool
) -> None:
    """
    Start the NMEA TCP server.
    Args:
        port (int): TCP port to listen on.
        interval_sec (float): Position update interval in seconds.
        method_type (str): Generation method.
        method_params (list): Parameters for the generator.
        wait_for_keypress (bool): Wait for ENTER before starting transmission.
    """
    try:
        generator: NMEAGenerator = create_generator(method_type, *method_params)
        generator.interval_sec = interval_sec
        
        if not wait_for_keypress:
            generator.start_transmission()
        
        update_thread: threading.Thread = threading.Thread(target=generator.update_position)
        update_thread.daemon = True
        update_thread.start()
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('0.0.0.0', port))
            s.listen(5)
            s.settimeout(1)
            
            print(f"\nNMEA TCP Server started on port {port}")
            print("=" * 40)
            print(f"Generation method: {method_type}")
            print(f"Initial position: {method_params[0]}° N, {method_params[1]}° E")
            if len(method_params) > 2:
                print(f"Speed: {method_params[2]} knots")
            print(f"Update interval: {interval_sec} sec")
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
                    client_thread: threading.Thread = threading.Thread(
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
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="NMEA TCP Server - Simulates GPS data transmission",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("port", type=int, help="TCP port to listen on")
    parser.add_argument("--interval", type=float, default=1.0,
                      help="Position update interval in seconds")
    parser.add_argument("--method", type=str, required=True, nargs='+',
                      help="Generation method and parameters\n"
                           "Format: <method> [params...]\n"
                           "Examples:\n"
                           "  generate 55.7522 37.6156 [speed=5.0]")
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
            interval_sec=args.interval,
            method_type=method_type,
            method_params=method_params,
            wait_for_keypress=args.wait_for_keypress
        )
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
