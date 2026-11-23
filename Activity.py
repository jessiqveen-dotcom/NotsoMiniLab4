"""
# Activity.py
# Domain model representing a customer activity in the IoT CRM system
# Author: jessiqveen-dotcom
"""

from Log import *


class Activity:
    """
    **Activity** represents an interaction or engagement performed with a **Client**
    in the CRM system (e.g., *Presentation*, *Phone Call*, *Conference*, *Meeting*).
    Stores activity details retrieved from the Oracle ORDS REST webservice
    (`/customer/get_activities/:cust_id` or `/customer/get_all_activities`) and formats
    them for a 16x2 character LCD display.

    Parameters:
    ----------
    id : int or str
        Unique identifier of the activity record
    activity_type : str
        Type of activity (e.g., *"Meeting"*, *"Presentation"*, *"Phone Call"*, *"Conference"*)
    name : str
        Short title or name of the activity
    description : str, optional
        Detailed description of the activity (default: "")
    activity_date : str, optional
        ISO date string of when the activity took place (default: "")
    owner : str, optional
        Staff member who performed or owns the activity (default: "")
    location : str, optional
        City or venue where the activity occurred (default: "")

    Examples:
    ---------
    1. Create an Activity directly:
       `act = Activity(1, "Presentation", "Cloud Overview", "Cloud migration deck", "2026-10-14", "Irene Walker", "Miami")`
    2. Create an Activity from an ORDS JSON dictionary and format for LCD:
       `act = Activity.fromJson(item_dict)`
       `line0, line1 = act.getDisplayLines()`
    """

    def __init__(
        self,
        id,
        activity_type: str,
        name: str,
        description: str = "",
        activity_date: str = "",
        owner: str = "",
        location: str = "",
    ):
        self.id = id
        self.activity_type = str(activity_type) if activity_type is not None else "Activity"
        self.name = str(name) if name is not None else "Unnamed"
        self.description = str(description) if description is not None else ""
        self.activity_date = str(activity_date)[:10] if activity_date else ""
        self.owner = str(owner) if owner is not None else "Unassigned"
        self.location = str(location) if location is not None else ""
        Log.i(f"Activity created: [{self.activity_type}] {self.name} (Owner: {self.owner})")

    @classmethod
    def fromJson(cls, data: dict):
        """
        Creates an **Activity** instance from a JSON dictionary returned by the ORDS REST API.

        Parameters:
        ----------
        data : dict
            Dictionary containing keys `id`, `activity_type`, `name`, `description`,
            `activity_date`, `owner`, `location`

        Examples:
        ---------
        1. Parse an ORDS activity item:
           `act = Activity.fromJson({"id": 1, "activity_type": "Presentation", "name": "Cloud Overview"})`
        2. Parse an item with owner and location:
           `act = Activity.fromJson({"id": 5, "activity_type": "Conference", "name": "Demo Grounds", "owner": "Irene Walker", "location": "Miami"})`
        """
        return cls(
            id=data.get("id", 0),
            activity_type=data.get("activity_type") or "Activity",
            name=data.get("name") or "Unnamed",
            description=data.get("description") or "",
            activity_date=data.get("activity_date") or "",
            owner=data.get("owner") or "Unassigned",
            location=data.get("location") or "",
        )

    def getDisplayLines(self, index: int = None, total: int = None) -> tuple:
        """
        Formats the activity information as a 2-tuple of 16-character strings `(line0, line1)`
        suitable for rendering on a 16x2 character **LCDDisplay**.

        Parameters:
        ----------
        index : int, optional
            1-based index of this activity when browsing a list (default: None)
        total : int, optional
            Total number of activities for the active client (default: None)

        Examples:
        ---------
        1. Format single activity lines:
           `line0, line1 = act.getDisplayLines()`
        2. Format activity lines with pagination badge:
           `line0, line1 = act.getDisplayLines(index=1, total=3)`
        """
        if index is not None and total is not None and total > 0:
            badge = f"{index}/{total}"
            max_name = 16 - len(badge) - 1
            line0 = f"{self.name[:max_name]:<{max_name}} {badge}"
        else:
            line0 = f"A:{self.name[:14]:<14}"

        detail = self.activity_type
        if self.location:
            line1 = f"{detail[:9]:<9}@{self.location[:6]:<6}"
        elif self.owner and self.owner != "Unassigned":
            line1 = f"{detail[:7]:<7}:{self.owner[:8]:<8}"
        else:
            line1 = f"{detail[:16]:<16}"

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
           `text = act.getDisplay()`
        2. Split lines for LCD rendering:
           `l0, l1 = act.getDisplay().split("\\n")`
        """
        line0, line1 = self.getDisplayLines()
        return f"{line0}\n{line1}"

    def __str__(self) -> str:
        return f"Activity(id={self.id}, type='{self.activity_type}', name='{self.name}', owner='{self.owner}')"


if __name__ == "__main__":
    Log.i("Starting self-contained verification for Activity")

    sample_json = {
        "id": 1,
        "activity_type": "Presentation",
        "name": "Cloud Overview",
        "description": "Outlining the architecture and benefits of moving to the cloud",
        "activity_date": "2026-10-14T00:00:00Z",
        "owner": "Irene Walker",
        "location": "Miami",
    }
    act = Activity.fromJson(sample_json)
    assert act.id == 1
    assert act.activity_type == "Presentation"
    assert act.name == "Cloud Overview"
    assert act.activity_date == "2026-10-14"
    assert act.owner == "Irene Walker"

    l0, l1 = act.getDisplayLines(index=1, total=3)
    Log.i(f"LCD Preview -> [{l0}] | [{l1}]")
    assert len(l0) == 16
    assert len(l1) == 16
    assert "1/3" in l0

    Log.i("Testing complete - all Activity checks passed")
