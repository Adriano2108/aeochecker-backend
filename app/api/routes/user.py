from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.user import UserResponse
from app.api.deps import get_current_user
from app.services.user import UserService
from typing import Dict, Any, List
from app.schemas.analysis import ReportSummary

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
            username=name
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
    username = decoded_token.get("username", "")
    
    user_data = await UserService.promote_user(
        user_id=user["uid"],
        email=email,
        username=username
    )
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user_data

@router.get("/me/reports", response_model=List[ReportSummary])
async def get_my_reports(limit: int = 10, offset: int = 0, user=Depends(get_current_user)):
    """
    Get current user's analysis reports with pagination
    """
    reports = await UserService.get_user_reports(user["uid"], limit=limit, offset=offset)
    return reports

@router.delete("/{uid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_specified_user(
    uid: str, 
    current_user=Depends(get_current_user)
):
    """
    Delete user - used for cleanup after anonymous account upgrading
    """
    if uid == current_user["uid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account."
        )
    
    user_to_delete = await UserService.get_user_data(uid)
    if not user_to_delete or user_to_delete.get("persistent", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete this user. Only anonymous users can be deleted."
        )
    
    #TODO: Add additional checks here:
    # 1. Limit how many deletions a user can perform
    # 2. Logic to check if this is suspicious or abusive deletion
    
    success = await UserService.delete_user(uid)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete user"
        )
    
    return None