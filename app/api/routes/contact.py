from fastapi import APIRouter, HTTPException, status, Body
from app.schemas.contact import ContactMessageCreate, ContactMessageInDB
from app.services.contact_service import ContactService
from app.schemas.user import UserInDB

router = APIRouter(
    prefix="/contact",
    tags=["contact"],
)

@router.post(
    "", 
    response_model=ContactMessageInDB, 
    status_code=status.HTTP_201_CREATED,
    summary="Submit a contact message"
)
async def submit_contact_message(
    contact_request: ContactMessageCreate = Body(...)
):
    """
    Receive a contact message from the frontend and save it.

    - **user**: Optional information about the logged-in user (if any).
    - **email**: The email address provided in the contact form.
    - **message**: The content of the contact message.
    """
    try:
        # The user field in ContactMessageCreate is already typed as Optional[UserInDB]
        # So, contact_request.user will be either a UserInDB instance or None.
        saved_message = await ContactService.save_contact_message(contact_request)
        return saved_message
    except Exception as e:
        # Log the exception e for debugging purposes
        print(f"Error saving contact message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while saving the contact message."
        ) 