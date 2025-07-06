def has_active_subscription(user_data: dict) -> bool:
    """
    Check if user has an active subscription (starter or developer)
    
    Args:
        user_data: User data dictionary from Firestore
        
    Returns:
        bool: True if user has active subscription, False otherwise
    """
    if not user_data:
        return False
        
    subscription = user_data.get("subscription")
    if not subscription:
        return False
        
    return (
        subscription.get("status") == "active" and 
        subscription.get("type") in ["starter", "developer"]
    ) 