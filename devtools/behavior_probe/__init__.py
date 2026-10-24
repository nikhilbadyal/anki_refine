"""Behaviour probe (keyboard, live settings, card-area integrity). Development
only; never packaged or shipped.

Inert unless the dev launcher sets REFINE_BEHAVIOR_OUT. Even then it refuses to
touch a profile outside an `.anki-dev` base folder (see probe.py).
"""

import os

if os.environ.get("REFINE_BEHAVIOR_OUT"):
    from . import probe

    probe.install(os.environ["REFINE_BEHAVIOR_OUT"])
