"""UI screenshot probe. Development only; never packaged or shipped.

Inert unless the dev launcher sets REFINE_UI_OUT. Even then it refuses to
touch a profile outside an `.anki-dev` base folder (see probe.py).
"""

import os

if os.environ.get("REFINE_UI_OUT"):
    from . import probe

    probe.install(os.environ["REFINE_UI_OUT"])
