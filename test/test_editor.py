import csv
import io
from pathlib import Path
import unittest

from editor_model import Step, appearance, dumps, loads, swatch


def player_events(source):
    """Simulate the existing player's actions and sleeps, including SPEED sleeps."""
    events, elapsed, delay = [], 0, 0
    for row in csv.reader(io.StringIO(source)):
        if not row or row[0].strip().startswith("#"):
            continue
        if row[0] == "SPEED":
            delay = float(row[1]) / 1000
        else:
            events.append((round(elapsed, 6), row))
        elapsed += delay
    return events, round(elapsed, 6)


class EditingTests(unittest.TestCase):
    def test_existing_shows_keep_actions_and_timing(self):
        for path in (Path(__file__).resolve().parents[1] / "scripts").glob("*.csv"):
            with self.subTest(path=path):
                source = path.read_text(encoding="utf-8-sig")
                steps, comments = loads(source)
                self.assertEqual(player_events(source), player_events(dumps(steps, comments)))

    def test_new_steps_keep_holds_after_reopening(self):
        steps = [Step(), Step("White light", [2700, 60], 1.25),
                 Step("Brightness", [40], 0), Step("Turn off", [], 3)]
        reopened, _ = loads(dumps(steps))
        self.assertEqual(reopened, steps)

    def test_every_step_type_and_comments(self):
        steps = [Step(), Step("White light", [2700, 60], 1),
                 Step("White tone", [4000], 0.5), Step("Brightness", [20], 2),
                 Step("Turn off", [], 1), Step("Pause", [], 3), Step("Turn on", [], 0)]
        source = dumps(steps, ["# My show"])
        reopened, comments = loads(source)
        self.assertEqual(comments, ["# My show"])
        self.assertEqual(player_events(source), player_events(dumps(reopened, comments)))
        self.assertEqual(player_events(source)[1], 9.5)

    def test_bad_imports_fail_with_line_numbers(self):
        for row in ("SPEED,nan", "SPEED,-1", "HSV,400,40,80", "HSV,30,40",
                    "OFF,1", "WHITE,0,90", "BRIGHT,101", "UNKNOWN,1"):
            with self.subTest(row=row):
                with self.assertRaisesRegex(ValueError, "line 2"):
                    loads("# Test\n" + row)

    def test_preview_relative_brightness_and_power(self):
        state = appearance(Step("Color", [0, 100, 100]))
        self.assertEqual(swatch(state), "#ff0000")
        state = appearance(Step("Brightness", [50]), state)
        self.assertEqual(swatch(state), "#800000")
        state = appearance(Step("Turn off", []), state)
        self.assertEqual(swatch(state), "#000000")
        self.assertEqual(swatch(appearance(Step("Turn on", []), state)), "#800000")


if __name__ == "__main__":
    unittest.main()
