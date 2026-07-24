"""
One-time helper to get a Strava REFRESH TOKEN.

You only need to run this ONCE per Strava app. It will:
1. Open your browser to Strava's authorization page.
2. Catch the redirect on http://localhost:8000/authorized
3. Exchange the returned code for tokens.
4. Print your refresh token, which you then paste into the Streamlit app
   (or into a .streamlit/secrets.toml file).

Usage:
    python get_refresh_token.py

Requirements:
    pip install requests
"""

import http.server
import urllib.parse
import webbrowser
import requests

REDIRECT_PORT = 8000
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/authorized"
SCOPE = "read_all,activity:read_all"

auth_code = {}


class RedirectHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        if code:
            auth_code["code"] = code
            self.wfile.write(
                b"<html><body><h2>Authorized! You can close this tab and "
                b"go back to your terminal.</h2></body></html>"
            )
        else:
            self.wfile.write(
                b"<html><body><h2>No code received. Check the terminal "
                b"for errors.</h2></body></html>"
            )

    def log_message(self, format, *args):
        pass  # silence default request logging


def main():
    print("=== Strava Refresh Token Setup ===\n")
    client_id = input("Enter your Strava Client ID: ").strip()
    client_secret = input("Enter your Strava Client Secret: ").strip()

    auth_url = (
        "https://www.strava.com/oauth/authorize?"
        + urllib.parse.urlencode(
            {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": REDIRECT_URI,
                "approval_prompt": "force",
                "scope": SCOPE,
            }
        )
    )

    print(f"\nOpening browser to authorize your app...")
    print(f"If it doesn't open automatically, visit this URL:\n{auth_url}\n")
    webbrowser.open(auth_url)

    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), RedirectHandler)
    print(f"Waiting for authorization on http://localhost:{REDIRECT_PORT} ...")
    while "code" not in auth_code:
        server.handle_request()

    code = auth_code["code"]
    print("\nGot authorization code, exchanging for tokens...")

    token_response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
    )
    token_response.raise_for_status()
    tokens = token_response.json()

    print("\n=== SUCCESS ===")
    print(f"Access token  (expires soon):  {tokens['access_token']}")
    print(f"Refresh token (long-lived):    {tokens['refresh_token']}")
    print("\nSave the REFRESH TOKEN somewhere safe - you'll enter it into the")
    print("Streamlit app (or put it in .streamlit/secrets.toml).")
    print("The app will use it to automatically fetch new access tokens.")


if __name__ == "__main__":
    main()
