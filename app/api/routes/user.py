from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.user import UserResponse
from app.api.deps import get_current_user
from app.services.user import UserService
from typing import Dict, Any, List

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(get_current_user)]
)

@router.get("/me", response_model=UserResponse)
async def get_my_info(user=Depends(get_current_user)):
    """
    Get current user's profile information
    """
    user_data = await UserService.get_user_data(user["uid"])
    
    if not user_data:
        decoded_token = user.get("decoded_token", {})
        email = decoded_token.get("email", "")
        email = None if not email or email == "" else email
        name = decoded_token.get("name", "")
        
        user_data = await UserService.create_user_if_not_exists(
            user_id=user["uid"],
            email=email,
            display_name=name
        )
    
    return user_data

@router.post("/me/promote", response_model=UserResponse)
async def promote_user(user=Depends(get_current_user)):
    """
    Promote a user from anonymous to persistent authentication.
    """
    decoded_token = user.get("decoded_token", {})
    email = decoded_token.get("email", "")
    email = None if not email or email == "" else email
    name = decoded_token.get("name", "")
    
    user_data = await UserService.promote_user(
        user_id=user["uid"],
        email=email,
        display_name=name
    )
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user_data

@router.get("/me/reports", response_model=List[Dict[str, Any]])
async def get_my_reports(limit: int = 10, user=Depends(get_current_user)):
    """
    Get current user's analysis reports
    """
    reports = await UserService.get_user_reports(user["uid"], limit=limit)
    return reports