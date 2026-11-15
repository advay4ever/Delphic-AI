"""Opt-in desktop credentials, using only native OS vault backends."""

import hashlib
import importlib
import json
from pathlib import Path
import sys
import threading


class DeviceCredentialError(Exception):
    """A deliberately non-secret message suitable for the settings dialog."""


def native_backend():
    choices = {
        "darwin": ("keyring.backends.macOS", "Keyring"),
        "win32": ("keyring.backends.Windows", "WinVaultKeyring"),
    }
    if sys.platform not in choices:
        return None
    module, name = choices[sys.platform]
    try:
        backend = getattr(importlib.import_module(module), name)()
        if backend.priority <= 0:
            return None
        if sys.platform == "win32":
            backend.persist = "local machine"
        return backend
    except Exception:
        # Never use keyring's configurable/plugin fallback (which may be plaintext).
        return None


class DeviceCredentialStore:
    def __init__(self, data_dir, backend):
        scope = hashlib.sha256(str(Path(data_dir).resolve()).encode()).hexdigest()[:24]
        self.service = "ai.delphic.desktop." + scope
        self.account = "ai-connection-v1"
        self.backend = backend
        self.lock = threading.RLock()
        self._loaded = False
        self._config = None
        self.error = ""

    @property
    def available(self):
        return self.backend is not None

    def load(self):
        with self.lock:
            if not self.available:
                return None
            if not self._loaded:
                self._loaded = True
                try:
                    raw = self.backend.get_password(self.service, self.account)
                    if raw is not None:
                        if not isinstance(raw, str) or len(raw) > 12000:
                            raise ValueError("Invalid credential")
                        data = json.loads(raw)
                        fields = ("provider", "api_key", "model", "image_model")
                        if (not isinstance(data, dict) or data.get("version") != 1
                                or any(not isinstance(data.get(f), str) or not data[f] for f in fields)):
                            raise ValueError("Invalid credential")
                        self._config = {f: data[f] for f in fields}
                except Exception:
                    self.error = "Could not read the saved key. Unlock your system credential store and restart Delphic."
            return dict(self._config) if self._config else None

    def save(self, config):
        with self.lock:
            if not self.available:
                raise DeviceCredentialError("Protected key storage is unavailable. Leave Remember key unchecked to connect temporarily.")
            fields = ("provider", "api_key", "model", "image_model")
            value = {f: config[f] for f in fields}
            payload = json.dumps({"version": 1, **value})
            # Windows' credential blob limit is 2560 bytes, encoded as UTF-16.
            if len(payload.encode("utf-16-le")) > 2560:
                raise DeviceCredentialError("This connection is too large for protected storage. Connect without remembering it.")
            try:
                self.backend.set_password(self.service, self.account, payload)
            except Exception:
                self.error = "Could not verify protected storage after saving failed. The current connection remains available for this run; save again or forget the key."
                raise DeviceCredentialError("Could not save the key in protected storage. Your connection was not changed.") from None
            self._config, self._loaded, self.error = value, True, ""

    def clear(self):
        with self.lock:
            saved = self.load()
            if not saved and not self.error:
                return
            if not self.available:
                raise DeviceCredentialError("Protected key storage is unavailable. The saved key was not removed.")
            try:
                # A previous OS operation may have completed before reporting failure.
                if not self.error or self.backend.get_password(self.service, self.account) is not None:
                    self.backend.delete_password(self.service, self.account)
            except Exception:
                self.error = "Could not verify removal from protected storage. The current connection remains available; try forgetting the key again."
                raise DeviceCredentialError("Could not remove the saved key. Unlock your system credential store and try again.") from None
            self._config, self._loaded, self.error = None, True, ""
