# Lode Star NMEA TCP Server

This project provides a simple TCP server that generates and streams NMEA GPS sentences (RMC and GGA) to connected clients. It is useful for simulating GPS data for testing navigation software or hardware.

## Features

- Generates synthetic NMEA sentences (RMC and GGA) with configurable start position and speed.
- Simulates movement along a circular path.
- Thread-safe and supports multiple simultaneous client connections.
- Cross-platform (no admin rights required).
- Configurable update interval.
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
lode-star <port> --method generate <lat> <lon> [speed] [--interval <seconds>] [--wait-for-keypress]
```

Or, if not installed, you can run directly:

```sh
python -m lode_star.cli <port> --method generate <lat> <lon> [speed] [--interval <seconds>] [--wait-for-keypress]
```

### Arguments

- `<port>`: TCP port to listen on (e.g., `5000`)
- `--method generate <lat> <lon> [speed]`: Generation method and parameters
  - `lat`: Initial latitude (e.g., `55.7522`)
  - `lon`: Initial longitude (e.g., `37.6156`)
  - `speed`: (optional) Speed in knots (default: `5.0`)
- `--interval <seconds>`: Position update interval in seconds (default: `1.0`)
- `--wait-for-keypress`: Wait for ENTER before starting transmission

### Example

```sh
lode-star 5000 --method generate 55.7522 37.6156 10 --interval 0.5 --wait-for-keypress
```

This command starts the server on port 5000, simulates movement from Moscow at 10 knots, updates every 0.5 seconds, and waits for you to press ENTER before sending data to clients.

## Connecting Clients

Any TCP client (e.g., `telnet`, `nc`, or your application) can connect to the specified port to receive live NMEA sentences.

Example using `nc` (netcat):

```sh
nc localhost 5000
```

## License

MIT License
