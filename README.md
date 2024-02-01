# LasthopWeb
Web App for Lasthop music throwbacks 


# Development
- Clone repo: `git clone git@github.com:NickyReid/LasthopWeb.git`
- Create and activate virtual env: `virtualenv venv;  source venv/bin/activate `
- Install requirements: `pip install -r requirements.txt`
- Set the environment variables (see below)
- Start with ` gunicorn app:app --workers=4 --bind 0.0.0.0:8080 --timeout=180`

#### Environment Variables
```buildoutcfg env vars
LAST_FM_API_KEY=<lastfm api key>
SESSION_SECRET_KEY=<session_secret_key>
RECENT_TRACKS_WORKERS=20
```

### Spotify
To use the Spotify playlist function, create an app on the [Spotify For Developers](https://developer.spotify.com/documentation/web-api/concepts/apps) site to get a client ID and client secret. Add your HOST to the redirect URIs on the dashboard and set the following environment variables:
```buildoutcfg env vars
SPOTIPY_CLIENT_ID=<spotify_client_id>
SPOTIPY_CLIENT_SECRET=<spotify_client_secret>
HOST=http://0.0.0.0:8080
SHOPIFY_SEARCH_MAX_CACHE_AGE_HOURS=168
MAX_PLAYLIST_LENGTH=1000
```

#### Firestore Database
If you want to use a Firestore database, add the service account credentials to a service-acc.json file in the root of the project and update the environment variables:

```buildoutcfg env vars
GOOGLE_CLOUD_PROJECT=<your google cloud project id>
FIRESTORE_DB=<the name of the firestore db you are using>
```

#### Google Cloud Monitoring
setting `GOOGLE_CLOUD_PROJECT` will also send metrics to Google Cloud Monitoring if the `ENVIRONMENT` environment variable is set to "prod"
