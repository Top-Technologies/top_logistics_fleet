"""
Provider-independent GPS Integration API Layer (Section 45).
Standard interface for external GPS/telematics platforms (Wialon, Teltonika, Concox, etc.).
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import logging
import requests

_logger = logging.getLogger(__name__)


class GPSProviderBase(ABC):
    """
    Abstract interface for GPS Providers.
    Each GPS vendor implements these standardized methods.
    """

    def __init__(self, api_url, api_key=None, username=None, password=None, timeout=30):
        self.api_url = api_url
        self.api_key = api_key
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session_id = None

    @abstractmethod
    def authenticate(self):
        """Authenticates with the external GPS platform and stores session token."""
        pass

    @abstractmethod
    def get_devices(self):
        """
        Retrieves device inventory.
        Returns: list of dicts with standardized keys:
        [{'device_id': '...', 'imei': '...', 'name': '...', 'status': 'active/offline'}]
        """
        pass

    @abstractmethod
    def get_positions(self, device_ids=None):
        """
        Retrieves latest GPS telemetry positions for units (Section 24).
        Returns: list of dicts:
        [{
            'device_id': 'GPS123',
            'timestamp': '2026-09-14T08:30:00',
            'latitude': 9.0300,
            'longitude': 38.7400,
            'speed': 42.0,
            'direction': 180.0,
            'ignition': True,
            'odometer': 125430.0,
            'battery': 12.6,
            'gps_signal': 95
        }]
        """
        pass

    @abstractmethod
    def get_vehicle_status(self, device_id):
        """Returns current operational status (online, offline, idling, moving)."""
        pass

    @abstractmethod
    def get_odometer(self, device_id):
        """Returns the high-precision cumulative mileage/odometer in km."""
        pass

    @abstractmethod
    def get_events(self, device_id, start_time, end_time):
        """Retrieves events (overspeed, geofence, excessive stop) between timestamps."""
        pass


def calibrate_sensor(raw_val, tbl):
    """
    Applies Wialon piecewise linear calibration table (tbl) to a raw sensor reading.
    Each segment in tbl has {'x': threshold, 'a': slope, 'b': intercept}.
    Formula: y = a * x + b
    """
    if raw_val is None:
        return 0.0
    try:
        raw_val = float(raw_val)
    except (ValueError, TypeError):
        return 0.0

    if raw_val <= 0.0:
        return 0.0

    if not tbl:
        # If no calibration table is defined:
        # Values > 1000 without calibration are usually raw mV ADC values, not litres
        if raw_val > 1000.0:
            return 0.0
        return max(0.0, round(raw_val, 2))

    # tbl is expected to be sorted by 'x'
    if raw_val < tbl[0].get('x', 0):
        return 0.0

    chosen_seg = tbl[0]
    for seg in tbl:
        if raw_val >= seg.get('x', 0):
            chosen_seg = seg
        else:
            break

    a = chosen_seg.get('a', 1.0)
    b = chosen_seg.get('b', 0.0)
    calibrated = a * raw_val + b
    return max(0.0, round(calibrated, 2))



class WialonGPSClient(GPSProviderBase):
    """Concrete implementation for Wialon platform."""

    WIALON_ERRORS = {
        1: "Invalid session or session expired",
        2: "Invalid service name",
        3: "Invalid result",
        4: "Invalid input / token parameters",
        5: "Error performing request on Wialon remote server",
        6: "Unknown Wialon internal error",
        7: "Access denied / Invalid authorization token",
        8: "Invalid user name or password",
        9: "Authorization server is unavailable",
    }

    def __init__(self, api_url, api_key=None, username=None, password=None, timeout=30):
        # Default Wialon endpoint if empty or base domain given
        url = (api_url or "").strip()
        if not url:
            url = "https://hst-api.wialon.com/wialon/ajax.html"
        elif not url.endswith("/wialon/ajax.html") and not url.endswith(".html"):
            url = url.rstrip("/") + "/wialon/ajax.html"
        super().__init__(url, api_key=api_key, username=username, password=password, timeout=timeout)

    def authenticate(self):
        """Authenticates with the Wialon platform using the API token and stores session EID."""
        if not self.api_key:
            raise ValueError("Wialon API token is missing. Please provide a valid API token in the provider configuration.")

        _logger.info("Wialon authenticate: Initiating handshake with %s", self.api_url)
        params = {"token": self.api_key.strip()}
        try:
            resp = requests.get(
                self.api_url,
                params={"svc": "token/login", "params": json.dumps(params)},
                timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            _logger.exception("Wialon authentication network failure: %s", e)
            raise ConnectionError(f"Failed to connect to Wialon gateway at {self.api_url}: {e}")

        if not isinstance(data, dict):
            raise ValueError(f"Unexpected response format from Wialon: {data}")

        if "error" in data:
            code = data.get("error")
            err_desc = self.WIALON_ERRORS.get(code, f"Wialon API Error Code {code}")
            _logger.error("Wialon login rejected: %s (code %s)", err_desc, code)
            raise PermissionError(f"Wialon Authentication failed: {err_desc}")

        self.session_id = data.get("eid")
        user_name = data.get("user", {}).get("nm", "Unknown")
        _logger.info("Wialon authenticated successfully. User: %s, Session EID: %s", user_name, self.session_id[:8] + "...")
        return True

    def _ensure_session(self):
        if not self.session_id:
            self.authenticate()

    def get_devices(self):
        """
        Retrieves all AVL units from Wialon with full telemetry and sensor calibration.
        Returns: list of dicts with standardized keys.
        """
        self._ensure_session()
        search_params = {
            "spec": {
                "itemsType": "avl_unit",
                "propName": "sys_name",
                "propValueMask": "*",
                "sortType": "sys_name"
            },
            "force": 1,
            "flags": 0xFFFFFFFF,
            "from": 0,
            "to": 0
        }

        try:
            resp = requests.get(
                self.api_url,
                params={
                    "svc": "core/search_items",
                    "params": json.dumps(search_params),
                    "sid": self.session_id
                },
                timeout=self.timeout
            )
            data = resp.json()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Wialon search_items request failed: {e}")

        # Check for session expiration and retry once
        if isinstance(data, dict) and data.get("error") == 1:
            _logger.info("Wialon session expired. Re-authenticating...")
            self.authenticate()
            resp = requests.get(
                self.api_url,
                params={
                    "svc": "core/search_items",
                    "params": json.dumps(search_params),
                    "sid": self.session_id
                },
                timeout=self.timeout
            )
            data = resp.json()

        if isinstance(data, dict) and "error" in data:
            code = data.get("error")
            err_desc = self.WIALON_ERRORS.get(code, f"Error Code {code}")
            raise RuntimeError(f"Wialon units search failed: {err_desc}")

        items = data.get("items", []) if isinstance(data, dict) else []
        _logger.info("Retrieved %d AVL units from Wialon.", len(items))

        devices = []
        for item in items:
            unit_id = str(item.get("id"))
            unit_name = (item.get("nm") or f"Unit #{unit_id}").strip()
            pos = item.get("pos") or {}
            lmsg = item.get("lmsg") or {}
            prms = lmsg.get("p", {}) if isinstance(lmsg, dict) else {}
            sens = item.get("sens", {}) if isinstance(item.get("sens"), dict) else {}

            # Coordinates & Motion
            lat = float(pos.get("y", 0.0) or 0.0)
            lng = float(pos.get("x", 0.0) or 0.0)
            speed = float(pos.get("s", 0.0) or 0.0)
            altitude = float(pos.get("z", 0.0) or 0.0)
            direction = float(pos.get("c", 0.0) or 0.0)
            satellites = int(pos.get("sc", 0) or 0)
            epoch_t = pos.get("t")

            dt_comm = None
            if epoch_t:
                try:
                    dt_comm = datetime.fromtimestamp(epoch_t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    dt_comm = None

            # Odometer / Mileage
            odometer = float(item.get("cnm", 0.0) or 0.0)
            if odometer == 0.0 and "io_16" in prms:
                try:
                    odometer = round(float(prms["io_16"]) / 1000.0, 2)
                except Exception:
                    pass

            # Ignition Detection
            ignition = False
            for s in sens.values():
                stype = s.get("t", "")
                sname = s.get("n", "").lower()
                if stype == "engine operation" or "ignition" in sname:
                    param_name = s.get("p")
                    raw_ign = prms.get(param_name)
                    if s.get("tbl"):
                        ignition = bool(calibrate_sensor(raw_ign, s.get("tbl")))
                    elif raw_ign is not None:
                        ignition = bool(raw_ign)
                    break
            if not ignition and "io_239" in prms:
                try:
                    ignition = bool(int(prms["io_239"]))
                except Exception:
                    pass

            # Fuel Level Calibration
            fuel_level = 0.0
            fuel_found = False
            for s in sens.values():
                stype = s.get("t", "")
                sname = s.get("n", "").lower()
                if stype in ("fuel level", "instant fuel consumption") or "fuel" in sname:
                    param_name = s.get("p")
                    raw_fuel = prms.get(param_name)
                    if raw_fuel is None and "io_270" in prms:
                        raw_fuel = prms["io_270"]
                    if raw_fuel is not None:
                        fuel_level = calibrate_sensor(raw_fuel, s.get("tbl", []))
                        fuel_found = True
                        break

            # Battery Voltage (External vehicle power preferred, fallback to internal tracker)
            battery = 0.0
            if "pwr_ext" in prms and prms["pwr_ext"] is not None:
                battery = round(float(prms["pwr_ext"]), 2)
            elif "io_66" in prms and prms["io_66"] is not None:
                battery = round(float(prms["io_66"]) / 1000.0, 2)
            elif "pwr_int" in prms and prms["pwr_int"] is not None:
                battery = round(float(prms["pwr_int"]), 2)

            # Device operational status
            status = 'active'
            if not lat and not lng:
                status = 'offline'

            # Hardware IMEI / UID
            uid_val = item.get("uid")
            imei = str(uid_val) if uid_val else f"WL-{unit_id}"
            sim_number = str(item.get("ph") or "")

            devices.append({
                'device_id': unit_id,
                'name': unit_name,
                'imei': imei,
                'sim_number': sim_number,
                'latitude': lat,
                'longitude': lng,
                'altitude': altitude,
                'speed': speed,
                'direction': direction,
                'gps_signal': satellites,
                'ignition': ignition,
                'odometer': odometer,
                'fuel_level': fuel_level,
                'battery': battery,
                'last_communication': dt_comm,
                'status': status,
            })

        return devices

    def get_positions(self, device_ids=None):
        """Retrieves latest telemetry positions for units."""
        devices = self.get_devices()
        if device_ids:
            device_id_set = {str(d) for d in device_ids}
            devices = [d for d in devices if d['device_id'] in device_id_set]

        positions = []
        for d in devices:
            positions.append({
                'device_id': d['device_id'],
                'timestamp': d['last_communication'] or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                'latitude': d['latitude'],
                'longitude': d['longitude'],
                'altitude': d['altitude'],
                'speed': d['speed'],
                'direction': d['direction'],
                'ignition': d['ignition'],
                'odometer': d['odometer'],
                'fuel_level': d['fuel_level'],
                'battery': d['battery'],
                'gps_signal': d['gps_signal'],
            })
        return positions

    def get_vehicle_status(self, device_id):
        positions = self.get_positions(device_ids=[device_id])
        if not positions:
            return 'offline'
        pos = positions[0]
        if pos.get('speed', 0.0) > 5.0:
            return 'moving'
        if pos.get('ignition'):
            return 'idling'
        return 'stopped'

    def get_odometer(self, device_id):
        positions = self.get_positions(device_ids=[device_id])
        return positions[0].get('odometer', 0.0) if positions else 0.0

    def get_events(self, device_id, start_time, end_time):
        return []


class GenericGPSClient(GPSProviderBase):
    """Concrete implementation for Generic REST GPS API."""

    def authenticate(self):
        return True

    def get_devices(self):
        return []

    def get_positions(self, device_ids=None):
        return []

    def get_vehicle_status(self, device_id):
        return 'online'

    def get_odometer(self, device_id):
        return 0.0

    def get_events(self, device_id, start_time, end_time):
        return []


def get_gps_client(provider):
    """Factory helper to obtain an initialized GPSProviderBase client for a provider record."""
    auth_type = getattr(provider, 'auth_type', 'token')
    api_url = getattr(provider, 'api_url', '')
    api_key = getattr(provider, 'api_key', '')
    username = getattr(provider, 'username', '')
    password = getattr(provider, 'password', '')
    timeout = getattr(provider, 'timeout', 30) or 30

    return WialonGPSClient(
        api_url=api_url,
        api_key=api_key,
        username=username,
        password=password,
        timeout=timeout,
    )
