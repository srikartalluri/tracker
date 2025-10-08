import os, json, uuid, webbrowser
from dotenv import load_dotenv
from flask import Flask, jsonify, request, make_response
from plaid.api import plaid_api
from plaid import Configuration, ApiClient, Environment
# ✅ correct, class imports (not modules)
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest


load_dotenv()

PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
PLAID_SECRET = os.getenv("PLAID_SECRET")
PLAID_ENV = (os.getenv("PLAID_ENV") or "sandbox").lower()
PLAID_REDIRECT_URI = os.getenv("PLAID_REDIRECT_URI")

ENV_MAP = {
    "sandbox": Environment.Sandbox,
    # "development": Environment.Development,
    "production": Environment.Production,
}

config = Configuration(
    host=ENV_MAP[PLAID_ENV],
    api_key={"clientId": PLAID_CLIENT_ID, "secret": PLAID_SECRET},
)
api_client = ApiClient(config)
plaid_client = plaid_api.PlaidApi(api_client)

ACCESS_TOKEN_PATH = "plaid_access_token.json"

app = Flask(__name__)

def save_access_token(token, item_id):
    with open(ACCESS_TOKEN_PATH, "w") as f:
        json.dump({"access_token": token, "item_id": item_id}, f, indent=2)

def shutdown_server():
    from flask import request as flask_request
    func = flask_request.environ.get("werkzeug.server.shutdown")
    if func:
        func()

@app.route("/")
def index():
    # Minimal page that auto-opens Plaid Link
    html = """
<!doctype html>
<html>
<meta charset="utf-8">
<title>Plaid OAuth Connect</title>
<body>
  <p>Opening Plaid Link…</p>
  <pre id="out"></pre>
  <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
  <script>
    async function go() {
      const res = await fetch('/link_token', { method: 'POST' });
      const { link_token } = await res.json();
      const handler = Plaid.create({
        token: link_token,
        onSuccess: async (public_token) => {
          const r = await fetch('/exchange', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ public_token })
          });
          const data = await r.json();
          document.getElementById('out').textContent = JSON.stringify(data, null, 2);
        },
        onExit: (err) => { if (err) console.error(err); }
      });
      handler.open();
    }
    go();
  </script>
</body>
</html>
"""
    return make_response(html, 200)

@app.route("/oauth-redirect")
def oauth_redirect():
    # Re-open Link after Chase OAuth redirect
    html = """
<!doctype html>
<html>
<meta charset="utf-8">
<title>Completing OAuth…</title>
<body>
  <p>Completing OAuth…</p>
  <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
  <script>
    const receivedRedirectUri = window.location.href;
    async function go() {
      const res = await fetch('/link_token', { method: 'POST' });
      const { link_token } = await res.json();
      const handler = Plaid.create({
        token: link_token,
        receivedRedirectUri,
        onSuccess: async (public_token) => {
          await fetch('/exchange', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ public_token })
          });
          document.body.innerHTML = "<p>All set! You can close this tab.</p>";
        }
      });
      handler.open();
    }
    go();
  </script>
</body>
</html>
"""
    return make_response(html, 200)

@app.route("/link_token", methods=["POST"])
def link_token():
    req = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=str(uuid.uuid4())),
        client_name="Local Script",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
        redirect_uri=PLAID_REDIRECT_URI,  # required for Chase OAuth
        transactions={"days_requested": 730},  # optional, but we need recent transactions
    )
    res = plaid_client.link_token_create(req).to_dict()
    return jsonify({"link_token": res["link_token"]})

@app.route("/exchange", methods=["POST"])
def exchange():
    public_token = request.json.get("public_token")
    r = plaid_client.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=public_token)
    ).to_dict()
    access_token = r["access_token"]
    item_id = r["item_id"]
    save_access_token(access_token, item_id)
    print("\n=== ACCESS TOKEN SAVED ===")
    print(access_token)
    print("==========================\n", flush=True)
    # Stop the server so the script exits
    shutdown_server()
    return jsonify({"ok": True, "item_id": item_id})

if __name__ == "__main__":
    url = "http://localhost:5050/"
    print(f"Opening {url} …")
    webbrowser.open(url)
    app.run(port=5050, debug=False, use_reloader=False)
