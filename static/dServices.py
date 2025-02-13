from apiclient import discovery
from Cryptodome.Cipher import AES
from google.oauth2 import service_account

gCredentials = service_account.Credentials.from_service_account_file(
    filename="service_account.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
sheetService = discovery.build(
    serviceName="sheets", version="v4", credentials=gCredentials
).spreadsheets()

cryptService = AES.new("WnFKN1v_gUcgmUVZnjjjGXGwk557zBSO".encode("utf8"), AES.MODE_ECB)
