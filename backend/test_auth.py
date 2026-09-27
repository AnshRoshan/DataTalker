# backend/test_auth.py
# Assert-based self-check for the API-key auth dependency.
#   uv run --directory backend python test_auth.py
import os
from fastapi import HTTPException
from api.dependencies import require_api_key


def status(auth):
    # request is only consulted when DATATALKER_REQUIRE_LOGIN is on (see
    # test_auth_login.py); the shared-key path never touches it.
    try:
        require_api_key(request=None, authorization=auth)
        return 200
    except HTTPException as e:
        return e.status_code


# No key configured on the server -> deny everything (503, not silently open).
os.environ.pop("DATATALKER_API_KEY", None)
assert status("Bearer anything") == 503

# Key configured -> only the exact "Bearer <key>" passes.
os.environ["DATATALKER_API_KEY"] = "s3cret"
assert status(None) == 401
assert status("Bearer wrong") == 401
assert status("s3cret") == 401           # missing "Bearer " prefix
assert status("Bearer s3cret") == 200    # correct

print("auth: all assertions passed")
