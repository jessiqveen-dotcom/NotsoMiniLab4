"""
# CRMController.py
# MVC Controller coordinating CRMService, Client, Contact, Activity, LCDDisplay, Buttons, LightStrip, and PassiveBuzzer
# Author: jessiqveen-dotcom
"""

import time
from Log import *
from Client import Client
from Contact import Contact
from Activity import Activity
from CRMService import CRMService


class CRMController:
    """
    **CRMController** is the main Model-View-Controller (MVC) orchestrator for the
    futuristic Conference Office IoT CRM Machine. It connects to Wi-Fi via **Net**,
    communicates with the Oracle ORDS REST webservices via **CRMService**, and coordinates
    user interaction across an **LCDDisplay** (16x2 I2C), a **LightStrip** (8-LED NeoPixel),
    a **PassiveBuzzer**, and 3 or 4 **Button** inputs (`Previous`, `Next`, `Select`, and optional `Back`).

    Supports both Lab 4 sequence designs:
    - **Option B (`preload=False`, default)**: Loads only the client directory at startup
      (`loadClientsOnly()`), then fetches contacts and activities on-demand (`loadClientDetails()`)
      when the user selects a client.
    - **Option A (`preload=True`)**: Eagerly fetches all clients, contacts, and activities
      at startup (`loadAllData()`) before entering the browsing loop.

    ### Ingenuity Features (LightStrip & PassiveBuzzer):
    - **Connecting / Fetching REST API**: **BLUE** LightStrip chase/fill + ascending chime.
    - **Client Browsing (Unloaded)**: **CYAN** LightStrip with LED index indicator.
    - **Active Client (Has Contacts & Activities)**: **GREEN** LightStrip scaled proportionally
      to the client's engagement score (`2 * activities + contacts`), plus a 3-tone success fanfare.
    - **Partial Client (Contacts or Activities only)**: **YELLOW** LightStrip + double-tone alert.
    - **Inactive Client (0 Activities)**: **RED** LightStrip warning (as suggested in lab instructions)
      + low warning buzz (220 Hz) alerting the conference host that no activities exist yet.

    Parameters:
    ----------
    ssid : str, optional
        Wi-Fi SSID to connect to (default: `"FIU_WiFi"`)
    password : str, optional
        Wi-Fi password; `None` for open networks (default: `None`)
    course : str, optional
        Oracle ORDS course schema, `"ism6106"` or `"ism6205"` (default: `"ism6106"`)
    preload : bool, optional
        `False` for Sequence Option B (Lazy On-Demand); `True` for Sequence Option A (Eager Preload)
        (default: `False`)
    prioritize_name : str, optional
        Customer name to place at index 0 for immediate display (default: `"Jessica Camacho"`)
    net : Net, optional
        Pre-configured `Net` instance (default: `None`)
    service : CRMService, optional
        Pre-configured `CRMService` instance (default: `None`)
    display : LCDDisplay, optional
        Pre-configured `LCDDisplay` instance (default: `None`)
    lightstrip : LightStrip, optional
        Pre-configured `LightStrip` instance (default: `None`)
    buzzer : PassiveBuzzer, optional
        Pre-configured `PassiveBuzzer` instance (default: `None`)
    buttons : list of Button, optional
        List of 3 or 4 `Button` instances `[Prev, Next, Select, (Back)]` (default: `None`)

    Examples:
    ---------
    1. Run the IoT CRM Controller using Sequence Option B (Lazy Loading):
       `crm = CRMController(ssid="MyHotspot", password="secret", course="ism6106", preload=False)`
       `crm.start()`
       `crm.run()`
    2. Programmatically step through the sequence for console verification:
       `crm.selectCurrent()`
       `crm.nextItem()`
    """

    # Browsing Modes
    MODE_CLIENTS = "CLIENTS"
    MODE_CONTACTS = "CONTACTS"
    MODE_ACTIVITIES = "ACTIVITIES"

    # Audio Tones (Hz)
    TONE_NAV = 523       # C5 - Next/Previous scroll
    TONE_SELECT = 659    # E5 - Select/Drill down
    TONE_BACK = 392      # G4 - Return to client list
    TONE_SUCCESS = 784   # G5 - Active client fanfare top note
    TONE_WARN_RED = 220  # A3 - Warning tone when client has 0 activities

    # RGB Colors (fallback if Lights module not imported)
    COLOR_RED = (255, 0, 0)
    COLOR_GREEN = (0, 255, 0)
    COLOR_YELLOW = (255, 200, 0)
    COLOR_BLUE = (0, 0, 255)
    COLOR_CYAN = (0, 200, 255)
    COLOR_PURPLE = (180, 0, 255)

    def __init__(
        self,
        ssid: str = "FIU_WiFi",
        password: str = None,
        course: str = "ism6106",
        preload: bool = False,
        prioritize_name: str = "Jessica Camacho",
        net=None,
        service: CRMService = None,
        display=None,
        lightstrip=None,
        buzzer=None,
        buttons: list = None,
    ):
        Log.i(f"CRMController: initializing (course={course}, preload={preload})")
        self.ssid = ssid
        self.password = password
        self.course = course
        self.preload = bool(preload)
        self.prioritize_name = prioritize_name

        # Domain state
        self.clients = []
        self.mode = self.MODE_CLIENTS
        self._clientIndex = 0
        self._contactIndex = 0
        self._activityIndex = 0
        self._running = False
        self._pendingEvents = []

        # 1. Network & CRMService
        self.net = net
        self.service = service

        # 2. LCD Display (I2C0 on GP0=SDA, GP1=SCL)
        if display is not None:
            self.display = display
        else:
            from Displays import LCDDisplay
            self.display = LCDDisplay(sda=0, scl=1)

        # 3. LightStrip (GP2, 8 NeoPixels)
        if lightstrip is not None:
            self.lightstrip = lightstrip
        else:
            from LightStrip import LightStrip
            self.lightstrip = LightStrip(pin=2, name="CRMStrip", numleds=8, brightness=0.5)

        # 4. PassiveBuzzer (GP16)
        if buzzer is not None:
            self.buzzer = buzzer
        else:
            try:
                from Buzzer import PassiveBuzzer
                self.buzzer = PassiveBuzzer(pin=16, name="CRMBuzzer")
            except ImportError:
                from Buzzer import ActiveBuzzer
                self.buzzer = ActiveBuzzer(pin=16, name="CRMBuzzer")

        # 5. Navigation Buttons (GP18=Previous, GP19=Next, GP20=Select, GP21=Back)
        if buttons is not None:
            self.buttons = list(buttons)
            for btn in self.buttons:
                if hasattr(btn, "setHandler"):
                    btn.setHandler(self)
        else:
            from Button import Button
            self.buttons = [
                Button(18, "previous", handler=self),
                Button(19, "next", handler=self),
                Button(20, "select", handler=self),
                Button(21, "back", handler=self),
            ]

    def connectNetwork(self) -> bool:
        """
        Connects to Wi-Fi using PicoLibrary's **Net** class and initializes **CRMService**
        while showing progress on the **LCDDisplay** and **LightStrip**.
        Gracefully handles Wokwi Simulator mode if virtual Wi-Fi cannot connect.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. Connect to Wi-Fi and verify status:
           `connected = crm.connectNetwork()`
        2. Check CRMService readiness:
           `assert crm.service is not None`
        """
        self._showStatus("IoT CRM Machine", f"WiFi:{self.ssid[:11]}", self.COLOR_BLUE)

        if self.net is None:
            try:
                from Net import Net
                self.net = Net()
            except Exception as e:
                Log.w(f"CRMController: Net module unavailable ({e}); continuing in simulator mode")

        ip_addr = "Sim-Mode"
        if self.net is not None:
            try:
                if not self.net.isConnected():
                    Log.i(f"CRMController: connecting to Wi-Fi SSID '{self.ssid}'...")
                    self.net.connect(self.ssid, self.password)
                if hasattr(self.net, "getLocalIp"):
                    ip_addr = self.net.getLocalIp()
            except Exception as e:
                Log.w(f"CRMController: Wi-Fi connection skipped/fallback ({e})")
                ip_addr = "10.10.0.2 (Sim)"

        Log.i(f"CRMController: Network ready (IP: {ip_addr})")
        self._showStatus("WiFi Connected!", f"IP:{str(ip_addr)[:13]}", self.COLOR_CYAN)

        if self.service is None:
            self.service = CRMService(net=self.net, course=self.course)

        version = self.service.getVersion()
        Log.i(f"CRMController: Oracle ORDS CRM API Version {version}")
        return True

    def start(self) -> None:
        """
        Initializes network connectivity and executes the configured startup sequence:
        - **Option A (`self.preload == True`)**: Calls `self.service.loadAllData()` to fetch
          all clients, contacts, and activities upfront.
        - **Option B (`self.preload == False`)**: Calls `self.service.loadClientsOnly()` to fetch
          only the list of clients at startup.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. Start the CRM controller:
           `crm.start()`
        2. Verify clients were loaded:
           `assert len(crm.clients) > 0`
        """
        Log.i("CRMController: start() invoked")
        self.connectNetwork()

        if self.preload:
            self._showStatus("Loading All CRM", "Clients+Details", self.COLOR_BLUE)
            self.clients = self.service.loadAllData(prioritize_name=self.prioritize_name)
        else:
            self._showStatus("Loading Clients", "Please wait...", self.COLOR_BLUE)
            self.clients = self.service.loadClientsOnly(prioritize_name=self.prioritize_name)

        self.mode = self.MODE_CLIENTS
        self._clientIndex = 0
        self._contactIndex = 0
        self._activityIndex = 0

        if self.buzzer:
            self.buzzer.beep(self.TONE_SELECT, 80)

        self.updateView()

    def currentClient(self) -> Client:
        """
        Returns the currently active **Client** object, or `None` if no clients are loaded.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. Get the currently displayed client:
           `client = crm.currentClient()`
        2. Print active client name:
           `Log.i(crm.currentClient().customer_name)`
        """
        if not self.clients:
            return None
        return self.clients[self._clientIndex]

    def currentContact(self) -> Contact:
        """
        Returns the currently selected **Contact** of the active client, or `None` if the client
        has no contacts.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. Get the currently displayed contact:
           `contact = crm.currentContact()`
        2. Check contact phone:
           `if contact: Log.i(contact.phone)`
        """
        client = self.currentClient()
        if not client or not client.contacts:
            return None
        return client.contacts[self._contactIndex % len(client.contacts)]

    def currentActivity(self) -> Activity:
        """
        Returns the currently selected **Activity** of the active client, or `None` if the client
        has no activities.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. Get the currently displayed activity:
           `activity = crm.currentActivity()`
        2. Check activity type:
           `if activity: Log.i(activity.activity_type)`
        """
        client = self.currentClient()
        if not client or not client.activities:
            return None
        return client.activities[self._activityIndex % len(client.activities)]

    def nextItem(self) -> None:
        """
        Advances to the next item in the active browsing mode:
        - In `MODE_CLIENTS`: moves to the next **Client**.
        - In `MODE_CONTACTS`: moves to the next **Contact** of the selected client.
        - In `MODE_ACTIVITIES`: moves to the next **Activity** of the selected client.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. Scroll forward in the current list:
           `crm.nextItem()`
        2. Scroll to next client:
           `crm.mode = CRMController.MODE_CLIENTS; crm.nextItem()`
        """
        if not self.clients:
            return

        if self.mode == self.MODE_CLIENTS:
            self._clientIndex = (self._clientIndex + 1) % len(self.clients)
            client = self.currentClient()
            Log.i(
                f"CRMController: nextItem [CLIENTS] -> {client.customer_name} "
                f"({self._clientIndex + 1}/{len(self.clients)})"
            )
        elif self.mode == self.MODE_CONTACTS:
            client = self.currentClient()
            if client and client.contacts:
                self._contactIndex = (self._contactIndex + 1) % len(client.contacts)
                contact = self.currentContact()
                Log.i(
                    f"CRMController: nextItem [CONTACTS] -> {contact.name} "
                    f"({self._contactIndex + 1}/{len(client.contacts)})"
                )
            else:
                Log.i("CRMController: nextItem [CONTACTS] -> No contacts to scroll")
        elif self.mode == self.MODE_ACTIVITIES:
            client = self.currentClient()
            if client and client.activities:
                self._activityIndex = (self._activityIndex + 1) % len(client.activities)
                act = self.currentActivity()
                Log.i(
                    f"CRMController: nextItem [ACTIVITIES] -> {act.name} "
                    f"({self._activityIndex + 1}/{len(client.activities)})"
                )
            else:
                Log.i("CRMController: nextItem [ACTIVITIES] -> No activities to scroll")

        if self.buzzer:
            self.buzzer.beep(self.TONE_NAV, 50)
        self.updateView()

    def previousItem(self) -> None:
        """
        Moves to the previous item in the active browsing mode (`CLIENTS`, `CONTACTS`, or `ACTIVITIES`).

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. Scroll backward in the current list:
           `crm.previousItem()`
        2. Verify index wraps around cleanly:
           `crm.previousItem()`
        """
        if not self.clients:
            return

        if self.mode == self.MODE_CLIENTS:
            self._clientIndex = (self._clientIndex - 1) % len(self.clients)
            client = self.currentClient()
            Log.i(
                f"CRMController: previousItem [CLIENTS] -> {client.customer_name} "
                f"({self._clientIndex + 1}/{len(self.clients)})"
            )
        elif self.mode == self.MODE_CONTACTS:
            client = self.currentClient()
            if client and client.contacts:
                self._contactIndex = (self._contactIndex - 1) % len(client.contacts)
                contact = self.currentContact()
                Log.i(
                    f"CRMController: previousItem [CONTACTS] -> {contact.name} "
                    f"({self._contactIndex + 1}/{len(client.contacts)})"
                )
        elif self.mode == self.MODE_ACTIVITIES:
            client = self.currentClient()
            if client and client.activities:
                self._activityIndex = (self._activityIndex - 1) % len(client.activities)
                act = self.currentActivity()
                Log.i(
                    f"CRMController: previousItem [ACTIVITIES] -> {act.name} "
                    f"({self._activityIndex + 1}/{len(client.activities)})"
                )

        if self.buzzer:
            self.buzzer.beep(self.TONE_NAV, 50)
        self.updateView()

    def selectCurrent(self) -> None:
        """
        Handles the **Select / Action** button press to cycle through the client's details:
        1. If in `MODE_CLIENTS`:
           - When running **Sequence Option B (`preload=False`)** and `!client.details_loaded`,
             invokes `self.service.loadClientDetails(client)` to fetch contacts and activities
             on-demand from the REST API.
           - Plays an audio cue matching the client's engagement status (3-tone fanfare if active,
             low warning tone if 0 activities) and transitions to `MODE_CONTACTS`.
        2. If in `MODE_CONTACTS`: transitions to `MODE_ACTIVITIES` to browse the client's activities.
        3. If in `MODE_ACTIVITIES`: returns to `MODE_CLIENTS` so the user can work smoothly even
           with a 3-button layout (`Prev`, `Next`, `Select`).

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. Select the current client and view their contacts:
           `crm.selectCurrent()`
        2. Press Select again to view the client's activities:
           `crm.selectCurrent()`
        3. Press Select a third time to return to the client directory:
           `crm.selectCurrent()`
        """
        client = self.currentClient()
        if not client:
            return

        if self.mode == self.MODE_CLIENTS:
            Log.i(f"CRMController: selectCurrent() -> Selected client '{client.customer_name}' (ID: {client.id})")
            if not client.details_loaded:
                self._showStatus(client.customer_name[:16], "Fetching CRM...", self.COLOR_BLUE)
                self.service.loadClientDetails(client)

            self._contactIndex = 0
            self._activityIndex = 0
            self.mode = self.MODE_CONTACTS
            Log.i(
                f"CRMController: Switched to MODE_CONTACTS for '{client.customer_name}' "
                f"(Contacts: {len(client.contacts)}, Activities: {len(client.activities)})"
            )
            self._playClientEngagementFeedback(client)
            self.updateView()

        elif self.mode == self.MODE_CONTACTS:
            self._activityIndex = 0
            self.mode = self.MODE_ACTIVITIES
            Log.i(
                f"CRMController: Switched to MODE_ACTIVITIES for '{client.customer_name}' "
                f"(Activities: {len(client.activities)})"
            )
            if self.buzzer:
                self.buzzer.beep(self.TONE_SELECT, 70)
            self.updateView()

        elif self.mode == self.MODE_ACTIVITIES:
            self.backToClients()

    def backToClients(self) -> None:
        """
        Returns immediately to `MODE_CLIENTS` (the main client directory view) from
        either `MODE_CONTACTS` or `MODE_ACTIVITIES`.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. Return to the client directory list:
           `crm.backToClients()`
        2. Verify active mode is MODE_CLIENTS:
           `assert crm.mode == CRMController.MODE_CLIENTS`
        """
        client = self.currentClient()
        cname = client.customer_name if client else "None"
        Log.i(f"CRMController: backToClients() from {self.mode} (Client: '{cname}')")
        self.mode = self.MODE_CLIENTS
        if self.buzzer:
            self.buzzer.beep(self.TONE_BACK, 70)
        self.updateView()

    def _playClientEngagementFeedback(self, client: Client) -> None:
        """
        Plays an audio signature on the **PassiveBuzzer** reflecting the client's CRM activity status:
        - Has activities and contacts: ascending 3-note chord (`523 -> 659 -> 784 Hz`).
        - Has activities or contacts only: 2-note chime (`523 -> 659 Hz`).
        - Has 0 activities: low warning tone (`220 Hz` for 200 ms) alerting that no activities exist.
        """
        if not self.buzzer:
            return
        if client.hasActivities() and client.hasContacts():
            for tone in (self.TONE_NAV, self.TONE_SELECT, self.TONE_SUCCESS):
                self.buzzer.beep(tone, 55)
        elif client.hasActivities():
            for tone in (self.TONE_NAV, self.TONE_SELECT):
                self.buzzer.beep(tone, 65)
        else:
            Log.w(f"CRMController: Client '{client.customer_name}' has 0 activities -> playing warning tone")
            self.buzzer.beep(self.TONE_WARN_RED, 180)

    def _updateLightStripForClient(self, client: Client) -> None:
        """
        Updates the **LightStrip** color and active pixel count based on the client's CRM state:
        - Details not yet loaded (Option B before selection): **CYAN** with 2 indicator LEDs.
        - **0 Activities** (Inactive/Prospect warning): **RED** across all 8 LEDs (as suggested in lab prompt).
        - **Has Activities AND Contacts** (Engaged Client): **GREEN** scaled to engagement level.
        - **Has Activities but 0 Contacts**: **YELLOW** scaled to engagement level.
        """
        if not self.lightstrip or not client:
            return

        num_leds = getattr(self.lightstrip, "_numleds", 8)

        if not client.details_loaded:
            self.lightstrip.setColor(self.COLOR_CYAN, num_leds)
            return

        if not client.hasActivities():
            # Lab instruction highlight: customers who don't have any activities show RED on lightstrip
            Log.i(f"CRMController: LightStrip -> RED (Client '{client.customer_name}' has 0 activities)")
            self.lightstrip.setColor(self.COLOR_RED, num_leds)
        elif client.hasContacts():
            leds = client.getEngagementLevel(num_leds)
            Log.i(
                f"CRMController: LightStrip -> GREEN ({leds}/{num_leds} LEDs for "
                f"'{client.customer_name}': {len(client.contacts)} contacts, {len(client.activities)} activities)"
            )
            self.lightstrip.setColor(self.COLOR_GREEN, leds)
        else:
            leds = client.getEngagementLevel(num_leds)
            Log.i(
                f"CRMController: LightStrip -> YELLOW ({leds}/{num_leds} LEDs for "
                f"'{client.customer_name}': 0 contacts, {len(client.activities)} activities)"
            )
            self.lightstrip.setColor(self.COLOR_YELLOW, leds)

    def updateView(self) -> None:
        """
        Refreshes the 16x2 **LCDDisplay** and **LightStrip** to reflect the current mode
        (`MODE_CLIENTS`, `MODE_CONTACTS`, or `MODE_ACTIVITIES`) and currently selected item.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. Refresh LCD and LightStrip:
           `crm.updateView()`
        """
        client = self.currentClient()
        if not client:
            self._showStatus("No CRM Clients", "Check Network", self.COLOR_RED)
            return

        if self.mode == self.MODE_CLIENTS:
            line0, line1 = client.getDisplayLines(
                index=self._clientIndex + 1, total=len(self.clients)
            )
        elif self.mode == self.MODE_CONTACTS:
            if client.hasContacts():
                contact = self.currentContact()
                line0, line1 = contact.getDisplayLines(
                    index=self._contactIndex + 1, total=len(client.contacts)
                )
            else:
                line0 = f"{client.customer_name[:11]:<11} C:0"
                line1 = "No Contacts Fnd "
        elif self.mode == self.MODE_ACTIVITIES:
            if client.hasActivities():
                activity = self.currentActivity()
                line0, line1 = activity.getDisplayLines(
                    index=self._activityIndex + 1, total=len(client.activities)
                )
            else:
                line0 = f"{client.customer_name[:11]:<11} A:0"
                line1 = "No Activities!  "
        else:
            line0, line1 = client.getDisplayLines()

        self._renderLCD(line0, line1)
        self._updateLightStripForClient(client)

    def _showStatus(self, line0: str, line1: str, color: tuple = None) -> None:
        """Displays a two-line status banner on the LCD and optionally sets the LightStrip color."""
        self._renderLCD(line0, line1)
        if self.lightstrip and color is not None:
            self.lightstrip.setColor(color)

    def _renderLCD(self, line0: str, line1: str) -> None:
        """Safely writes two 16-character lines to the **LCDDisplay** and logs the output."""
        pad0 = f"{line0:<16}"[:16]
        pad1 = f"{line1:<16}"[:16]
        Log.i(f"LCD [{self.mode}] -> Row 0: '{pad0}' | Row 1: '{pad1}'")
        if self.display:
            if hasattr(self.display, "_working"):
                self.display._working = False
            self.display.clear()
            self.display.showText(pad0, 0, 0)
            self.display.showText(pad1, 1, 0)

    def buttonPressed(self, name: str) -> None:
        """
        Interrupt callback invoked by PicoLibrary's **Button** when a button is pressed.
        Queues the button name so that network I/O and LCD I2C updates execute safely outside
        the hardware ISR context when running the main loop, or executes immediately during
        synchronous testing.

        Parameters:
        ----------
        name : str
            Name of the button that was pressed (`"previous"`, `"next"`, `"select"`, `"back"`)

        Examples:
        ---------
        1. Simulate pressing the Select button:
           `crm.buttonPressed("select")`
        2. Simulate pressing the Next button:
           `crm.buttonPressed("next")`
        """
        Log.i(f"CRMController: buttonPressed('{name}')")
        if self._running:
            self._pendingEvents.append(name)
        else:
            self._handleButtonAction(name)

    def buttonReleased(self, name: str) -> None:
        """
        Interrupt callback invoked by PicoLibrary's **Button** when a button is released.

        Parameters:
        ----------
        name : str
            Name of the button that was released

        Examples:
        ---------
        1. Handle button release:
           `crm.buttonReleased("select")`
        """
        Log.d(f"CRMController: buttonReleased('{name}')")

    def _handleButtonAction(self, name: str) -> None:
        """Dispatches a button press event to the appropriate navigation method."""
        norm = str(name).strip().lower()
        if norm in ("next", "right", "down", "btn2", "button2"):
            self.nextItem()
        elif norm in ("previous", "prev", "left", "up", "btn1", "button1"):
            self.previousItem()
        elif norm in ("select", "enter", "mode", "action", "btn3", "button3"):
            self.selectCurrent()
        elif norm in ("back", "return", "cancel", "home", "btn4", "button4"):
            self.backToClients()

    def run(self, poll_delay: float = 0.05) -> None:
        """
        Starts the CRM controller (if not already started) and runs the main event loop
        processing button presses asynchronously.

        Parameters:
        ----------
        poll_delay : float, optional
            Sleep interval in seconds between event queue checks (default: `0.05`)

        Examples:
        ---------
        1. Start and run the interactive hardware loop:
           `crm.run()`
        """
        if not self.clients:
            self.start()
        self._running = True
        Log.i("CRMController: Event loop running. Press buttons to browse Clients, Contacts, and Activities.")
        try:
            while self._running:
                while self._pendingEvents:
                    evt = self._pendingEvents.pop(0)
                    self._handleButtonAction(evt)
                time.sleep(poll_delay)
        except KeyboardInterrupt:
            Log.i("CRMController: KeyboardInterrupt received; stopping controller")
            self.stop()

    def stop(self) -> None:
        """
        Stops the controller loop and turns off the **LightStrip** and **PassiveBuzzer**.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. Stop the controller cleanly:
           `crm.stop()`
        """
        self._running = False
        for btn in self.buttons:
            if hasattr(btn, "setHandler"):
                btn.setHandler(None)
        if self.buzzer:
            self.buzzer.stop()
        if self.lightstrip:
            self.lightstrip.off()
        Log.i("CRMController: stopped")


if __name__ == "__main__":
    Log.i("Starting self-contained verification for CRMController")

    class _MockNet:
        def isConnected(self):
            return True

        def connect(self, ssid, password=None):
            pass

        def getLocalIp(self):
            return "192.168.1.105"

        def getJson(self, url):
            if url.endswith("/version"):
                return {"version": "1.0"}
            elif url.endswith("/get_customers"):
                return {
                    "items": [
                        {
                            "id": 128058722105441789727396196677757602970,
                            "customer_name": "Jessica Camacho",
                            "category": "Consumer",
                            "geography_name": "North America",
                            "type": "Production",
                        },
                        {
                            "id": 1,
                            "customer_name": "Carlton Closets",
                            "category": "Corporate",
                            "geography_name": "North America",
                            "type": "Planning / Prospecting",
                        },
                    ]
                }
            elif "/get_contacts/" in url:
                if "128058722105441789727396196677757602970" in url:
                    return {
                        "items": [
                            {
                                "id": 501,
                                "name": "Jessica Camacho",
                                "title": "Architect",
                                "company": "FIU IoT Lab",
                                "phone": "305-348-2000",
                                "contact_type": "Customer",
                            }
                        ]
                    }
                return {
                    "items": [
                        {
                            "id": 1,
                            "name": "Barry Bruce",
                            "title": "CFO",
                            "company": "California Closets",
                            "phone": "295-732-1037",
                            "contact_type": "Customer",
                        }
                    ]
                }
            elif "/get_activities/" in url:
                if "128058722105441789727396196677757602970" in url:
                    return {
                        "items": [
                            {
                                "id": 601,
                                "activity_type": "Conference",
                                "name": "CRM IoT Demo",
                                "description": "Presenting Pico 2W CRM integration",
                                "activity_date": "2026-11-21T00:00:00Z",
                                "owner": "Jessica Camacho",
                                "location": "Miami",
                            }
                        ]
                    }
                return {"items": []}
            return {"items": []}

    class _MockLCD:
        def __init__(self):
            self.rows = ["", ""]

        def clear(self, line=-1):
            self.rows = ["", ""]

        def showText(self, text, row=0, col=0):
            self.rows[row] = text

    class _MockStrip:
        def __init__(self):
            self._numleds = 8
            self.color = None
            self.pixels = 0

        def setColor(self, color, numPixels=None):
            self.color = color
            self.pixels = self._numleds if numPixels is None else numPixels

        def off(self):
            self.color = (0, 0, 0)
            self.pixels = 0

    class _MockBuzzer:
        def __init__(self):
            self.tones = []

        def beep(self, tone=500, duration=50):
            self.tones.append(tone)

        def stop(self):
            pass

    mock_net = _MockNet()
    mock_lcd = _MockLCD()
    mock_strip = _MockStrip()
    mock_buzzer = _MockBuzzer()

    crm = CRMController(
        preload=False,
        net=mock_net,
        display=mock_lcd,
        lightstrip=mock_strip,
        buzzer=mock_buzzer,
        buttons=[],
    )

    # 1. Start with Option B (Clients only)
    crm.start()
    assert crm.mode == CRMController.MODE_CLIENTS
    assert crm.currentClient().customer_name == "Jessica Camacho"
    assert crm.currentClient().details_loaded is False

    # 2. Select Jessica Camacho -> triggers lazy loading of contacts & activities, enters MODE_CONTACTS
    crm.buttonPressed("select")
    assert crm.mode == CRMController.MODE_CONTACTS
    assert crm.currentClient().details_loaded is True
    assert mock_strip.color == CRMController.COLOR_GREEN

    # 3. Press Select again -> enters MODE_ACTIVITIES
    crm.buttonPressed("select")
    assert crm.mode == CRMController.MODE_ACTIVITIES
    assert crm.currentActivity().name == "CRM IoT Demo"

    # 4. Press Select again -> returns to MODE_CLIENTS
    crm.buttonPressed("select")
    assert crm.mode == CRMController.MODE_CLIENTS

    # 5. Navigate to Carlton Closets (which has 0 activities) and select -> LightStrip turns RED
    crm.buttonPressed("next")
    assert crm.currentClient().customer_name == "Carlton Closets"
    crm.buttonPressed("select")
    assert mock_strip.color == CRMController.COLOR_RED

    crm.stop()
    Log.i("Testing complete - all CRMController checks passed")
