"""Lightshow editing and playback data, independent of the desktop interface."""
from dataclasses import dataclass, field
import colorsys
import csv
import io
import math


KINDS = ("Color", "White light", "Brightness", "White tone", "Turn on", "Turn off", "Pause")


@dataclass
class Step:
    kind: str = "Color"
    values: list = field(default_factory=lambda: [330, 35, 80])
    seconds: float = 2.0


def validate(step):
    if step.kind not in KINDS:
        raise ValueError("Choose a step type.")
    if not math.isfinite(step.seconds) or not 0 <= step.seconds <= 86400:
        raise ValueError("Hold time must be between 0 and 86400 seconds.")
    bounds = {"Color": [(0, 360), (0, 100), (0, 100)],
              "White light": [(1, 100000), (0, 100)],
              "White tone": [(1, 100000)], "Brightness": [(0, 100)],
              "Turn on": [], "Turn off": [], "Pause": []}[step.kind]
    if len(step.values) != len(bounds):
        raise ValueError("This step has missing settings.")
    for value, (low, high) in zip(step.values, bounds):
        if not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"A setting must be a whole number between {low} and {high}.")


def loads(source):
    steps, comments = [], []
    delay = 0
    types = {"HSV": "Color", "WHITE": "White light", "TEMP": "White tone",
             "BRIGHT": "Brightness", "ON": "Turn on", "OFF": "Turn off"}
    for number, line in enumerate(source.splitlines(), 1):
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            comments.append(line)
            continue
        try:
            row = next(csv.reader([line], strict=True))
            command = row[0].strip().upper()
            if command == "SPEED":
                if len(row) != 2:
                    raise ValueError("A pace setting needs one value.")
                delay = float(row[1]) / 1000
                step = Step("Pause", [], delay)
                validate(step)
                # The existing player also waits after a pace setting.
                if delay:
                    if steps and steps[-1].kind != "Pause" and steps[-1].seconds == 0:
                        steps[-1].seconds = delay
                    else:
                        steps.append(step)
            elif command in types:
                step = Step(types[command], [int(v) for v in row[1:]], delay)
                validate(step)
                steps.append(step)
            else:
                raise ValueError("Unrecognized light setting.")
        except (ValueError, csv.Error) as error:
            raise ValueError(f"Cannot open line {number}: {error}") from error
    return steps, comments


def dumps(steps, comments=()):
    """Encode explicit holds without adding the player's extra SPEED delays."""
    output = io.StringIO(newline="")
    for comment in comments:
        output.write(comment + "\n")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["SPEED", 0])
    commands = {"Color": "HSV", "White light": "WHITE", "White tone": "TEMP",
                "Brightness": "BRIGHT", "Turn on": "ON", "Turn off": "OFF"}
    for step in steps:
        validate(step)
        if step.kind != "Pause":
            writer.writerow([commands[step.kind], *step.values])
        if step.seconds:
            writer.writerow(["SPEED", format(step.seconds * 1000, ".12g")])
            writer.writerow(["SPEED", 0])
    return output.getvalue()


def white_rgb(kelvin):
    t = max(1000, min(40000, kelvin)) / 100
    red = 255 if t <= 66 else 329.698727446 * (t - 60) ** -0.1332047592
    green = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * (t - 60) ** -0.0755148492
    blue = 255 if t >= 66 else (0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307)
    return tuple(max(0, min(255, c)) / 255 for c in (red, green, blue))


def appearance(step, state=((1, 1, 1), 80, True)):
    rgb, brightness, enabled = state
    if step.kind == "Color":
        h, s, brightness = step.values
        rgb, enabled = colorsys.hsv_to_rgb(h / 360, s / 100, 1), True
    elif step.kind in ("White light", "White tone"):
        rgb, enabled = white_rgb(step.values[0]), True
        if step.kind == "White light":
            brightness = step.values[1]
    elif step.kind == "Brightness":
        brightness, enabled = step.values[0], True
    elif step.kind in ("Turn on", "Turn off"):
        enabled = step.kind == "Turn on"
    return rgb, brightness, enabled


def swatch(state):
    rgb, brightness, enabled = state
    scale = brightness / 100 if enabled else 0
    return "#" + "".join(f"{round(c * scale * 255):02x}" for c in rgb)
