"""HMAC client for secure communication with the OAuth proxy."""

import hmac
import hashlib
import time
import base64
import json
from typing import Optional, Dict, Any

class HMACClient:
    """Generate HMAC signatures for API requests to the OAuth proxy."""
    
    def __init__(self, api_key: str, hmac_secret: str):
        """Initialize HMAC client.
        
        Args:
            api_key: User's API key
            hmac_secret: Shared secret for HMAC signatures
        """
        self.api_key = api_key
        self.secret = hmac_secret.encode('utf-8')
        
    def generate_signature(
        self,
        method: str,
        path: str,
        body: str = "",
        headers: Optional[Dict[str, str]] = None
    ) -> tuple[str, str]:
        """Generate HMAC-SHA256 signature for a request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path (e.g., /api/v1/shops/123)
            body: Request body (for POST/PUT/PATCH)
            headers: Optional headers to include in signature
            
        Returns:
            Tuple of (signature, timestamp)
        """
        # Current timestamp
        timestamp = str(int(time.time()))
        
        # Build the string to sign
        # Format: METHOD|PATH|TIMESTAMP|API_KEY|BODY|HEADERS
        parts = [
            method.upper(),
            path,
            timestamp,
            self.api_key,
            body
        ]
        
        # Add sorted headers if provided
        if headers:
            # Only include specific security-relevant headers
            security_headers = {
                k: v for k, v in headers.items()
                if k.lower() in ['content-type', 'content-length', 'host']
            }
            if security_headers:
                header_str = json.dumps(security_headers, sort_keys=True)
                parts.append(header_str)
        
        message = '|'.join(parts)
        
        # Calculate HMAC-SHA256
        signature = hmac.new(
            self.secret,
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Return base64-encoded signature and timestamp
        return base64.b64encode(signature).decode('utf-8'), timestamp
    
    def get_headers_with_signature(
        self,
        method: str,
        path: str,
        api_key: str,
        body: str = "",
        additional_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Get headers with HMAC signature for a request.
        
        Args:
            method: HTTP method
            path: Request path
            api_key: User's API key
            body: Request body (if any)
            additional_headers: Additional headers to include
            
        Returns:
            Headers dict with authentication and signature
        """
        signature, timestamp = self.generate_signature(method, path, body)
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-HA-Signature": signature,
            "X-HA-Timestamp": timestamp,
            "Accept": "application/json",
        }
        
        if additional_headers:
            headers.update(additional_headers)
            
        return headers