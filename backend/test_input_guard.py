# backend/test_input_guard.py
# Assert-based self-check for db_path confinement and db_url SSRF guard.
#   uv run --directory backend python test_input_guard.py
import os
import pathlib
import tempfile
from fastapi import HTTPException
from core.database import validate_database_path
from core.file_handler import is_url_fetch_safe

BACKEND = str(pathlib.Path(__file__).resolve().parent)  # default allowed dir is backend/

# --- db_path confinement (SEC-04) ---
hosp = os.path.join(BACKEND, "hospital.db")
assert validate_database_path(hosp) == os.path.realpath(hosp)  # bundled fixture is inside -> allowed

outside = tempfile.NamedTemporaryFile(suffix=".db", delete=False)  # system temp is outside backend/
outside.close()
try:
    try:
        validate_database_path(outside.name)
        assert False, "path outside the allowed dir must be rejected"
    except HTTPException as e:
        assert e.status_code == 403, e.status_code
finally:
    os.unlink(outside.name)

# --- db_url SSRF guard (SEC-03) ---
def safe(u):
    return is_url_fetch_safe(u)[0]

assert safe("https://8.8.8.8/db.sqlite")            # public IP literal is fine
assert not safe("http://127.0.0.1/x")               # loopback
assert not safe("http://169.254.169.254/latest/")   # link-local (cloud metadata)
assert not safe("http://10.0.0.5/x")                # private
assert not safe("http://192.168.1.10/x")            # private
assert not safe("ftp://8.8.8.8/x")                  # disallowed scheme
assert not safe("file:///etc/passwd")               # disallowed scheme

print("input_guard: all assertions passed")
