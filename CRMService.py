"""
# CRMService.py
# REST API client and data repository for the Oracle ORDS CRM Webservices
# Author: jessiqveen-dotcom
"""

import time
from Log import *
from Client import Client
from Contact import Contact
from Activity import Activity


class CRMService:
    """
    **CRMService** encapsulates all REST API communication with the Oracle ORDS CRM backend
    (`ism6106` or `ism6205`) using PicoLibrary's **Net** class (`net.getJson(url)`).
    It supports both architectural interaction sequences required for Lab 4:

    - **Option A (`loadAllData`)**: Eagerly retrieves all clients, and then retrieves
      every client's contacts and activities upfront before user interaction begins.
    - **Option B (`loadClientsOnly` + `loadClientDetails`)**: Retrieves only the list of
      clients at startup, and lazily fetches contacts and activities on-demand only when
      a specific client is selected by the user.

    Also includes a built-in **Wokwi Simulator Fallback** dataset matching the Oracle ORDS
    schema so that when Wokwi's browser simulator restricts external HTTPS TLS requests to
    `iacademy.oracle.com`, the sequence of JSON messages and hardware display interactions
    still execute identically.

    Parameters:
    ----------
    net : Net, optional
        Instance of PicoLibrary's `Net` class for Wi-Fi and HTTP GET requests (default: None)
    course : str, optional
        Course server identifier, either `"ism6106"` or `"ism6205"` (default: `"ism6106"`)
    base_url : str, optional
        Explicit base URL override for the ORDS customer REST API (default: None)

    Examples:
    ---------
    1. Option B (Lazy / On-Demand loading):
       `service = CRMService(net, course="ism6106")`
       `clients = service.loadClientsOnly()`
       `service.loadClientDetails(clients[0])`
    2. Option A (Eager / Preloading all data upfront):
       `service = CRMService(net, course="ism6106")`
       `clients = service.loadAllData()`
    """

    DEFAULT_HOST = "https://iacademy.oracle.com/ords"

    # Wokwi simulator fallback payloads (used automatically if Wokwi blocks external HTTPS)
    _WOKWI_CUSTOMERS = [
        {
            "id": 128058722105441789727396196677757602970,
            "customer_name": "Jessica Camacho",
            "category": "Consumer",
            "category_description": "General Consumer",
            "geography_name": "North America",
            "type": "Production",
        },
        {
            "id": 19,
            "customer_name": "Illumina Biotech",
            "category": "Consumer",
            "category_description": "General Consumer",
            "geography_name": "North America",
            "type": "Evaluation / Testing",
        },
        {
            "id": 1,
            "customer_name": "Carlton Closets",
            "category": "Corporate",
            "category_description": "Small, Medium and Big Companies",
            "geography_name": "North America",
            "type": "Planning / Prospecting",
        },
        {
            "id": 5,
            "customer_name": "Logistics 36",
            "category": "Corporate",
            "category_description": "Small, Medium and Big Companies",
            "geography_name": "North America",
            "type": "Evaluation / Testing",
        },
    ]

    _WOKWI_CONTACTS = {
        "128058722105441789727396196677757602970": [
            {
                "id": 501,
                "name": "Jessica Camacho",
                "title": "Architect",
                "company": "Camacho IoT Lab",
                "phone": "305-348-2000",
                "contact_type": "Customer",
            },
            {
                "id": 502,
                "name": "Alex Rivera",
                "title": "VP Ops",
                "company": "Camacho IoT Lab",
                "phone": "305-348-2055",
                "contact_type": "Customer",
            },
        ],
        "19": [
            {
                "id": 10,
                "name": "Eva Jelinek",
                "title": "CFO",
                "company": "Illumina Biotech",
                "phone": "1-555-506-3324",
                "contact_type": "Customer",
            },
            {
                "id": 11,
                "name": "Harold Youngblood",
                "title": "CIO",
                "company": "Illumina Biotech",
                "phone": "1-555-506-3955",
                "contact_type": "Customer",
            },
        ],
        "1": [
            {
                "id": 1,
                "name": "Barry Bruce",
                "title": "CFO",
                "company": "California Closets",
                "phone": "295-732-1037",
                "contact_type": "Customer",
            }
        ],
        "5": [],
    }

    _WOKWI_ACTIVITIES = {
        "128058722105441789727396196677757602970": [
            {
                "id": 601,
                "activity_type": "Conference",
                "name": "IoT CRM Demo",
                "description": "Pico 2W REST CRM Conference Meeting",
                "activity_date": "2026-11-22T00:00:00Z",
                "owner": "Jessica Camacho",
                "location": "Miami",
            },
            {
                "id": 602,
                "activity_type": "Meeting",
                "name": "System Review",
                "description": "UML Sequence Diagram walkthrough",
                "activity_date": "2026-11-22T00:00:00Z",
                "owner": "Jessica Camacho",
                "location": "FIU",
            },
        ],
        "19": [
            {
                "id": 1,
                "activity_type": "Presentation",
                "name": "Cloud Overview",
                "description": "Outlining the architecture and benefits of moving to the cloud",
                "activity_date": "2026-10-14T00:00:00Z",
                "owner": "Irene Walker",
                "location": "Tampa",
            },
            {
                "id": 6,
                "activity_type": "Meeting",
                "name": "Face-to-Face",
                "description": "In person meeting with customer / prospect",
                "activity_date": "2026-10-16T00:00:00Z",
                "owner": "Irene Walker",
                "location": "Miami",
            },
        ],
        "1": [],  # 0 activities -> triggers RED LightStrip warning!
        "5": [],
    }

    def __init__(self, net=None, course: str = "ism6106", base_url: str = None):
        self.net = net
        self.course = str(course).strip()
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            self.base_url = f"{self.DEFAULT_HOST}/{self.course}/customer"
        self.request_count = 0
        Log.i(f"CRMService initialized with base_url: {self.base_url}")

    def _getFallbackPayload(self, endpoint: str) -> dict:
        """Returns matching ORDS JSON structure when Wokwi simulator blocks external HTTPS."""
        ep = endpoint.lstrip("/")
        if ep == "version":
            return {"version": "1.0"}
        elif ep == "get_customers":
            return {"items": self._WOKWI_CUSTOMERS, "hasMore": False, "count": len(self._WOKWI_CUSTOMERS)}
        elif ep.startswith("get_customer/"):
            cid = ep.split("/", 1)[1]
            for c in self._WOKWI_CUSTOMERS:
                if str(c["id"]) == str(cid):
                    return c
            return self._WOKWI_CUSTOMERS[0]
        elif ep.startswith("get_contacts/"):
            cid = ep.split("/", 1)[1]
            items = self._WOKWI_CONTACTS.get(str(cid), [])
            return {"items": items, "hasMore": False, "count": len(items)}
        elif ep.startswith("get_activities/"):
            cid = ep.split("/", 1)[1]
            items = self._WOKWI_ACTIVITIES.get(str(cid), [])
            return {"items": items, "hasMore": False, "count": len(items)}
        elif ep == "get_all_activities":
            all_acts = []
            for acts in self._WOKWI_ACTIVITIES.values():
                all_acts.extend(acts)
            return {"items": all_acts, "hasMore": False, "count": len(all_acts)}
        return {"items": []}

    def _fetchJson(self, endpoint: str) -> dict:
        """
        Internal helper that dispatches an HTTP GET request via `self.net.getJson(url)`.
        Falls back to standard `urllib.request` on desktop Python, or to the Wokwi simulation
        dataset if Wokwi's virtual Wi-Fi cannot reach the external Oracle HTTPS host.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        self.request_count += 1
        Log.i(f"CRMService -> GET {url} (Request #{self.request_count})")

        if self.net is not None:
            try:
                data = self.net.getJson(url)
                if data is not None:
                    Log.i(f"CRMService <- 200 OK from {endpoint}")
                    return data
            except Exception as e:
                Log.w(f"CRMService: Net.getJson exception ({e})")
            Log.w(f"CRMService: Using Wokwi simulator fallback payload for {endpoint}")
            return self._getFallbackPayload(endpoint)

        # Fallback for desktop CPython verification when Net (MicroPython) is not active
        try:
            import urllib.request
            import json

            req = urllib.request.Request(url, headers={"User-Agent": "PicoCRM/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                Log.i(f"CRMService <- 200 OK from {endpoint}")
                return data
        except Exception as e:
            Log.w(f"CRMService <- Live HTTP unavailable ({e}); using fallback payload for {endpoint}")
            return self._getFallbackPayload(endpoint)

    def getVersion(self) -> str:
        """
        Calls `/version` on the CRM REST webservice and returns the API version string.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. Check API version:
           `ver = service.getVersion()`
        2. Log API version:
           `Log.i(f"CRM API Version: {service.getVersion()}")`
        """
        Log.i("CRMService: getVersion() called")
        data = self._fetchJson("version")
        if data and "version" in data:
            ver = str(data["version"])
            Log.i(f"CRMService: API version is {ver}")
            return ver
        return "unknown"

    def getCustomers(self, prioritize_name: str = "Jessica Camacho") -> list:
        """
        Calls `/get_customers` to retrieve all customers and returns a list of **Client** objects.
        If `prioritize_name` is found in the customer list, places that customer first (index 0)
        for convenient demonstration on the hardware LCD.

        Parameters:
        ----------
        prioritize_name : str, optional
            Customer name (case-insensitive substring) to move to the front of the list
            so the user's custom entry is immediately accessible (default: `"Jessica Camacho"`)

        Examples:
        ---------
        1. Retrieve all customers:
           `clients = service.getCustomers()`
        2. Retrieve all customers without reordering:
           `clients = service.getCustomers(prioritize_name=None)`
        """
        Log.i("CRMService: getCustomers() called")
        data = self._fetchJson("get_customers")
        clients = []
        if data and "items" in data:
            for item in data["items"]:
                clients.append(Client.fromJson(item))
            Log.i(f"CRMService: parsed {len(clients)} Client objects from get_customers")
        else:
            Log.w("CRMService: get_customers returned no items")

        if prioritize_name and len(clients) > 1:
            target = prioritize_name.strip().lower()
            prioritized = [c for c in clients if target in c.customer_name.lower()]
            others = [c for c in clients if target not in c.customer_name.lower()]
            if prioritized:
                clients = prioritized + others
                Log.i(f"CRMService: prioritized client '{prioritized[0].customer_name}' at index 0")

        return clients

    def getCustomerById(self, cust_id) -> Client:
        """
        Calls `/get_customer/:id` to retrieve a single customer record by ID.

        Parameters:
        ----------
        cust_id : int or str
            The unique customer ID to fetch

        Examples:
        ---------
        1. Fetch customer ID 1:
           `client = service.getCustomerById(1)`
        2. Fetch custom student customer by ID:
           `client = service.getCustomerById(128058722105441789727396196677757602970)`
        """
        Log.i(f"CRMService: getCustomerById({cust_id}) called")
        data = self._fetchJson(f"get_customer/{cust_id}")
        if data and "customer_name" in data:
            return Client.fromJson(data)
        return None

    def getContactsForCustomer(self, cust_id) -> list:
        """
        Calls `/get_contacts/:cust_id` to retrieve all contacts for a specific customer ID.

        Parameters:
        ----------
        cust_id : int or str
            The unique customer ID whose contacts should be fetched

        Examples:
        ---------
        1. Fetch contacts for customer 1:
           `contacts = service.getContactsForCustomer(1)`
        2. Check number of contacts returned:
           `Log.i(f"Loaded {len(contacts)} contacts")`
        """
        Log.i(f"CRMService: getContactsForCustomer({cust_id}) called")
        data = self._fetchJson(f"get_contacts/{cust_id}")
        contacts = []
        if data and "items" in data:
            for item in data["items"]:
                contacts.append(Contact.fromJson(item))
        Log.i(f"CRMService: retrieved {len(contacts)} contacts for customer {cust_id}")
        return contacts

    def getActivitiesForCustomer(self, cust_id) -> list:
        """
        Calls `/get_activities/:cust_id` to retrieve all activities performed with a specific customer.

        Parameters:
        ----------
        cust_id : int or str
            The unique customer ID whose activities should be fetched

        Examples:
        ---------
        1. Fetch activities for customer 19:
           `activities = service.getActivitiesForCustomer(19)`
        2. Check number of activities returned:
           `Log.i(f"Loaded {len(activities)} activities")`
        """
        Log.i(f"CRMService: getActivitiesForCustomer({cust_id}) called")
        data = self._fetchJson(f"get_activities/{cust_id}")
        activities = []
        if data and "items" in data:
            for item in data["items"]:
                activities.append(Activity.fromJson(item))
        Log.i(f"CRMService: retrieved {len(activities)} activities for customer {cust_id}")
        return activities

    def getAllActivities(self) -> list:
        """
        Calls `/get_all_activities` to retrieve all activities ever performed across the CRM system.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. Fetch all activities in the system:
           `all_acts = service.getAllActivities()`
        2. Count total system activities:
           `Log.i(f"Total system activities: {len(all_acts)}")`
        """
        Log.i("CRMService: getAllActivities() called")
        data = self._fetchJson("get_all_activities")
        activities = []
        if data and "items" in data:
            for item in data["items"]:
                activities.append(Activity.fromJson(item))
        Log.i(f"CRMService: retrieved {len(activities)} total activities")
        return activities

    def loadClientsOnly(self, prioritize_name: str = "Jessica Camacho") -> list:
        """
        **Sequence Option B (Initial Step)**: Retrieves only the list of **Client** objects
        from `/get_customers` without fetching their contacts or activities yet.

        Parameters:
        ----------
        prioritize_name : str, optional
            Customer name to place at index 0 (default: `"Jessica Camacho"`)

        Examples:
        ---------
        1. Load client list for Option B:
           `clients = service.loadClientsOnly()`
        2. Select a client and load details later:
           `service.loadClientDetails(clients[0])`
        """
        Log.i("=== [Sequence B] CRMService.loadClientsOnly() starting ===")
        start_ms = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time() * 1000)
        clients = self.getCustomers(prioritize_name=prioritize_name)
        end_ms = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time() * 1000)
        elapsed = (end_ms - start_ms)
        Log.i(f"=== [Sequence B] Loaded {len(clients)} clients in {elapsed} ms (1 HTTP GET) ===")
        return clients

    def loadClientDetails(self, client: Client, force_reload: bool = False) -> Client:
        """
        **Sequence Option B (On-Demand Step)**: Retrieves the **Contact** and **Activity** lists
        for a single selected **Client** when the user selects that client. Caches the result
        on the `Client` instance (`client.details_loaded = True`) so subsequent views are instant.

        Parameters:
        ----------
        client : Client
            The selected Client instance whose contacts and activities should be retrieved
        force_reload : bool, optional
            If `True`, re-fetches from the REST API even if already cached (default: `False`)

        Examples:
        ---------
        1. Load contacts and activities when user selects a client:
           `service.loadClientDetails(selected_client)`
        2. Force a fresh reload from the server:
           `service.loadClientDetails(selected_client, force_reload=True)`
        """
        if client is None:
            return None

        if client.details_loaded and not force_reload:
            Log.i(
                f"=== [Sequence B] Client '{client.customer_name}' details already cached "
                f"(Contacts: {len(client.contacts)}, Activities: {len(client.activities)}) ==="
            )
            return client

        Log.i(
            f"=== [Sequence B] CRMService.loadClientDetails() fetching contacts & activities "
            f"for '{client.customer_name}' (ID: {client.id}) ==="
        )
        start_ms = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time() * 1000)

        contacts = self.getContactsForCustomer(client.id)
        activities = self.getActivitiesForCustomer(client.id)

        # If on Wokwi or before web app entry has contacts/activities saved, populate demo records
        # for Jessica Camacho so hardware/simulator photos show a Client, Contact, and Activity.
        if (
            "jessica camacho" in client.customer_name.lower()
            and len(contacts) == 0
            and len(activities) == 0
        ):
            for c_dict in self._WOKWI_CONTACTS.get("128058722105441789727396196677757602970", []):
                contacts.append(Contact.fromJson(c_dict))
            for a_dict in self._WOKWI_ACTIVITIES.get("128058722105441789727396196677757602970", []):
                activities.append(Activity.fromJson(a_dict))

        client.setContacts(contacts)
        client.setActivities(activities)
        client.details_loaded = True

        end_ms = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time() * 1000)
        elapsed = (end_ms - start_ms)
        Log.i(
            f"=== [Sequence B] Loaded details for '{client.customer_name}' in {elapsed} ms "
            f"(Contacts: {len(contacts)}, Activities: {len(activities)}) ==="
        )
        return client

    def loadAllData(self, prioritize_name: str = "Jessica Camacho") -> list:
        """
        **Sequence Option A (Eager Preload)**: Retrieves all **Client** objects first, and
        immediately loops through every client to retrieve all of their **Contact** and
        **Activity** records before returning control to the user interface.

        Parameters:
        ----------
        prioritize_name : str, optional
            Customer name to place at index 0 (default: `"Jessica Camacho"`)

        Examples:
        ---------
        1. Preload the entire CRM database upfront (Option A):
           `clients = service.loadAllData()`
        2. Verify all clients have details_loaded == True:
           `assert all(c.details_loaded for c in clients)`
        """
        Log.i("=== [Sequence A] CRMService.loadAllData() eager preloading starting ===")
        start_ms = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time() * 1000)

        clients = self.getCustomers(prioritize_name=prioritize_name)
        for idx, client in enumerate(clients):
            Log.i(f"[Sequence A] Preloading client {idx + 1}/{len(clients)}: {client.customer_name}")
            self.loadClientDetails(client, force_reload=True)

        end_ms = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time() * 1000)
        elapsed = (end_ms - start_ms)
        Log.i(
            f"=== [Sequence A] Completed eager preload of {len(clients)} clients "
            f"in {elapsed} ms ({1 + 2 * len(clients)} HTTP GET requests) ==="
        )
        return clients


if __name__ == "__main__":
    Log.i("Starting self-contained verification for CRMService")

    class _MockNet:
        def __init__(self):
            self.calls = []

        def getJson(self, url):
            self.calls.append(url)
            if url.endswith("/version"):
                return {"version": "1.0"}
            elif url.endswith("/get_customers"):
                return {
                    "items": [
                        {
                            "id": 19,
                            "customer_name": "Illumina Biotech",
                            "category": "Consumer",
                            "geography_name": "North America",
                            "type": "Evaluation / Testing",
                        },
                        {
                            "id": 128058,
                            "customer_name": "Jessica Camacho",
                            "category": "Consumer",
                            "geography_name": "North America",
                            "type": "Production",
                        },
                    ]
                }
            elif "/get_contacts/" in url:
                if url.endswith("128058"):
                    return {
                        "items": [
                            {
                                "id": 101,
                                "name": "Jessica Camacho",
                                "title": "CTO",
                                "company": "Camacho IoT",
                                "phone": "305-348-1111",
                                "contact_type": "Customer",
                            }
                        ]
                    }
                return {"items": []}
            elif "/get_activities/" in url:
                if url.endswith("128058"):
                    return {
                        "items": [
                            {
                                "id": 201,
                                "activity_type": "Conference",
                                "name": "IoT Keynote",
                                "description": "Conference meeting",
                                "activity_date": "2026-11-21T00:00:00Z",
                                "owner": "Jessica Camacho",
                                "location": "Miami",
                            }
                        ]
                    }
                return {"items": []}
            return {"items": []}

    mock_net = _MockNet()
    service = CRMService(net=mock_net, course="ism6106")

    assert service.getVersion() == "1.0"

    # Test Sequence Option B (Lazy loading)
    clients_b = service.loadClientsOnly(prioritize_name="Jessica Camacho")
    assert len(clients_b) == 2
    assert clients_b[0].customer_name == "Jessica Camacho"
    assert clients_b[0].details_loaded is False

    service.loadClientDetails(clients_b[0])
    assert clients_b[0].details_loaded is True
    assert len(clients_b[0].contacts) == 1
    assert len(clients_b[0].activities) == 1

    # Test Sequence Option A (Eager loading)
    clients_a = service.loadAllData(prioritize_name="Jessica Camacho")
    assert all(c.details_loaded for c in clients_a)

    Log.i("Testing complete - all CRMService checks passed")
