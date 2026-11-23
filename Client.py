"""
# Client.py
# Domain model representing a CRM customer/client with associated contacts and activities
# Author: jessiqveen-dotcom
"""

from Log import *
from Contact import Contact
from Activity import Activity


class Client:
    """
    **Client** represents a customer organization or individual in the IoT CRM machine.
    Maintains client profile metadata along with lists of associated **Contact** and
    **Activity** objects. Supports both **Option A (Eager Preloading)** and
    **Option B (On-Demand Lazy Loading)** via the `details_loaded` state flag.

    Parameters:
    ----------
    id : int or str
        Unique customer ID in the Oracle CRM database
    customer_name : str
        Name of the client or organization
    category : str, optional
        Client category, e.g., *"Corporate"*, *"Consumer"*, *"Nonprofit"* (default: "Corporate")
    category_description : str, optional
        Detailed description of the client category (default: "")
    geography_name : str, optional
        Geographic region of the client, e.g., *"North America"* (default: "North America")
    client_type : str, optional
        Engagement stage/type, e.g., *"Production"*, *"Proof of Concept (PoC)"* (default: "Prospect")

    Examples:
    ---------
    1. Create a Client and attach a Contact and an Activity:
       `client = Client(19, "Illumina Biotech", "Consumer", "General Consumer", "North America", "Evaluation / Testing")`
       `client.addContact(Contact(1, "Barry Bruce", "CFO"))`
       `client.addActivity(Activity(1, "Presentation", "Cloud Overview"))`
    2. Create a Client from an ORDS JSON dictionary:
       `client = Client.fromJson(item_dict)`
    """

    def __init__(
        self,
        id,
        customer_name: str,
        category: str = "Corporate",
        category_description: str = "",
        geography_name: str = "North America",
        client_type: str = "Prospect",
    ):
        self.id = id
        self.customer_name = str(customer_name) if customer_name is not None else "Unknown Client"
        self.category = str(category) if category is not None else "General"
        self.category_description = str(category_description) if category_description is not None else ""
        self.geography_name = str(geography_name) if geography_name is not None else "Global"
        self.client_type = str(client_type) if client_type is not None else "Standard"
        self.contacts = []
        self.activities = []
        self.details_loaded = False
        Log.i(f"Client created: {self.customer_name} (ID: {self.id}, Category: {self.category})")

    @classmethod
    def fromJson(cls, data: dict):
        """
        Creates a **Client** instance from a JSON dictionary returned by the ORDS REST API
        (`/customer/get_customers` or `/customer/get_customer/:id`).

        Parameters:
        ----------
        data : dict
            Dictionary containing `id`, `customer_name`, `category`, `category_description`,
            `geography_name`, and `type`

        Examples:
        ---------
        1. Parse an ORDS customer item:
           `client = Client.fromJson({"id": 19, "customer_name": "Illumina Biotech", "category": "Consumer"})`
        2. Parse a custom student customer entry:
           `client = Client.fromJson({"id": 128058, "customer_name": "Jessica Camacho", "category": "Consumer"})`
        """
        return cls(
            id=data.get("id", 0),
            customer_name=data.get("customer_name") or "Unknown Client",
            category=data.get("category") or "General",
            category_description=data.get("category_description") or "",
            geography_name=data.get("geography_name") or "Global",
            client_type=data.get("type") or "Standard",
        )

    def addContact(self, contact: Contact) -> None:
        """
        Adds a **Contact** object to this client's contact list.

        Parameters:
        ----------
        contact : Contact
            The Contact instance to associate with this client

        Examples:
        ---------
        1. Add a contact to a client:
           `client.addContact(Contact(1, "Jane Doe", "VP Engineering"))`
        2. Verify contact count after adding:
           `assert len(client.contacts) == 1`
        """
        self.contacts.append(contact)

    def setContacts(self, contacts: list) -> None:
        """
        Replaces this client's contact list with the provided list of **Contact** objects.

        Parameters:
        ----------
        contacts : list of Contact
            List of Contact instances retrieved for this client

        Examples:
        ---------
        1. Set contacts list:
           `client.setContacts([Contact(1, "Alice"), Contact(2, "Bob")])`
        2. Clear contacts list:
           `client.setContacts([])`
        """
        self.contacts = list(contacts)

    def addActivity(self, activity: Activity) -> None:
        """
        Adds an **Activity** object to this client's activity list.

        Parameters:
        ----------
        activity : Activity
            The Activity instance to associate with this client

        Examples:
        ---------
        1. Add an activity to a client:
           `client.addActivity(Activity(10, "Meeting", "Kickoff Call"))`
        2. Verify activity status after adding:
           `assert client.hasActivities() is True`
        """
        self.activities.append(activity)

    def setActivities(self, activities: list) -> None:
        """
        Replaces this client's activity list with the provided list of **Activity** objects.

        Parameters:
        ----------
        activities : list of Activity
            List of Activity instances retrieved for this client

        Examples:
        ---------
        1. Set activities list:
           `client.setActivities([Activity(1, "Meeting", "Face-to-Face")])`
        2. Clear activities list:
           `client.setActivities([])`
        """
        self.activities = list(activities)

    def hasContacts(self) -> bool:
        """Returns `True` if the client has at least one contact loaded."""
        return len(self.contacts) > 0

    def hasActivities(self) -> bool:
        """Returns `True` if the client has at least one activity loaded."""
        return len(self.activities) > 0

    def getEngagementLevel(self, max_leds: int = 8) -> int:
        """
        Calculates how many LEDs on the **LightStrip** (`1` to `max_leds`) should be illuminated
        to visualize the client's engagement level based on their number of activities and contacts.

        Parameters:
        ----------
        max_leds : int, optional
            Total number of NeoPixel LEDs on the LightStrip (default: 8)

        Examples:
        ---------
        1. Get engagement LED count for an 8-LED strip:
           `num_leds = client.getEngagementLevel(8)`
        2. Check LED level when no activities exist:
           `assert client.getEngagementLevel(8) == 8`
        """
        if not self.details_loaded:
            return max_leds
        if len(self.activities) == 0 and len(self.contacts) == 0:
            return max_leds  # Full red alert strip when no activities or contacts
        score = len(self.activities) * 2 + len(self.contacts)
        return max(2, min(max_leds, score))

    def getDisplayLines(self, index: int = None, total: int = None) -> tuple:
        """
        Formats the client summary as a 2-tuple of 16-character strings `(line0, line1)`
        suitable for rendering on a 16x2 character **LCDDisplay**.

        Parameters:
        ----------
        index : int, optional
            1-based index of this client in the directory list (default: None)
        total : int, optional
            Total number of clients in the directory list (default: None)

        Examples:
        ---------
        1. Format client lines without index:
           `line0, line1 = client.getDisplayLines()`
        2. Format client lines with index and total count:
           `line0, line1 = client.getDisplayLines(index=1, total=22)`
        """
        if index is not None and total is not None and total > 0:
            badge = f"{index}/{total}"
            max_name = 16 - len(badge) - 1
            line0 = f"{self.customer_name[:max_name]:<{max_name}} {badge}"
        else:
            line0 = f"{self.customer_name[:16]:<16}"

        if self.details_loaded:
            stats = f"C:{len(self.contacts)} A:{len(self.activities)}"
            cat_len = 16 - len(stats) - 1
            line1 = f"{self.category[:cat_len]:<{cat_len}} {stats}"
        else:
            geo_short = self.geography_name[:6]
            line1 = f"{self.category[:9]:<9} {geo_short:>6}"

        return (f"{line0:<16}"[:16], f"{line1:<16}"[:16])

    def getDisplay(self) -> str:
        """
        Returns a newline-separated two-line string representation for a 16x2 LCD.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. Get combined display string:
           `text = client.getDisplay()`
        2. Split lines for LCD rendering:
           `l0, l1 = client.getDisplay().split("\\n")`
        """
        line0, line1 = self.getDisplayLines()
        return f"{line0}\n{line1}"

    def __str__(self) -> str:
        return (
            f"Client(id={self.id}, name='{self.customer_name}', "
            f"contacts={len(self.contacts)}, activities={len(self.activities)}, "
            f"loaded={self.details_loaded})"
        )


if __name__ == "__main__":
    Log.i("Starting self-contained verification for Client")

    raw_customer = {
        "id": 128058722105441789727396196677757602970,
        "customer_name": "Jessica Camacho",
        "category": "Consumer",
        "category_description": "General Consumer",
        "geography_name": "North America",
        "type": "Production",
    }
    client = Client.fromJson(raw_customer)
    assert client.customer_name == "Jessica Camacho"
    assert client.hasContacts() is False
    assert client.hasActivities() is False

    l0, l1 = client.getDisplayLines(index=1, total=22)
    Log.i(f"Unloaded LCD Preview -> [{l0}] | [{l1}]")
    assert len(l0) == 16
    assert len(l1) == 16

    client.addContact(Contact(101, "Jessica Camacho", "Lead Architect", "FIU", "305-348-2000"))
    client.addActivity(Activity(201, "Meeting", "IoT CRM Demo", "Hardware demo", "2026-11-21", "Jessica Camacho", "Miami"))
    client.details_loaded = True

    assert client.hasContacts() is True
    assert client.hasActivities() is True
    l0_loaded, l1_loaded = client.getDisplayLines(index=1, total=22)
    Log.i(f"Loaded LCD Preview   -> [{l0_loaded}] | [{l1_loaded}]")
    assert "C:1 A:1" in l1_loaded

    Log.i("Testing complete - all Client checks passed")
