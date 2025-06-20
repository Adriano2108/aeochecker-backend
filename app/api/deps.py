from fastapi import Depends, HTTPException, status, Header
from app.core.firebase import firebase_auth, db
from firebase_admin.auth import InvalidIdTokenError, ExpiredIdTokenError
from typing import Optional

async def get_current_user(authorization: str = Header(...)):
    """
    Verify Firebase JWT token and retrieve user information
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split("Bearer ")[1]
    
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        uid = decoded_token["uid"]
        
        return {"uid": uid, "decoded_token": decoded_token}
    
    except InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user_optional(authorization: Optional[str] = Header(default=None)):
    """
    Optional authentication - returns user if valid auth provided, None otherwise
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.split("Bearer ")[1]
    
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        uid = decoded_token["uid"]
        
        return {"uid": uid, "decoded_token": decoded_token}
    
    except (InvalidIdTokenError, ExpiredIdTokenError, Exception):
        # If auth fails, just return None instead of raising exception
        return None

async def check_user_credits(user=Depends(get_current_user)):
    """
    Check if user has sufficient credits for analysis
    """
    user_doc = db.collection("users").document(user["uid"]).get()
    
    if not user_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database"
        )
    
    user_data = user_doc.to_dict()
    credits = user_data.get("credits", 0)
    
    if credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient credits"
        )
    
    return {"user": user, "credits": credits, "user_data": user_data} 