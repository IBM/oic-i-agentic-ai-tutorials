import requests

from requests_oauthlib import OAuth1

ACCOUNT_REALM = "3898579_SB1" 

CONSUMER_KEY = "b8a9276b3984647859a3a610010b0ca2af699a9aa1693bee6aad349902ad2012"

CONSUMER_SECRET = "bb7d1bad3b5c08ed7cff0e2a1ee669776fa1582b1eb3adc785f4ce1f660141f2"

TOKEN_ID = "07bb722dba45d462020a66f896429a885dc528acd1e51ec6b983f7335539c601"

TOKEN_SECRET = "91e6c190fd2ec2e364067ba22962c21808f50e12fc5929f875cccff4975a69cf"

base_url = "https://3898579-sb1.suitetalk.api.netsuite.com/services/rest/record/v1/customer"

auth = OAuth1(

    CONSUMER_KEY,

    CONSUMER_SECRET,

    TOKEN_ID,

    TOKEN_SECRET,

    realm=ACCOUNT_REALM,

)

headers = {

    "Content-Type": "application/json"

}

try:

    response = requests.get(base_url, auth=auth, headers=headers)

    print(f"Status: {response.status_code}")

    print(f"Response: {response.text[:500]}")

except Exception as e:

    print(f"Exception: {e}")
 
import requests

from requests_oauthlib import OAuth1

import oauthlib.oauth1

ACCOUNT_REALM  = "3898579_SB1" 

CONSUMER_KEY = "b8a9276b3984647859a3a610010b0ca2af699a9aa1693bee6aad349902ad2012"

CONSUMER_SECRET = "bb7d1bad3b5c08ed7cff0e2a1ee669776fa1582b1eb3adc785f4ce1f660141f2"

TOKEN_ID = "07bb722dba45d462020a66f896429a885dc528acd1e51ec6b983f7335539c601"

TOKEN_SECRET = "91e6c190fd2ec2e364067ba22962c21808f50e12fc5929f875cccff4975a69cf"

auth = OAuth1(

    CONSUMER_KEY,

    client_secret=CONSUMER_SECRET,

    resource_owner_key=TOKEN_ID,

    resource_owner_secret=TOKEN_SECRET,

    signature_method=oauthlib.oauth1.SIGNATURE_HMAC_SHA256,

    realm=ACCOUNT_REALM,

)

headers = {"Content-Type": "application/json"}

TEST_URL = "https://3898579-sb1.suitetalk.api.netsuite.com/services/rest/record/v1/customer?limit=1"

print("🔄 Testing login...")

try:

    resp = requests.get(TEST_URL, auth=auth, headers=headers)

    if resp.status_code == 200:

        print(" Login successful!")

    elif resp.status_code == 403:

        print(" Forbidden – role missing REST permissions")

        print(resp.text)

    elif resp.status_code == 401:

        print(" Unauthorized – tokens or signature incorrect")

        print(resp.text)

    else:

        print(f"❌ Login failed: {resp.status_code}")

        print(resp.text)

except Exception as e:

    print("❌ Exception during login:", str(e))
 
