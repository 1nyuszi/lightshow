import argparse
import asyncio
import csv
import os
from pathlib import Path
import random
from kasa import Discover

async def run_lighting_script(filename, host, username, password):
    print(f"Connecting to Tapo bulb at {host}...")
    try:
        dev = await Discover.discover_single(
            host, username=username, password=password
        )
        await dev.update()
        print(f"Successfully connected to: {dev.alias or dev.model}\n")
    except Exception as e:
        print(f"Failed to connect to device: {e}")
        return

    print(f"Looping playback of '{filename}' (press Ctrl+C to stop)...\n")

    while True:
        # Reset the speed at the beginning of each playback.
        current_delay = 0.0
        has_commands = False
        with open(filename, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            
            for row_num, row in enumerate(reader, start=1):
                # Skip empty lines OR lines that start with a comment (#)
                if not row or row[0].strip().startswith('#'):
                    continue
                
                has_commands = True
                command = row[0].strip().upper()
                print(f"Line {row_num}: Executing {row}")

                try:
                    if command == "SPEED":
                        # Convert milliseconds to seconds for asyncio.sleep
                        current_delay = float(row[1]) / 1000.0

                    elif command == "HSV":
                        hue = int(row[1])
                        saturation = int(row[2])
                        brightness = int(row[3])
                        await dev.turn_on()
                        await dev.set_hsv(hue, saturation, brightness)

                    elif command == "WHITE":
                        temp = int(row[1])
                        brightness = int(row[2])
                        await dev.turn_on()
                        await dev.set_color_temp(temp, brightness=brightness)

                    elif command == "TEMP":
                        temp = int(row[1])
                        await dev.turn_on()
                        await dev.set_color_temp(temp)

                    elif command == "BRIGHT":
                        brightness = int(row[1])
                        await dev.turn_on()
                        await dev.set_brightness(brightness)

                    elif command == "OFF":
                        await dev.turn_off()

                    elif command == "ON":
                        await dev.turn_on()

                    else:
                        print(f"  -> Warning: Unknown command '{command}'")

                    # Apply the delay defined by the SPEED command
                    if current_delay > 0:
                        await asyncio.sleep(current_delay)

                except Exception as e:
                    print(f"  -> Error executing command {row}: {e}")

        if not has_commands:
            print("No commands found in script; stopping playback.")
            return
        await asyncio.sleep(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Loop a CSV lighting script.")
    parser.add_argument(
        "filename", nargs="?", type=Path,
        help="CSV file to play; defaults to a random CSV from the scripts folder.",
    )
    args = parser.parse_args()
    filename = args.filename
    if filename is None:
        scripts_dir = Path(__file__).resolve().parent / "scripts"
        candidates = sorted(
            path for path in scripts_dir.glob("*")
            if path.is_file() and path.suffix.lower() == ".csv"
        )
        if not candidates:
            parser.error(f"No CSV files found in {scripts_dir}")
        filename = random.choice(candidates)
    if not filename.is_file():
        parser.error(f"Script file does not exist: {filename}")

    required_variables = ("KASA_HOST", "KASA_USERNAME", "KASA_PASSWORD")
    missing_variables = [name for name in required_variables if not os.environ.get(name)]
    if missing_variables:
        raise SystemExit(
            "Missing required environment variables: " + ", ".join(missing_variables)
        )
    asyncio.run(run_lighting_script(
        filename,
        os.environ["KASA_HOST"],
        os.environ["KASA_USERNAME"],
        os.environ["KASA_PASSWORD"],
    ))
