import time

from typing import Any

from lode_server.generators import get_generator
from lode_server.core import Position, NMEAEncoder, LodeGenerator, ClientThread


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
        self._port = port
        self._source = source
        self._params = params
        self._wait_for_keypress = wait_for_keypress
        self._client_handler = None
        self._generator = None
        self._encoder = NMEAEncoder()
        
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
            f"{'Point, #:':>15}\t{data.index}\n"
            f"{'Latitude, deg:':>15}\t{data.lat:<12.6f}\n"
            f"{'Longitude, deg:':>15}\t{data.lon:<12.6f}\n"
            f"{'Speed, km/h:':>15}\t{data.speed:<12.2f}\n"
            f"{'Elevation, m:':>15}\t{data.elevation:<12.2f}\n"
            f"{'Time:':>15}\t{data.time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{description}"
        )
        print(output)

    def run(self) -> None:
        """Start the Lode TCP server and begin data transmission."""
        try:
            # Start client handler thread
            self.client_handler = ClientThread(self._port)
            self.client_handler.start()

            self.generator = self._create_generator(self._source, *self._params)

            print(f"\nLode TCP Server started on port {self._port}")
            print("=" * 40)
            print(f"Generator source: {self._source}")
            if self._params:
                print(f"Source parameters: {', '.join(str(p) for p in self._params)}")
            print(f"Wait for keypress: {'Yes' if self._wait_for_keypress else 'No'}")
            print("=" * 40)

            if self._wait_for_keypress:
                print("\nServer is waiting for ENTER to start transmission...")
                input()
            print("Transmission started!")
            print("Press Ctrl+C to stop the server\n")

            print("\n" * 1)
            while True:
                try:
                    last_time = time.perf_counter()
                    data = next(self.generator)

                    self._print_data(data)

                    rmc = self._encoder.encode_rmc(data)
                    gga = self._encoder.encode_gga(data)
                    self.client_handler.add_data(rmc, gga)

                    current_time = time.perf_counter()
                    elapsed = current_time - last_time
                    remaining_time = data.duration - elapsed

                    if remaining_time > 0.001:
                        time.sleep(remaining_time)
                    if data.transition == "manual":
                        print("Press ENTER to proceed to the next point", end="", flush=True)
                        input()

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
