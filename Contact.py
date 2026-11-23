"""
# Contact.py
# Domain model representing a customer contact in the IoT CRM system
# Author: jessiqveen-dotcom
"""

from Log import *


class Contact:
    """
    **Contact** represents a person associated with a **Client** (Customer) in the CRM system.
    Stores contact details retrieved from the Oracle ORDS REST webservice
    (`/customer/get_contacts/:cust_id`) and formats them for a 16x2 character LCD display.

    Parameters:
    ----------
    id : int or str
        Unique identifier of the contact record
    name : str
        Full name of the contact person
    title : str, optional
        Job title or role of the contact (default: "Contact")
    company : str, optional
        Company name associated with the contact (default: "")
    phone : str, optional
        Telephone number of the contact (default: "")
    contact_type : str, optional
        Category or role type of the contact, e.g., *"Customer"* (default: "Customer")

    Examples:
    ---------
    1. Create a Contact directly:
       `c = Contact(101, "Jessica Camacho", "CTO", "Camacho Tech", "305-555-0199", "Customer")`
    2. Create a Contact from an ORDS JSON dictionary and format for LCD:
       `c = Contact.fromJson(item_dict)`
       `line0, line1 = c.getDisplayLines()`
    """

    def __init__(
        self,
        id,
        name: str,
        title: str = "Contact",
        company: str = "",
        phone: str = "",
        contact_type: str = "Customer",
    ):
        self.id = id
        self.name = str(name) if name is not None else "Unknown"
        self.title = str(title) if title is not None else "Contact"
        self.company = str(company) if company is not None else ""
        self.phone = str(phone) if phone is not None else "N/A"
        self.contact_type = str(contact_type) if contact_type is not None else "Customer"
        Log.i(f"Contact created: {self.name} ({self.title}) - {self.phone}")

    @classmethod
    def fromJson(cls, data: dict):
        """
        Creates a **Contact** instance from a JSON dictionary returned by the ORDS REST API.

        Parameters:
        ----------
        data : dict
            Dictionary containing keys `id`, `name`, `title`, `company`, `phone`, `contact_type`

        Examples:
        ---------
        1. Parse an ORDS contact item:
           `contact = Contact.fromJson({"id": 1, "name": "Barry Bruce", "title": "CFO", "phone": "295-732-1037"})`
        2. Parse a dictionary with missing optional fields:
           `contact = Contact.fromJson({"id": 2, "name": "Jessica Camacho"})`
        """
        return cls(
            id=data.get("id", 0),
            name=data.get("name") or "Unknown",
            title=data.get("title") or "Contact",
            company=data.get("company") or "",
            phone=data.get("phone") or "N/A",
            contact_type=data.get("contact_type") or "Customer",
        )

    def getDisplayLines(self, index: int = None, total: int = None) -> tuple:
        """
        Formats the contact information as a 2-tuple of 16-character strings `(line0, line1)`
        suitable for rendering on a 16x2 character **LCDDisplay**.

        Parameters:
        ----------
        index : int, optional
            1-based index of this contact when browsing a list (default: None)
        total : int, optional
            Total number of contacts for the active client (default: None)

        Examples:
        ---------
        1. Format single contact lines:
           `line0, line1 = contact.getDisplayLines()`
        2. Format contact lines with pagination badge:
           `line0, line1 = contact.getDisplayLines(index=1, total=2)`
        """
        if index is not None and total is not None and total > 0:
            badge = f"{index}/{total}"
            max_name = 16 - len(badge) - 1
            line0 = f"{self.name[:max_name]:<{max_name}} {badge}"
        else:
            line0 = f"C:{self.name[:14]:<14}"

        role_str = self.title if self.title else self.contact_type
        if self.phone and self.phone != "N/A":
            line1 = f"{role_str[:6]:<6} {self.phone[-9:]:>9}"
        else:
            line1 = f"{role_str[:16]:<16}"

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
           `text = contact.getDisplay()`
        2. Split lines for LCD rendering:
           `l0, l1 = contact.getDisplay().split("\\n")`
        """
        line0, line1 = self.getDisplayLines()
        return f"{line0}\n{line1}"

    def __str__(self) -> str:
        return f"Contact(id={self.id}, name='{self.name}', title='{self.title}', phone='{self.phone}')"


if __name__ == "__main__":
    Log.i("Starting self-contained verification for Contact")

    sample_json = {
        "id": 1,
        "name": "Barry Bruce",
        "title": "CFO",
        "company": "California Closets",
        "phone": "295-732-1037",
        "contact_type": "Customer",
    }
    contact = Contact.fromJson(sample_json)
    assert contact.id == 1
    assert contact.name == "Barry Bruce"
    assert contact.title == "CFO"
    assert contact.phone == "295-732-1037"

    l0, l1 = contact.getDisplayLines(index=1, total=2)
    Log.i(f"LCD Preview -> [{l0}] | [{l1}]")
    assert len(l0) == 16
    assert len(l1) == 16
    assert "1/2" in l0

    Log.i("Testing complete - all Contact checks passed")
