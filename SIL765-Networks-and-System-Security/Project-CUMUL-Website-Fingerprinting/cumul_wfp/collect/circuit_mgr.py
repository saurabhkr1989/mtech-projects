"""
File: circuit_mgr.py
Module: collect
Phase: Phase 1 - Data Collection

Purpose:
    Manages Tor circuit rotation using Stem controller.
    Provides NEWNYM signal to get fresh circuits for each capture instance.

Paper reference: N/A - infrastructure for data collection

Windows adaptation notes:
    Uses Stem library to control Tor Browser's embedded Tor process.

Dependencies:
    - stem: Tor control protocol implementation

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-03-17
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from stem import Signal
    from stem.control import Controller
    STEM_AVAILABLE = True
except ImportError:
    STEM_AVAILABLE = False
    print("WARNING: Stem not available. Circuit management disabled.")

import config


class CircuitManager:
    """
    Manages Tor circuit rotation for website fingerprinting.
    
    Each capture instance should use a fresh Tor circuit to ensure
    independence between samples. This class handles circuit rotation
    via the Stem controller.
    """

    def __init__(self, control_port=None, cookie_path=None):
        """
        Initialize the circuit manager.
        
        Args:
            control_port: Tor control port (default from config)
            cookie_path: Path to control authentication cookie (default from config)
        """
        self.control_port = control_port or config.TOR_CONTROL_PORT
        self.cookie_path = cookie_path or config.TOR_COOKIE_PATH
        self.controller = None
        self.is_connected = False

    def connect(self):
        """
        Connect to the Tor control port.
        
        Uses cookie authentication for secure local connection.
        """
        if not STEM_AVAILABLE:
            print("ERROR: Stem library not available")
            return False

        try:
            self.controller = Controller.from_port(port=self.control_port)
            self.controller.authenticate_cookie()
            self.is_connected = True
            print(f"Connected to Tor control port {self.control_port}")
            return True
        except Exception as e:
            print(f"Failed to connect to Tor: {e}")
            print("Make sure Tor Browser is running with ControlPort enabled")
            self.is_connected = False
            return False

    def new_circuit(self):
        """
        Signal Tor to create a new circuit.
        
        Sends NEWNYM signal to request a new circuit. This ensures
        each capture instance uses a fresh path through the Tor network.
        
        Waits CIRCUIT_WAIT_SECONDS after signal to allow circuit establishment.
        """
        if not self.is_connected or self.controller is None:
            print("ERROR: Not connected to Tor controller")
            return False

        try:
            self.controller.signal(Signal.NEWNYM)
            wait_time = getattr(config, 'CIRCUIT_WAIT_SECONDS', 5)
            time.sleep(wait_time)
            return True
        except Exception as e:
            print(f"Failed to signal NEWNYM: {e}")
            return False

    def get_circuit_info(self):
        """
        Get information about current Tor circuit.
        
        Returns:
            Dictionary with circuit details or None
        """
        if not self.is_connected:
            return None

        try:
            circuits = self.controller.get_circuits()
            if circuits:
                return {
                    'id': circuits[0].id,
                    'status': circuits[0].status,
                    'path': len(circuits[0].path)
                }
        except Exception as e:
            print(f"Failed to get circuit info: {e}")

        return None

    def close(self):
        """
        Close the connection to Tor controller.
        """
        if self.controller:
            try:
                self.controller.close()
                self.is_connected = False
            except Exception as e:
                print(f"Error closing controller: {e}")


def create_circuit_manager():
    """
    Factory function to create and connect a circuit manager.
    
    Returns:
        Connected CircuitManager instance or None
    """
    manager = CircuitManager()
    if manager.connect():
        return manager
    return None


if __name__ == "__main__":
    print("Testing CircuitManager...")
    manager = create_circuit_manager()
    if manager:
        print("Testing NEWNYM signal...")
        if manager.new_circuit():
            print("NEWNYM signal sent successfully")
        info = manager.get_circuit_info()
        if info:
            print(f"Circuit info: {info}")
        manager.close()
        print("Circuit manager test complete")
    else:
        print("Failed to create circuit manager")
        print("Make sure Tor Browser is running with ControlPort 9051")
