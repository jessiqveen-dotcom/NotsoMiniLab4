"""
# main.py
# Main application entry point for Lab 4 IoT CRM Machine (Interaction Modeling & Sequence Diagrams)
# Author: jessiqveen-dotcom
"""

import time
from Log import *
from CRMController import CRMController

# =============================================================================
# LAB 4 CONFIGURATION (Raspberry Pi Pico 2W + PicoLibrary)
# =============================================================================
# Update WIFI_SSID and WIFI_PASSWORD if using a mobile hotspot!
WIFI_SSID = "jessica08"
WIFI_PASSWORD = "7865875928"  # Phone hotspot password (use None for open FIU_WiFi, or "" for Wokwi-GUEST)
COURSE_SERVER = "ism6106"     # "ism6106" or "ism6205"
PRELOAD_ALL_AT_START = False  # False = Sequence Option B (Lazy On-Demand); True = Sequence Option A (Eager)
STUDENT_CUSTOMER_NAME = "Jessica Camacho"

# Hardware Pinout (PicoLibrary Standard Breadboard):
# - LCDDisplay (I2C0) : SDA = GP0, SCL = GP1
# - LightStrip        : DIN = GP2 (8 NeoPixel LEDs)
# - PassiveBuzzer     : PWM = GP16
# - Button 'previous' : GP18
# - Button 'next'     : GP19
# - Button 'select'   : GP20 (Cycles: Client -> Contacts -> Activities -> Client)
# - Button 'back'     : GP21 (Optional shortcut back to Client list)
# =============================================================================


def run_sequence_demo():
    """
    Runs a live REST API verification against the Oracle ORDS webservice
    (`ism6106`) when executed on desktop Python or in an environment without
    Pico GPIO pins, printing the exact sequence of messages matching the
    Sequence B (On-Demand) and Sequence A (Preload) UML Sequence Diagrams.
    """
    Log.i("================================================================")
    Log.i("   LAB 4: IoT CRM SYSTEM - LIVE REST API SEQUENCE SCENARIO      ")
    Log.i("================================================================")

    class _ConsoleLCD:
        def clear(self, line=-1):
            pass

        def showText(self, text, row=0, col=0):
            pass

    class _ConsoleLightStrip:
        def __init__(self):
            self._numleds = 8

        def setColor(self, color, numPixels=None):
            n = self._numleds if numPixels is None else numPixels
            Log.i(f"LightStrip.setColor({color}, numPixels={n})")

        def off(self):
            Log.i("LightStrip.off()")

    class _ConsoleBuzzer:
        def beep(self, tone=500, duration=60):
            Log.i(f"PassiveBuzzer.beep(tone={tone}Hz, duration={duration}ms)")

        def stop(self):
            Log.i("PassiveBuzzer.stop()")

    class _DesktopNet:
        def isConnected(self):
            return True

        def connect(self, ssid, password=None):
            Log.i(f"Net.connect(ssid='{ssid}')")

        def getLocalIp(self):
            return "10.109.42.18"

        def getJson(self, url):
            import urllib.request
            import json

            Log.i(f"Net.getJson('{url}')")
            req = urllib.request.Request(url, headers={"User-Agent": "PicoCRM/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))

    crm = CRMController(
        ssid=WIFI_SSID,
        password=WIFI_PASSWORD,
        course=COURSE_SERVER,
        preload=PRELOAD_ALL_AT_START,
        prioritize_name=STUDENT_CUSTOMER_NAME,
        net=_DesktopNet(),
        display=_ConsoleLCD(),
        lightstrip=_ConsoleLightStrip(),
        buzzer=_ConsoleBuzzer(),
        buttons=[],
    )

    # Step 1: Startup -> loads only Clients list (Sequence B)
    crm.start()

    # Step 2: User presses 'select' on Client 1 (Jessica Camacho) -> triggers lazy load of Contacts & Activities
    Log.i("--- User Action: Press 'select' button to view Contacts for active Client ---")
    crm.buttonPressed("select")

    # Step 3: User presses 'select' again -> switches to Activities view (already cached on Client)
    Log.i("--- User Action: Press 'select' button to view Activities for active Client ---")
    crm.buttonPressed("select")

    # Step 4: User presses 'select' again -> returns to Clients list
    Log.i("--- User Action: Press 'select' button to return to Clients directory ---")
    crm.buttonPressed("select")

    # Step 5: User presses 'next' -> browses to next Client (Illumina Biotech) and selects it
    Log.i("--- User Action: Press 'next' button to browse to next Client ---")
    crm.buttonPressed("next")
    Log.i("--- User Action: Press 'select' button on second Client ---")
    crm.buttonPressed("select")
    Log.i("--- User Action: Press 'select' button to view second Client's Activities ---")
    crm.buttonPressed("select")

    crm.stop()


def main():
    """Entry point for Raspberry Pi Pico 2W hardware or desktop console verification."""
    time.sleep(0.1)
    try:
        # Attempt to initialize with real Raspberry Pi Pico 2W hardware
        crm = CRMController(
            ssid=WIFI_SSID,
            password=WIFI_PASSWORD,
            course=COURSE_SERVER,
            preload=PRELOAD_ALL_AT_START,
            prioritize_name=STUDENT_CUSTOMER_NAME,
        )
        crm.start()
        crm.run()
    except ImportError:
        # Running on desktop Python (Thonny local interpreter / VS Code / Antigravity IDE)
        run_sequence_demo()


if __name__ == "__main__":
    main()
