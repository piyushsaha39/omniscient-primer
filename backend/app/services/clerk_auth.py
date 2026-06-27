import os
import requests
from fastapi import HTTPException, status

CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")

def get_user_google_token(clerk_user_id: str) -> str:
    """
    Fetches the active Google OAuth access token for a specific user from Clerk.
    """
    if not CLERK_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Backend misconfiguration: CLERK_SECRET_KEY missing."
        )

    # Clerk's endpoint to get external account tokens for a user
    # provider is 'oauth_google'
    url = f"https://api.clerk.com/v1/users/{clerk_user_id}/oauth_tokens/oauth_google"
    
    headers = {
        "Authorization": f"Bearer {CLERK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Google account connection not found for this user in Clerk."
            )
        elif response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch OAuth token from Clerk: {response.text}"
            )
            
        data = response.json()
        
        # Clerk returns a list of tokens. We grab the first/most current one.
        if isinstance(data, list) and len(data) > 0:
            token = data[0].get("token")
            if token:
                return token
                
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid Google token found in the Clerk response."
        )

    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Network error verifying credentials with authentication provider: {str(e)}"
        )