import argparse
import sys

from lode_server.server import run_server


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
