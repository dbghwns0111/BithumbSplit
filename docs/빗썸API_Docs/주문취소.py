# Python 3
# pip3 installl pyJwt
import jwt 
import uuid
import hashlib
import time
from urllib.parse import urlencode
import requests

accessKey = '발급받은 API KEY'
secretKey = '발급받은 SECRET KEY'
apiUrl = 'https://api.bithumb.com'

# Set API parameters
param = dict( uuid='C0917000000000070001' )

# Generate access token
query = urlencode(param).encode()
hash = hashlib.sha512()
hash.update(query)
query_hash = hash.hexdigest()
payload = {
    'access_key': accessKey,
    'nonce': str(uuid.uuid4()),
    'timestamp': round(time.time() * 1000), 
    'query_hash': query_hash,
    'query_hash_alg': 'SHA512',
}   
jwt_token = jwt.encode(payload, secretKey)
authorization_token = 'Bearer {}'.format(jwt_token)
headers = {
  'Authorization': authorization_token
}

try:
    # Call API
    response = requests.delete(apiUrl + '/v1/order', params=param, headers=headers)
    # handle to success or fail
    print(response.status_code)
    print(response.json())
except Exception as err:
    # handle exception
    print(err)
