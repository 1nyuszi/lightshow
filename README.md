# lightshow
Python lightshow

## Graphical editor

Launch `python editor.py` (or `py editor.py` on Windows) to open Lightshow Studio.
It uses Python's built-in Tkinter; editing does not require a bulb connection.

Create a show with **New**, or use **Open** to edit an existing show. Select a
step and choose a pastel color or a custom color, adjust brightness, and set
how many seconds it should hold. **Apply to step** updates the selected step;
settings also apply when selecting another step or saving. White light,
brightness changes, on/off, and pauses are available in the step type menu.

Use **Add**, **Duplicate**, **Delete**, and the arrow buttons to arrange your
sequence. **Undo** and **Redo** recover editing changes. **Preview show** plays
the sequence on screen, with optional looping. Screen colors are approximate;
the preview does not control your room lights.

**Save** and **Save as** create files compatible with the existing player.
The editor keeps the file format behind the scenes and preserves imported
comments. Existing pace changes appear as pauses where needed to preserve
the original playback timing. Saved files may be formatted differently.

To play a saved show on the bulb, use your configured terminal, for example:
`python lightshow.py scripts/harmonic.csv`.

Run all tests from the repository root with `python -m unittest discover -v`.
Tests live in the `test/` folder.
