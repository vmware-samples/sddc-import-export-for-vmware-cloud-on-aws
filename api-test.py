import requests
import json

refreshToken = ""
orgID = ""
sddcID = ""
strCSPProdURL = 'https://console.cloud.vmware.com'
strProdURL = 'https://vmc.vmware.com'
proxy_url = ""
proxy_url_short = ""

def getAccessToken(myRefreshToken):
        """ Gets the Access Token using the Refresh Token """
        access_token = ""
        params = {'api_token': myRefreshToken}
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = requests.post(f'{strCSPProdURL}/csp/gateway/am/api/auth/api-tokens/authorize', params=params, headers=headers)
        jsonResponse = response.json()
        try:
            access_token = jsonResponse['access_token']
        except:
            access_token = ""
        return access_token

def getNSXTproxy():
        """ Gets the Reverse Proxy URL """
        myHeader = {'csp-auth-token': access_token}
        myURL = "{}/vmc/api/orgs/{}/sddcs/{}".format(strProdURL, orgID, sddcID)
        response = requests.get(myURL, headers=myHeader)
        json_response = response.json()
        try:
            proxy_url = json_response['resource_config']['nsx_api_public_endpoint_url']
        except:
            proxy_url = ""
            print("Unable to get NSX-T proxy URL. API response:")
            print(json_response)
        return proxy_url

def invokeVMCGET(url: str) -> requests.Response:
    """Invokes a VMC On AWS GET request"""
    myHeader = {'csp-auth-token': access_token}
    try:
        response = requests.get(url,headers=myHeader)
        if response.status_code != 200:
            lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
            print(lastJSONResponse)
        return response
    except Exception as e:
            lastJSONResponse = e
            return None

def exportSDDCCGWGroups():
        """Exports the CGW groups to a JSON file"""
        myURL = proxy_url + "/policy/api/v1/infra/domains/cgw/groups"
        print(f'Trying to call {myURL}')
        response = invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False
        json_response = response.json()
        cgw_groups = json_response['results']

        # After grabbing an intial set of results, check for presence of a cursor
        while "cursor" in json_response:
            myURL = proxy_url + "/policy/api/v1/infra/domains/cgw/groups?cursor=" + json_response['cursor']
            print(f'Trying to call {myURL}')
            response = invokeVMCGET(myURL)
            if response is None or response.status_code != 200:
                return False
            json_response = response.json()
            cgw_groups.extend(json_response['results'])

        fname = 'api-test-groups-exported.json'
        print('Writing to file')
        with open(fname, 'w') as outfile:
            json.dump(cgw_groups, outfile,indent=4)

        return True

def exportSDDCServices():
    myURL = proxy_url + "/policy/api/v1/infra/services"
    print(f'Trying to call {myURL}')
    response = invokeVMCGET(myURL)
    if response is None or response.status_code != 200:
        return False

    json_response = response.json()
    sddc_services = json_response['results']
    fname = 'api-test-services-exported.json'
    print('Writing to file')
    with open(fname, 'w+') as outfile:
        for service in sddc_services:
            if service["_create_user"]!= "admin" and service["_create_user"]!="admin;admin" and service["_create_user"]!="system":
                json.dump(service, outfile,indent=4)
    return True

access_token = getAccessToken(refreshToken)
proxy_url = getNSXTproxy()
proxy_url_short = proxy_url.replace('/sks-nsxt-manager','')
print(f'Token: {access_token}')
print(f'Proxy URL: {proxy_url}')
print(f'Proxy URL short: {proxy_url_short}')

exportSDDCCGWGroups()
exportSDDCServices()