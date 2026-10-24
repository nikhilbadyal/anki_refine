"""M0 verification probe. Development only; never packaged or shipped.

Inert unless the dev launcher sets REFINE_M0_OUT. Even then it refuses to
touch a profile outside an `.anki-dev` base folder (see probe.py).
"""

import os

if os.environ.get("REFINE_M0_OUT"):
    from . import probe

    probe.install(os.environ["REFINE_M0_OUT"])
