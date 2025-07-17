from datetime import datetime
import uuid
from app.core.firebase import db
from app.schemas.contact import ContactMessageCreate, ContactMessageInDB, UserInDB
from firebase_admin import firestore

class ContactService:
    @staticmethod
    async def save_contact_message(contact_data: ContactMessageCreate) -> ContactMessageInDB:
        """
        Saves a contact message to Firestore.
        """
        collection_name = "contact_messages"
        message_id = str(uuid.uuid4())
        current_time = datetime.now()

        # Prepare user_data for Firestore: convert Pydantic model to dict
        # and handle potential None values explicitly if necessary.
        user_dict = None
        if contact_data.user:
            # Assuming UserInDB model has a .model_dump() method (standard in Pydantic v2)
            # or .dict() for Pydantic v1. Adjust if your UserInDB is different.
            # We also want to ensure that camelCase aliases are used for keys if specified in UserInDB's config.
            user_dict = contact_data.user.model_dump(by_alias=True)

        db_entry = {
            "id": message_id,
            "user": user_dict, # Store the user object (or None), changed from userData
            "email": contact_data.email,
            "message": contact_data.message,
            "createdAt": firestore.SERVER_TIMESTAMP # Use server timestamp for creation
        }

        db.collection(collection_name).document(message_id).set(db_entry)

        # For the return object, we want the actual timestamp, not the server placeholder
        # Fetching the doc again or using the client-side current_time are options.
        # Using client-side time for simplicity here.
        return ContactMessageInDB(
            id=message_id,
            user=contact_data.user,
            email=contact_data.email,
            message=contact_data.message,
            created_at=current_time
        ) 