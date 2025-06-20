#!/usr/bin/env python3
"""
Firebase SDK script to set 'persistent' field for users collection.
If persistent is not present:
- If email is present, set persistent to true
- Else set persistent to false
"""

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import os
from typing import Dict, Any

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    # Path to your service account key file
    key_path = "/Users/adrianobarbet/Desktop/Coding/WebDev/aeochecker/Keys/aeochecker-ai-seo-firebase-adminsdk-fbsvc-5f2f1b78d8.json"
    
    try:
        # Check if the key file exists
        if not os.path.exists(key_path):
            raise FileNotFoundError(f"Service account key file not found at: {key_path}")
        
        # Initialize Firebase with service account credentials
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized with service account credentials")
        
    except Exception as e:
        print(f"❌ Failed to initialize Firebase: {e}")
        raise

def update_user_persistent_field(db, doc_ref, doc_data: Dict[str, Any], doc_id: str) -> bool:
    """
    Update the persistent field for a user document if it's not present.
    
    Args:
        db: Firestore database instance
        doc_ref: Document reference
        doc_data: Document data
        doc_id: Document ID
        
    Returns:
        bool: True if document was updated, False otherwise
    """
    # Check if 'persistent' field is already present
    if 'persistent' in doc_data:
        print(f"⏭️  User {doc_id}: 'persistent' field already exists ({doc_data['persistent']})")
        return False
    
    # Determine persistent value based on email presence
    has_email = 'email' in doc_data and doc_data['email'] is not None and doc_data['email'].strip()
    persistent_value = has_email
    
    try:
        # Update the document with the persistent field
        doc_ref.update({'persistent': persistent_value})
        
        email_status = f"email: {doc_data.get('email', 'N/A')}" if has_email else "no email"
        print(f"✅ User {doc_id}: Set persistent = {persistent_value} ({email_status})")
        return True
        
    except Exception as e:
        print(f"❌ Failed to update user {doc_id}: {e}")
        return False

def process_users_collection():
    """Main function to process all users in the collection"""
    print("🚀 Starting Firebase users collection update...")
    
    # Initialize Firebase
    initialize_firebase()
    
    # Get Firestore database instance
    db = firestore.client()
    
    # Get reference to users collection
    users_ref = db.collection('users')
    
    try:
        # Get all documents in the users collection
        docs = users_ref.stream()
        
        updated_count = 0
        total_count = 0
        
        print("\n📋 Processing users...")
        
        for doc in docs:
            total_count += 1
            doc_data = doc.to_dict()
            
            if update_user_persistent_field(db, doc.reference, doc_data, doc.id):
                updated_count += 1
        
        print(f"\n📊 Summary:")
        print(f"   Total users processed: {total_count}")
        print(f"   Users updated: {updated_count}")
        print(f"   Users skipped (already had persistent field): {total_count - updated_count}")
        
        if updated_count > 0:
            print(f"\n✅ Successfully updated {updated_count} user(s)")
        else:
            print(f"\n✅ No updates needed - all users already have 'persistent' field")
            
    except Exception as e:
        print(f"❌ Error accessing users collection: {e}")
        raise

if __name__ == "__main__":
    try:
        process_users_collection()
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Script failed: {e}")
        exit(1)