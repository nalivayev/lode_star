# Lode Star NMEA TCP Server

This project provides a simple TCP server that generates and streams NMEA GPS sentences (RMC and GGA) to connected clients. It is useful for simulating GPS data for testing navigation software or hardware.

## Features

- Generates synthetic NMEA sentences (RMC and GGA) with configurable start position and speed.
- Simulates movement along a circular path or along a route from a GeoJSON file.
- Thread-safe and supports multiple simultaneous client connections.
- Cross-platform (no admin rights required).
- Configurable update interval (for synthetic mode).
- Option to start transmission after pressing ENTER.

## Requirements

- Python 3.7+
- No external dependencies (uses only standard library)

## Installation

Install the package in editable/development mode:

```sh
pip install -e .
```

Or install as a regular package:

```sh
pip install .
```

After installation, the `lode-star` command will be available in your terminal.

## Usage

Run the server from the command line:

```sh
lode-star <port> --method generate <lat> <lon> [speed=10.0] [interval=1.0] [--wait-for-keypress]
lode-star <port> --method route <path/to/route.json> [--wait-for-keypress]
```

Or, if not installed, you can run directly:

```sh
python -m lode_star.cli <port> --method generate <lat> <lon> [speed=10.0] [interval=1.0] [--wait-for-keypress]
python -m lode_star.cli <port> --method route <path/to/route.json> [--wait-for-keypress]
```

### Arguments

- `<port>`: TCP port to listen on (e.g., `5000`)
- `--method generate <lat> <lon> [speed=10.0] [interval=1.0]`: Synthetic movement mode
  - `lat`: Initial latitude (e.g., `55.7522`)
  - `lon`: Initial longitude (e.g., `37.6156`)
  - `speed=...`: (optional, string) Speed in **kilometers per hour** (default: `10.0`).  
    **Note:** Must be passed as a string in the method list, e.g. `speed=15`
  - `interval=...`: (optional, string) Position update interval in seconds (default: `1.0`).  
    **Note:** Must be passed as a string in the method list, e.g. `interval=0.5`
- `--method route <path/to/route.json>`: Route playback mode using GeoJSON  
  - `interval` is **not used** in this mode; all timing, speed, and stops are set in the GeoJSON file.
- `--wait-for-keypress`: Wait for ENTER before starting transmission

### Examples

```sh
lode-star 5000 --method generate 55.7522 37.6156 speed=15 interval=0.5 --wait-for-keypress
lode-star 5000 --method route ./route.geojson --wait-for-keypress
```

The first command starts the server on port 5000, simulates movement from Moscow at 15 km/h, updates every 0.5 seconds, and waits for you to press ENTER before sending data to clients.

The second command starts the server in route mode, playing back a route from `route.geojson`. All intervals, speeds, and stops are defined in the GeoJSON file; the `interval` parameter is ignored in this mode.

## Connecting Clients

Any TCP client (e.g., `telnet`, `nc`, or your application) can connect to the specified port to receive live NMEA sentences.

Example using `nc` (netcat):

```sh
nc localhost 5000
```

## License  
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
