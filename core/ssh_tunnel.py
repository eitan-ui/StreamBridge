"""SSH reverse tunnel manager for StreamBridge.

Opens an SSH reverse tunnel to a VPS so the PWA is accessible from the internet.
Equivalent to: ssh -R remote_port:localhost:local_port user@host -p port -i key -N
"""

import asyncio
import logging
import os
import sys
from typing import Callable, Optional

import asyncssh

from models.config import TunnelConfig, APP_DATA_DIR

logger = logging.getLogger(__name__)


class SSHTunnel:
    """Manages an SSH reverse tunnel with auto-reconnect."""

    def __init__(self, config: TunnelConfig, local_port: int) -> None:
        self._config = config
        self._local_port = local_port
        self._conn: Optional[asyncssh.SSHClientConnection] = None
        self._listener = None
        self._status: str = "disconnected"
        self._error_message: str = ""
        self._reconnect_task: Optional[asyncio.Task] = None
        self._stopped = False

        # Callback: on_status_changed(status: str, error: str, public_url: str)
        self.on_status_changed: Optional[Callable] = None

    @property
    def status(self) -> str:
        return self._status

    @property
    def error_message(self) -> str:
        return self._error_message

    @property
    def public_url(self) -> str:
        if self._status == "connected" and self._config.host:
            return f"http://{self._config.host}:{self._config.remote_port}/app"
        return ""

    def update_config(self, config: TunnelConfig) -> None:
        self._config = config

    def _set_status(self, status: str, error: str = "") -> None:
        self._status = status
        self._error_message = error
        if self.on_status_changed:
            self.on_status_changed(status, error, self.public_url)

    async def start(self) -> None:
        """Connect and create the reverse tunnel."""
        self._stopped = False
        if not self._config.host or not self._config.username:
            self._set_status("error", "Host and username are required")
            return

        self._set_status("connecting")
        delay = 2.0

        while not self._stopped:
            try:
                await self._connect()
                self._set_status("connected")
                logger.info(
                    "SSH tunnel open: %s:%d -> localhost:%d",
                    self._config.host, self._config.remote_port, self._local_port,
                )
                # Wait until connection closes
                await self._conn.wait_closed()
                if self._stopped:
                    break
                logger.warning("SSH tunnel connection lost, reconnecting...")
                self._set_status("connecting", "Connection lost, reconnecting...")
                delay = 2.0
            except asyncio.CancelledError:
                break
            except Exception as e:
                err_msg = str(e)
                logger.error("SSH tunnel error: %s", err_msg)
                self._set_status("error", err_msg)
                if self._stopped:
                    break
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60.0)
                self._set_status("connecting", f"Retrying... ({err_msg})")

        self._set_status("disconnected")

    def _get_known_hosts_path(self) -> str:
        """Resolve the known_hosts file path."""
        if self._config.known_hosts_path:
            return os.path.expanduser(self._config.known_hosts_path)
        # Default: StreamBridge's own known_hosts file
        ssh_dir = os.path.join(APP_DATA_DIR, "ssh")
        os.makedirs(ssh_dir, exist_ok=True)
        return os.path.join(ssh_dir, "known_hosts")

    async def _connect(self) -> None:
        """Establish SSH connection and set up reverse port forwarding."""
        known_hosts_path = self._get_known_hosts_path()

        if self._config.accept_new_keys:
            # TOFU: accept unknown keys and save them
            known_hosts = asyncssh.read_known_hosts(known_hosts_path) if os.path.exists(known_hosts_path) else None
        else:
            # Strict: require the host key to already be in known_hosts
            if not os.path.exists(known_hosts_path):
                raise ConnectionError(
                    f"Known hosts file not found: {known_hosts_path}. "
                    f"Enable 'Accept new keys' or add the host key manually."
                )
            known_hosts = known_hosts_path

        kwargs = {
            "host": self._config.host,
            "port": self._config.port,
            "username": self._config.username,
            "keepalive_interval": 30,
            "keepalive_count_max": 3,
            "known_hosts": known_hosts,
        }

        key_path = self._config.key_path
        if key_path and os.path.exists(key_path):
            kwargs["client_keys"] = [key_path]
        else:
            # Try default StreamBridge key
            default_key = os.path.join(APP_DATA_DIR, "ssh", "streambridge_key")
            if os.path.exists(default_key):
                kwargs["client_keys"] = [default_key]

        self._conn = await asyncssh.connect(**kwargs)

        # TOFU: save the host key if accept_new_keys is enabled
        if self._config.accept_new_keys and self._conn:
            try:
                host_key = self._conn.get_server_host_key()
                if host_key:
                    key_line = f"{self._config.host} {host_key.export_public_key('openssh').decode().strip()}\n"
                    # Only append if not already present
                    existing = ""
                    if os.path.exists(known_hosts_path):
                        with open(known_hosts_path, "r") as f:
                            existing = f.read()
                    if self._config.host not in existing:
                        os.makedirs(os.path.dirname(known_hosts_path), exist_ok=True)
                        with open(known_hosts_path, "a") as f:
                            f.write(key_line)
                        logger.info("Saved host key for %s (TOFU)", self._config.host)
            except (OSError, asyncssh.Error) as e:
                logger.warning("Could not save host key: %s", e)
        self._listener = await self._conn.forward_remote_port(
            "", self._config.remote_port,
            "localhost", self._local_port,
        )

    async def stop(self) -> None:
        """Close the tunnel and stop reconnecting."""
        self._stopped = True
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        if self._listener:
            self._listener.close()
            self._listener = None
        if self._conn:
            self._conn.close()
            try:
                await asyncio.wait_for(self._conn.wait_closed(), timeout=3.0)
            except (asyncio.TimeoutError, Exception):
                pass
            self._conn = None
        self._set_status("disconnected")

    @staticmethod
    def generate_key_pair() -> tuple[str, str]:
        """Generate an ed25519 SSH key pair in the StreamBridge config directory.

        Returns (private_key_path, public_key_text).
        """
        ssh_dir = os.path.join(APP_DATA_DIR, "ssh")
        os.makedirs(ssh_dir, exist_ok=True)
        private_path = os.path.join(ssh_dir, "streambridge_key")
        public_path = private_path + ".pub"

        key = asyncssh.generate_private_key("ssh-ed25519")
        key.write_private_key(private_path)
        key.write_public_key(public_path)

        # Make private key readable only by owner
        try:
            if sys.platform == "win32":
                import stat
                os.chmod(private_path, stat.S_IREAD | stat.S_IWRITE)
            else:
                os.chmod(private_path, 0o600)
        except OSError:
            pass

        public_text = key.export_public_key("openssh").decode("utf-8").strip()
        return private_path, public_text
