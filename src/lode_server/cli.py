import argparse
import socket
import time
import sys
from typing import Any, List

from lode_server.generator import NMEAGenerator, NMEAEncoder, Position
from lode_server.generators import get_generator


def create_generator(method: str, *params: Any) -> NMEAGenerator:
    """
    Factory function to create an NMEA generator using plugin system.
    """
    generator_class = get_generator(method)
    return generator_class(*params)

def print_data(data: Position, counter: int) -> None:
    """
    Print formatted position data to the console, updating output in-place.

    Args:
        data (Position): Position object with navigation data.
        counter (int): Point counter for display.
    """
    output = (
        f"\n{'Point, #:':>15}\t{counter}\n"
        f"{'Latitude, deg:':>15}\t{data.lat:<12.6f}\n"
        f"{'Longitude, deg:':>15}\t{data.lon:<12.6f}\n"
        f"{'Speed, km/h:':>15}\t{data.speed:<12.2f}\n"
        f"{'Elevation, m:':>15}\t{data.elevation:<12.2f}\n"
        f"{'Time:':>15}\t{data.time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"{'Description:':>15}\t{data.description}\n\n"
    )
    print("\033[F" * (output.count('\n')), end="")
    print(output, end="", flush=True)

def broadcast_data(data: Position, encoder: NMEAEncoder, clients: list) -> None:
    """
    Send NMEA data to all connected clients, removing failed connections.

    Args:
        data (Position): Position object to encode and send.
        encoder (NMEAEncoder): Encoder for NMEA sentences.
        clients (list): List of active client sockets.
    """
    # Generate NMEA sentences once for all clients
    rmc = encoder.encode_rmc(data)
    gga = encoder.encode_gga(data)
    
    # Send to all clients
    for conn in clients[:]:  # Iterate over a copy of the list
        try:
            conn.sendall(rmc.encode('ascii'))
            conn.sendall(gga.encode('ascii'))
        except Exception as e:
            print(f"Connection error: {str(e)} - removing client")
            try:
                conn.close()  # Ensure connection is properly closed
            except Exception as close_error:
                print(f"Error closing connection: {str(close_error)}")
            clients.remove(conn)  # Remove from active clients list

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
    clients = []
    try:
        generator = create_generator(method_type, *method_params)
        encoder = NMEAEncoder()
        point_counter = 1


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
            elif method_type == 'route':
                print(f"Route file: {method_params[0]}")
            elif method_type == 'csv':
                print(f"CSV file: {method_params[0]}")
            print(f"Wait for keypress: {'Yes' if wait_for_keypress else 'No'}")
            print("=" * 40)

            if wait_for_keypress:
                print("\nServer is waiting for ENTER to start transmission...")
                print("Clients can connect now, but won't receive data until you press ENTER")
                print("Press ENTER to start transmission...")
                input()
                print("Transmission started!")
            else:
                print("\nTransmission started automatically")
                print("Press Ctrl+C to stop the server\n")

            print("\n" * 7)
            while True:
                try:
                    # Accept new clients
                    try:
                        conn, addr = s.accept()
                        clients.append(conn)
                        print(f"Client connected: {addr}")
                    except socket.timeout:
                        pass

                    # Main data loop
                    data = next(generator)

                    print_data(data, point_counter)

                    point_counter += 1
                    broadcast_data(data, encoder, clients)
                    time.sleep(data.duration)
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

    except KeyboardInterrupt:
        print("\nServer shutdown requested...")
    finally:
        print("Server stopped gracefully")
        # Close all client connections
        for conn in clients:
            try:
                conn.close()
            except Exception as e:
                print(f"Error closing client connection: {str(e)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="NMEA TCP Server - Simulates GPS data transmission",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("port", type=int, help="TCP port to listen on")
    parser.add_argument("--method", type=str, required=True, nargs='+',
                      help="Generation method and parameters\n"
                           "Format: <method> [params...]\n"
                           "Examples:\n"
                           "  generate 55.7522 37.6156 [speed=10.0] [duration=1.0]\n"
                           "  route path/to/route.json")
    parser.add_argument("--wait-for-keypress", action="store_true",
                      help="Wait for keypress before starting transmission")
    
    args = parser.parse_args()
    
    if not args.method:
        print("Error: Method must be specified")
        sys.exit(1)
    
    method_type = args.method[0]
    method_params = args.method[1:] if len(args.method) > 1 else []

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
