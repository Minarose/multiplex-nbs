# Contributing

Thank you for helping improve Multiplex-NBS.

## Questions and problems

Open an [issue](https://github.com/Minarose/multiplex-nbs/issues). For a bug, include
the version (`multiplex-nbs --version`, `help Contents` in MATLAB, or the app's sidebar),
your operating system, what you did, and the error message. Please do not attach
participant data; a small simulated example that shows the problem is ideal.

## Changes to the code

1. Fork the repository and create a branch.
2. Install in editable mode with the test extras: `pip install -e ".[plot]"`.
3. Run the tests: `python -m unittest discover -s tests`. Tests that open windows run
   only with `NBS_TEST_DESKTOP=1`.
4. If you change a docstring or MATLAB help text, regenerate the API pages with
   `python tools/build_api_docs.py`.
5. For MATLAB changes, run `mnbs_selftest` in MATLAB.
6. Open a pull request describing the change and how you tested it.

Statistical changes should come with a test that would fail without them. By
contributing you agree that your contribution is licensed under the GNU General Public
License v3 or later.
