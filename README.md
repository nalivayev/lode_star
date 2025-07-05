# Lode Star TCP Server

This project simulates GNSS data transmission over TCP.  
It supports several generator sources: dynamic simulation (circular movement), route-based playback from a GeoJSON file, playback from a CSV file, and playback from a file with NMEA sentences.

## Features

- **NMEA 0183 output** (RMC, GGA sentences)
- **Multiple generator sources**:
  - **dynamic**: Simulates circular movement from a given point with configurable speed (in km/h), radius, and duration per point
  - **geojson**: Plays back a route from a GeoJSON file, using per-point speed (in km/h), duration, transition mode, and description
  - **csv**: Plays back a route from a CSV file, using per-point speed, duration, transition mode, and description
  - **nmea**: Plays back a sequence of NMEA sentences from a text file (see below)
- **TCP server**: Multiple clients can connect and receive the same stream
- **Console output**: Each point's data is printed in a formatted table and updates in-place
- **Configurable start**: Optionally wait for user keypress before starting transmission

## Usage

```sh
python -m lode_server <port> --source <type> [params...] [--wait-for-keypress]
```

### Sources and Parameters

#### 1. Dynamic Generation (`dynamic`)

Simulates circular movement from a starting point.

**Syntax:**
```
dynamic <lat> <lon> [speed=<km/h>] [duration=<seconds>] [radius=<km>] [transition=<mode>]
```

- `lat`, `lon` — starting coordinates (float)
- `speed` — speed in km/h (default: 10.0)
- `duration` — time in seconds between points (default: 1.0)
- `radius` — radius of the circular path in km (default: 0.1)
- `transition` — transition mode: `auto` (default) or `manual`

**Example:**
```
python -m lode_server 10110 --source dynamic 55.7522 37.6156 speed=15.0 duration=2.0 radius=0.2 transition=manual
```

#### 2. GeoJSON Playback (`geojson`)

Plays back a route from a GeoJSON file.

**Syntax:**
```
geojson <path/to/route.json>
```

- Each point in the GeoJSON should have `speed` (km/h), `duration` (seconds), and optionally `transition` and `description` in its properties.

**Example:**
```
python -m lode_server 10110 --source geojson path/to/route.json
```

#### 3. CSV Playback (`csv`)

Plays back a route from a CSV file.

**Syntax:**
```
csv <path/to/route.csv>
```

- CSV columns: `point_number,latitude,longitude,speed,elevation,duration,transition,description`
- Only the first five columns are required; others are optional.

**Example:**
```
python -m lode_server 10110 --source csv path/to/route.csv
```

#### 4. NMEA File Playback (`nmea`)

Plays back a sequence of NMEA sentences from a text file.  
Each line in the file should be a valid NMEA sentence (e.g., `$GPRMC,...`, `$GPGGA,...`).  
Currently, only RMC and GGA sentences are guaranteed to be parsed; others are skipped with a warning.

**Syntax:**
```
nmea <path/to/nmea.txt>
```

**Example:**
```
python -m lode_server 10110 --source nmea path/to/nmea.txt
```

### Optional Flags

- `--wait-for-keypress` — Wait for user to press ENTER before starting transmission.

## Example Output

```
TCP Server started on port 10110
========================================
Generator source: dynamic
         Param 1: 55.7522
         Param 2: 37.6156
         Param 3: speed=15.0
         Param 4: duration=2.0
         Param 5: radius=0.2
         Param 6: transition=manual
Wait for keypress: No
========================================

      Point, #:	1
 Latitude, deg:	55.752200   
Longitude, deg:	37.615600   
   Speed, km/h:	10.00       
  Elevation, m:	0.00        
         Time:	2025-06-19 12:00:00
  Description:	
```

## GeoJSON Route Format

Each feature must be a Point with coordinates `[lon, lat]` and the following properties:

| Property     | Type    | Description                                                       |
|--------------|---------|-------------------------------------------------------------------|
| speed        | float   | Speed at this point in **km/h**.                                  |
| elevation    | float   | Elevation above sea level in meters.                              |
| duration     | float   | Duration to stay at this point, in seconds.                       |
| transition   | string  | (Optional) Transition mode: `"auto"` (default) or `"manual"`.     |
| description  | string  | (Optional) Comment or description for this point.                 |

**Example:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "speed": 15.0,
        "elevation": 100.1,
        "duration": 1.0,
        "transition": "manual",
        "description": "Start point"
      },
      "geometry": {
        "type": "Point",
        "coordinates": [37.61752, 55.75222]
      }
    }
  ]
}
```

## CSV Route Format

CSV columns:

```
number,latitude,longitude,speed,elevation,duration,transition,description
```

- Only the first five columns are required.
- `transition` and `description` are optional.
- Lines starting with `#` are treated as comments.

**Example:**
```
1,55.7522,37.6156,10.0,120.5,2.0,auto,"Moscow center"
2,55.7530,37.6200,12.0,121.0,3.0,manual,"Red Square"
```

## NMEA File Format

Each line must be a valid NMEA sentence (for example, `$GPRMC,...` or `$GPGGA,...`).  
Only RMC and GGA sentences are guaranteed to be parsed.  
If a line cannot be parsed, it will be skipped and a warning will be logged.

**Example:**
```
$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A
$GPGGA,123520,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47
```

## Plugin System

Lode Star uses a plugin system for generators. Each generator (for example, dynamic, geojson, csv, nmea) is implemented as a separate Python class and registered using a decorator. This makes it easy to add new generator types without modifying the core server code.

- To add a new generator, create a new Python file in `lode_server/generators/`, define a class that inherits from `LodeGenerator`, and register it with the `@register_generator("your_source_name")` decorator.
- The generator will be automatically discovered and available via the `--source` command-line option.

**Example:**
```python
from lode_server.generator import LodeGenerator, Position
from lode_server.generators import register_generator

@register_generator("my_custom")
class MyCustomGenerator(LodeGenerator):
    def __init__(self, *args):
        super().__init__()
        # your initialization

    def _update_position(self):
        # your logic
        return Position(...)
```

This approach allows you to extend the server with custom data sources or simulation logic, simply by dropping new generator modules into the `generators` directory.

## Notes

- **Speed is always specified in km/h** in all sources and in GeoJSON/CSV.
- The server prints each point's data and sends sentences to all connected clients.
- If `--wait-for-keypress` is used, the server will not start sending data until you press ENTER.
- For `transition="manual"` in GeoJSON or CSV or generator, the server will wait for ENTER before sending the next point.

---
