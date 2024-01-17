# LasthopWeb
Web App for Lasthop music throwbacks 


# Development
- Clone repo: `git clone git@github.com:NickyReid/LasthopWeb.git`
- Create and activate virtual env: `virtualenv venv;  source venv/bin/activate `
- Install requirements: `pip install requirements.txt`
- Set the environment variables (see below)
- Create a firestore database and add credentials to service-acc.json
- Start with ` gunicorn app:app --workers=4 --bind 0.0.0.0:8080 --timeout=180`

#### Environment Variables
```buildoutcfg env vars
SPOTIPY_CLIENT_ID=<spotify_client_id>
SPOTIPY_CLIENT_SECRET=<spotify_client_secret>
SESSION_SECRET_KEY=<session_secret_key>
HOST=http://0.0.0.0:8080
```

