"""Streamlit Cloud entry point for the Career AI project.

The actual application is kept in the ``career mentor`` folder. Loading it
from this root file lets Streamlit Cloud run the project consistently even
though the folder name contains a space.
"""

from pathlib import Path
import runpy


runpy.run_path(Path(__file__).parent / "career mentor" / "app.py", run_name="__main__")
