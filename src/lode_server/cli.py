import argparse
import socket
import time
import sys
import threading
from typing import Any
from queue import Queue

from lode_server.generator import LodeGenerator, NMEAEncoder, Position
from lode_server.generators import get_generator


class ClientThread(threading.Thread):
    """Thread for handling client connections and broadcasting data."""
    
    def __init__(self, port: int):
        super().__init__(daemon=True)
        self.port = port
        self.clients = []
        self.data_queue = Queue()
        self.running = True
        self.lock = threading.Lock()
        self.server_socket = None

    def _broadcast(self, rmc: str, gga: str) -> None:
        """Send data to all connected clients."""
        with self.lock:
            for conn in self.clients[:]:
                try:
                    conn.sendall(rmc.encode('ascii'))
                    conn.sendall(gga.encode('ascii'))
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    self.clients.remove(conn)

    def _cleanup(self) -> None:
        """Clean up resources."""
        with self.lock:
            for conn in self.clients:
                try:
                    conn.close()
                except Exception:
                    pass
            self.clients.clear()
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

    def run(self) -> None:
        """Main thread loop for accepting clients and broadcasting data."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1)

            while self.running:
                try:
                    # Accept new clients
                    try:
                        conn, addr = self.server_socket.accept()
                        with self.lock:
                            self.clients.append(conn)
                    except socket.timeout:
                        pass

                    # Process data from queue
                    while not self.data_queue.empty():
                        rmc, gga = self.data_queue.get()
                        self._broadcast(rmc, gga)

                except Exception as e:
                    if self.running:
                        pass  # Silent error handling
        finally:
            self._cleanup()

    def add_data(self, rmc: str, gga: str) -> None:
        """Add data to the broadcast queue."""
        self.data_queue.put((rmc, gga))

    def stop(self) -> None:
        """Stop the thread gracefully."""
        self.running = False
        self._cleanup()


class LodeServer:
    """Main server class handling client connections and data broadcasting."""
    
    def __init__(self, port: int, source: str, params: list[Any], wait_for_keypress: bool):
        """
        Initialize the Lode server.

        Args:
            port: TCP port to listen on
            source: Generator source type (dynamic, geojson, csv, etc)
            params: Parameters for the generator
            wait_for_keypress: Whether to wait for keypress before starting transmission
        """
        self.port = port
        self.source = source
        self.params = params
        self.wait_for_keypress = wait_for_keypress
        self.client_handler = None
        self.generator = None
        self.encoder = NMEAEncoder()
        self.counter = 1

    def _create_generator(self, source: str, *params: Any) -> LodeGenerator:
        """
        Factory function to create an Lode generator using the plugin system.

        Args:
            source: The generator source type (dynamic, geojson, csv, etc)
            *params: Parameters for the generator

        Returns:
            An instance of the selected generator
        """
        generator_class = get_generator(source)
        return generator_class(*params)

    def _print_data(self, data: Position) -> None:
        """
        Print formatted position data to the console, updating output in-place.

        Args:
            data: Position object with navigation data
        """
        description = f"{'Description:':>15}\t{data.description}\n" if data.description else f"{'':>15}\t{'':<12}\n"
        output = (
            f"\n{'Point, #:':>15}\t{self.counter}\n"
            f"{'Latitude, deg:':>15}\t{data.lat:<12.6f}\n"
            f"{'Longitude, deg:':>15}\t{data.lon:<12.6f}\n"
            f"{'Speed, km/h:':>15}\t{data.speed:<12.2f}\n"
            f"{'Elevation, m:':>15}\t{data.elevation:<12.2f}\n"
            f"{'Time:':>15}\t{data.time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{description}\n"
        )
        print("\033[F" * (output.count('\n')), end="")
        print(output, end="", flush=True)
        self.counter += 1

    def run(self) -> None:
        """Start the Lode TCP server and begin data transmission."""
        try:
            # Start client handler thread
            self.client_handler = ClientThread(self.port)
            self.client_handler.start()

            self.generator = self._create_generator(self.source, *self.params)

            print(f"\nLode TCP Server started on port {self.port}")
            print("=" * 40)
            print(f"Generator source: {self.source}")
            if self.params:
                print(f"Source parameters: {', '.join(str(p) for p in self.params)}")
            print(f"Wait for keypress: {'Yes' if self.wait_for_keypress else 'No'}")
            print("=" * 40)

            if self.wait_for_keypress:
                print("\nServer is waiting for ENTER to start transmission...")
                input()
            print("Transmission started!")
            print("Press Ctrl+C to stop the server\n")

            print("\n" * 7)
            while True:
                try:
                    last_time = time.perf_counter()
                    data = next(self.generator)

                    self._print_data(data)

                    rmc = self.encoder.encode_rmc(data)
                    gga = self.encoder.encode_gga(data)
                    self.client_handler.add_data(rmc, gga)

                    current_time = time.perf_counter()
                    elapsed = current_time - last_time
                    remaining_time = data.duration - elapsed

                    if remaining_time > 0.001:
                        time.sleep(remaining_time)
                    if data.transition == "manual":
                        print("Press ENTER to proceed to the next point", end="", flush=True)
                        input()
                        print("\n" * 8)

                except KeyboardInterrupt:
                    break
                except StopIteration:
                    break
                except Exception as e:
                    print(f"Server error: {str(e)}")

        except Exception as e:
            print(f"Server initialization error: {str(e)}")
        finally:
            print("\nServer stopped gracefully")
            if self.client_handler:
                self.client_handler.stop()
                self.client_handler.join(timeout=1)


def run_server(
    port: int,
    source: str,
    params: list[Any],
    wait_for_keypress: bool
) -> None:
    """
    Start the Lode TCP server.

    Args:
        port: TCP port to listen on
        source: Generator source type (dynamic, geojson, csv, etc)
        params: Parameters for the generator
        wait_for_keypress: Whether to wait for keypress before starting transmission
    """
    server = LodeServer(port, source, params, wait_for_keypress)
    server.run()

def main():
    parser = argparse.ArgumentParser(
        description="Lode TCP Server - Simulates GPS data transmission",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("port", type=int, help="TCP port to listen on")
    parser.add_argument("--source", type=str, required=True, nargs='+',
                      help="Generator source type and parameters\n"
                           "Format: <source> [params...]\n"
                           "Examples:\n"
                           "  dynamic 55.7522 37.6156 [speed=10.0] [duration=1.0]\n"
                           "  geojson path/to/route.json\n"
                           "  csv path/to/route.csv\n"
                           "  nmea path/to/route.nmea")
    parser.add_argument("--wait-for-keypress", action="store_true",
                      help="Wait for keypress before starting transmission")
    
    args = parser.parse_args()
    
    if not args.source:
        print("Error: Source must be specified")
        sys.exit(1)
    
    source = args.source[0]
    params = args.source[1:] if len(args.source) > 1 else []

    try:
        run_server(args.port, source, params, args.wait_for_keypress)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
