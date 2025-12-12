import os
import json
import logging
import requests
import datetime
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class KisAuth:
    """
    Handles authentication with Korea Investment & Securities (KIS) OpenAPI.
    Manages Access Token issuance and auto-refresh.
    """
    def __init__(self, token_file="kis_token_real.json"):
        load_dotenv()
        self.app_key = os.getenv("KIS_APP_KEY")
        self.app_secret = os.getenv("KIS_APP_SECRET")
        self.acc_no = os.getenv("KIS_ACC_NO") 
        self.token_file = token_file
        self.access_token = None
        self.token_expired_at = None
        self.base_url = "https://openapi.koreainvestment.com:9443" # Check utils for base_url logic usually, but default to real for now

        if not self.app_key or not self.app_secret:
            raise ValueError("KIS_APP_KEY and KIS_APP_SECRET must be set in .env")

        self.load_token()

    def get_base_url(self):
        return self.base_url

    def load_token(self):
        """Loads token from local file if it exists and is valid."""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "r") as f:
                    data = json.load(f)
                    expired_str = data.get("expired_at")
                    if expired_str:
                        expired_at = datetime.datetime.strptime(expired_str, "%Y-%m-%d %H:%M:%S")
                        # Buffer time of 10 minutes
                        if datetime.datetime.now() < expired_at - datetime.timedelta(minutes=10):
                            self.access_token = data.get("access_token")
                            self.token_expired_at = expired_at
                            logger.info(f"Loaded valid access token from {self.token_file}")
                            return
            except Exception as e:
                logger.error(f"Failed to load token file: {e}")
        
        # If load failed or expired, issue new token
        self.issue_token()

    def issue_token(self):
        """Issues a new access token from KIS API."""
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        try:
            logger.info("Requesting new access token from KIS...")
            res = requests.post(url, headers=headers, data=json.dumps(body))
            res.raise_for_status()
            data = res.json()
            
            self.access_token = data["access_token"]
            # Expiration is usually 24 hours. The API returns 'access_token_token_expired' (e.g. "2022-08-30 14:00:00")
            # But the response body key might be 'access_token_token_expired' or similar. 
            # Real KIS API returns 'access_token_token_expired' in date format.
            
            expired_str = data.get("access_token_token_expired")
            if expired_str:
                self.token_expired_at = datetime.datetime.strptime(expired_str, "%Y-%m-%d %H:%M:%S")
            else:
                 # Fallback if not provided, assume 24h
                self.token_expired_at = datetime.datetime.now() + datetime.timedelta(hours=24)

            self.save_token()
            logger.info("Successfully issued new access token.")

        except Exception as e:
            logger.error(f"Failed to issue access token: {e}")
            raise

    def save_token(self):
        """Saves current token to file."""
        if not self.access_token or not self.token_expired_at:
            return

        data = {
            "access_token": self.access_token,
            "expired_at": self.token_expired_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(self.token_file, "w") as f:
            json.dump(data, f)
    
    def get_token(self):
        """Returns valid access token, refreshing if necessary."""
        if not self.access_token:
            self.issue_token()
        
        # Check expiration with buffer
        if self.token_expired_at and datetime.datetime.now() >= self.token_expired_at - datetime.timedelta(minutes=10):
            logger.info("Token expired or close to expiration. Refreshing...")
            self.issue_token()
            
        return self.access_token

    def get_header(self, tr_id=None):
        """Constructs standard header for KIS API calls."""
        token = self.get_token()
        header = {
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        if tr_id:
            header["tr_id"] = tr_id
        return header
