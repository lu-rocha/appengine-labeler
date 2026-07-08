import google.auth
from googleapiclient.discovery import build


PROJECT_ID = "tbx-lucimara-silva"
SERVICE_ID = "default"


credentials, _ = google.auth.default()

appengine = build(
    "appengine",
    "v1",
    credentials=credentials
)

service = (
    appengine
    .apps()
    .services()
    .get(
        appsId=PROJECT_ID,
        servicesId=SERVICE_ID
    )
    .execute()
)

print(service)