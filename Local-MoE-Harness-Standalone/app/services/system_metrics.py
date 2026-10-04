from __future__ import annotations

import importlib
import os
import sys

_module_name = ".system_metrics_windows" if os.name == "nt" else ".system_metrics_linux"
_impl = importlib.import_module(_module_name, __package__)
# Make the public platform facade the implementation module itself. Besides
# keeping imports simple, this preserves the long-standing test/extension
# contract where patching an attribute on app.services.system_metrics affects
# the globals used by functions defined in the platform implementation.
sys.modules[__name__] = _impl
