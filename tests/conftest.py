"""Point every test at an isolated, throwaway data directory so tests never touch the
real jarvis/data/ (or each other's SQLite DB) -- this must run before `jarvis.config` (or
anything importing it) is first imported, since paths/dirs are set up at import time."""
import os
import tempfile

_tmp_dir = tempfile.mkdtemp(prefix="jarvis_test_")
os.environ["JARVIS_DATA_DIR"] = _tmp_dir
