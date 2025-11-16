from mcp.server.fastmcp import FastMCP, Context
from mcp.server.elicitation import (
    AcceptedElicitation,
    DeclinedElicitation,
    CancelledElicitation,
)
from pydantic import BaseModel, Field
from typing import Dict, Any
from datetime import datetime
import anyio
import logging
import os

# Configure logging to reduce noise
logging.getLogger("mcp").setLevel(logging.WARNING)

port = int(os.environ.get("PORT", 8000))
mcp = FastMCP("Demo: Elicitation MCP Server", host="0.0.0.0", port=port)

dlp_str = """
{"Name": "Xander Phillips", "Phone": "055 6560 3327", "Mail": "nisl@enim.co.uk", "Company": "Elit A Feugiat Consulting"},
{"Name": "Elton Benjamin", "Phone": "0912 107 4176", "Mail":
"in.consectetuer@famesacturpis.org", "Company": "Amet Massa Quisque Corporation"},
{"Name": "Victor Pruitt", "Phone": "055 9771 6292", "Mail": "diam@Proindolor.org", "Company": "Mi Lorem Corp."},
{"Name": "Lyle Lloyd", "Phone": "07078 577451", "Mail": "neque@semut.com", "Company": "Facilisis Incorporated"},
{"Name": "Acton Rosa", "Phone": "0321 973 5347", "Mail": "vehicula@Cras.ca", "Company": "Nullam Incorporated"},
{"Name": "Garrison Holman", "Phone": "0845 46 46", "Mail": "Morbi@orci.net", "Company": "Tortor Nibh Sit LLC"},
{"Name": "Dexter Holman", "Phone": "0845 46 48", "Mail": "erat@turpis.co.uk", "Company": "Amet Ltd"},
{"Name": "Octavius Sharp", "Phone": "0393 949 6894", "Mail":
"malesuada@turpisNullaaliquet.edu", "Company": "Aenean Gravida Associates"},
{"Name": "Byron Lindsay", "Phone": "0327 742 0303", "Mail":
"In.faucibus@penatibusetmagnis.co.uk", "Company": "Mollis Non LLC"},
{"Name": "Dalton Workman", "Phone": "0800 1111", "Mail":
"Mauris@Suspendissecommodotincidunt.edu", "Company": "Morbi Neque Inc."},
{"Name": "Fletcher Riggs", "Phone": "(016977) 4429", "Mail":
"et.ultrices@nonummy.co.uk", "Company": "A Ultricies Adipiscing Incorporated"},
{"Name": "Melvin Whitehead", "Phone": "(023) 1781 0755", "Mail": "tortor@vestibulum.com", "Company": "Et Institute"},
{"Name": "Slade Hoover", "Phone": "0800 117363", "Mail": "iaculis@nonjustoProin.ca", "Company": "Arcu Vestibulum LLC"},
{"Name": "Tarik Hopkins", "Phone": "0358 406 2831", "Mail": "velit@ultrices.net", "Company": "Nunc Foundation"}
"""

class ElicitationSchema:
    """Schema definitions for different elicitation types."""

    class GetDate(BaseModel):
        date: str = Field(
            description="Enter the date for your booking (YYYY-MM-DD)",
            pattern=r"^\d{4}-\d{2}-\d{2}$"
        )

    class GetPartySize(BaseModel):
        party_size: int = Field(
            description="Enter the number of people for your booking",
            ge=1,
            le=20
        )

    class ConfirmBooking(BaseModel):
        confirm: bool = Field(description="Confirm the booking")
        notes: str = Field(default="", description="Special requests or notes")


async def elicit_with_validation(
    ctx: Context,
    message: str,
    schema_class: type[BaseModel],
    field_name: str | None
) -> str | int | Dict[str, Any] | None:
    """Generic elicitation handler with validation and error handling."""

    try:
        result = await ctx.elicit(message=message, schema=schema_class)

        match result:
            case AcceptedElicitation(data=data):
                # Debug: print what we received
                print(f"DEBUG: Received data type: {type(data)}, "
                      f"value: {data}")

                # If field_name is None, return the entire data object
                if field_name is None:
                    return data
                # Otherwise return the specific field
                if hasattr(data, field_name):
                    return getattr(data, field_name)
                return None
            case DeclinedElicitation():
                return None
            case CancelledElicitation():
                return None
    except (anyio.ClosedResourceError, ConnectionError) as e:
        print(f"Client disconnected during elicitation: {e}")
        return None
    except Exception as e:
        print(f"Elicitation error: {e}")
        return None


def validate_date(date_str: str) -> bool:
    """Validate date format and ensure it's not in the past."""
    try:
        booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        return booking_date >= datetime.now().date()
    except ValueError:
        return False


@mcp.tool()
async def book_table(ctx: Context, date: str = "", party_size: int = 0) -> str:
    """Book a table with intelligent elicitation for missing or invalid
    data."""

    try:
        # Collect date if missing or invalid
        while not date or not validate_date(date):
            if date and not validate_date(date):
                message = (f"Invalid date '{date}'. Please enter a valid "
                           f"future date:")
            else:
                message = "Please enter the date for your booking:"

            date_result = await elicit_with_validation(
                ctx, message, ElicitationSchema.GetDate, "date"
            )

            if date_result is None:
                return "Date input cancelled. Booking cancelled."

            date = str(date_result)

        # Collect party size if missing or invalid
        while not party_size or party_size <= 0:
            if party_size <= 0 and party_size != 0:
                message = (f"Invalid party size '{party_size}'. Please enter "
                           f"a valid number of people:")
            else:
                message = "Please enter the party size for your booking:"

            party_result = await elicit_with_validation(
                ctx, message, ElicitationSchema.GetPartySize, "party_size"
            )

            if party_result is None:
                return "Party size input cancelled. Booking cancelled."

            party_size = int(party_result)

        # Confirm booking with all details
        confirmation = await elicit_with_validation(
            ctx,
            f"Please confirm your booking for {party_size} people on {date}.",
            ElicitationSchema.ConfirmBooking,
            None  # Return full data object
        )

        if confirmation is None:
            return "Booking confirmation cancelled."

        # Handle both dict and object formats
        try:
            if isinstance(confirmation, dict):
                confirm_value = confirmation.get('confirm', False)
                notes_value = confirmation.get('notes', '')
            else:
                # Use hasattr to check if attributes exist before
                # accessing them
                if hasattr(confirmation, 'confirm'):
                    confirm_value = confirmation.confirm
                else:
                    confirm_value = False
                if hasattr(confirmation, 'notes'):
                    notes_value = confirmation.notes
                else:
                    notes_value = ''

            if confirm_value:
                notes_text = f" Notes: {notes_value}" if notes_value else ""
                return (f"✅ Your table for {party_size} people on {date} "
                        f"has been booked.{notes_text} "
                        f"dlp_content: {dlp_str}")
            else:
                return "❌ Booking cancelled."
        except Exception as e:
            return (f"❌ Error processing confirmation: "
                    f"{type(confirmation)} - {str(e)}")

    except (anyio.ClosedResourceError, ConnectionError):
        print("Client disconnected during booking process")
        return "Client disconnected - booking cancelled."
    except Exception as e:
        print(f"Unexpected error in book_table: {e}")
        return f"❌ Booking failed due to unexpected error: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
