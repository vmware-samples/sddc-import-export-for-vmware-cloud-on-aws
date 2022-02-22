# VMC connection module
################################################################################
### Copyright 2020-2021 VMware, Inc.
### SPDX-License-Identifier: BSD-2-Clause
################################################################################
import requests
import json

import datetime

class JSONResponse():
    """A REST API response object """
    def __init__(self, success: bool, json_body: str, last_response: str = None) -> None:
        self.success = success
        self.json_body = json_body
        self.last_response = last_response

class VMCConnection():
    """Connection to VMware Cloud on AWS"""
    def __init__(self, refresh_token: str, org_id: str = None, sddc_id: str = None, ProdURL: str = 'https://vmc.vmware.com', CSPProdURL: str = 'https://console.cloud.vmware.com') -> None:
        self.access_token = None
        self.access_token_expiration = None
        self.CSPProdURL = CSPProdURL
        self.lastJSONResponse = None
        self.org_id = org_id
        self.ProdURL = ProdURL
        self.proxy_url = None
        self.proxy_url_short = None
        self.refresh_token = refresh_token
        self.sddc_id = sddc_id

        self.getAccessToken()

        if sddc_id is None:
            print('No SDDC ID found, call getNSXTproxy before continuing')
        else:
            self.getNSXTproxy()

    def getAccessToken(self,myRefreshToken: str = None) -> str:
        """ Gets the Access Token using the Refresh Token """
        if myRefreshToken is None:
            myRefreshToken = self.refresh_token

        if self.org_id is None:
            print('No org ID found.')
            return None

        params = {'api_token': myRefreshToken}
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = requests.post(f'{self.CSPProdURL}/csp/gateway/am/api/auth/api-tokens/authorize', params=params, headers=headers)
        if response.status_code != 200:
            print (f'API Call Status {response.status_code}, text:{response.text}')
            return None

        jsonResponse = response.json()

        try:
            self.access_token = jsonResponse['access_token']
            expires_in = jsonResponse['expires_in']
            expirestime = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
            self.access_token_expiration = expirestime
            print(f'Token expires at {expirestime}')
        except:
            self.access_token = None
            self.access_token_expiration = None
        return self.access_token

    def getNSXTproxy(self) -> str:
            """ Gets the Reverse Proxy URL """
            if self.access_token is None:
                print('No access token, unable to continue')
                return None

            if self.sddc_id is None:
                print('No SDDC ID, unable to continue')
                return None

            myHeader = {'csp-auth-token': self.access_token}
            myURL = f'{self.ProdURL}/vmc/api/orgs/{self.org_id}/sddcs/{self.sddc_id}'
            response = requests.get(myURL, headers=myHeader)
            if response.status_code != 200:
                print (f'API Call Status {response.status_code}, text:{response.text}')
                return None
            json_response = response.json()
            try:
                self.proxy_url = json_response['resource_config']['nsx_api_public_endpoint_url']
                self.proxy_url_short = self.proxy_url.replace('/sks-nsxt-manager','')
            except:
                self.proxy_url = None
                print("Unable to find NSX-T proxy URL in response. JSON:")
                print(json_response)
            return self.proxy_url

    def check_access_token_expiration(self) -> None:
        """Retrieve a new access token if it is near expiration"""
        time_to_expire = self.access_token_expiration - datetime.datetime.now()
        if time_to_expire.total_seconds() <= 100:
            print('Access token expired, attempting to refresh...')
            self.getAccessToken()

    def invokeVMCGET(self,url: str, header: dict = None) -> requests.Response:
            """Invokes a VMC On AWS GET request"""
            self.check_access_token_expiration()
            myHeader = {'csp-auth-token': self.access_token}
            try:
                response = requests.get(url,headers=myHeader)
                if response.status_code != 200:
                    self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
                return response
            except Exception as e:
                    self.lastJSONResponse = e
                    return None

    def invokeVMCPUT(self,url: str, payload: str, patchMode: bool = False, headers: dict = None)  -> requests.Response:
        self.check_access_token_expiration()
        if headers is None:
            headers = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }

        try:
            if patchMode is False:
                response = requests.patch(url, headers=headers, data=payload)
            else:
                response = requests.post(url, headers=headers, data=payload )

            if response.status_code != 200:
                self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
            return response
        except Exception as e:
            self.lastJSONResponse = e
            return None





class VMCSDDC():
    def __init__(self, refresh_token: str, org_id: str, sddc_id: str) -> None:
        self.org_id = org_id
        self.sddc_id = sddc_id
        self.vmcconn = VMCConnection(refresh_token,org_id, sddc_id);

    def getSDDCCGWRule(self, rule_id: str) -> JSONResponse:
        """Retrieve a single CGW rule"""
        myURL = (self.vmcconn.proxy_url + f'/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules/{rule_id}')
        response = self.vmcconn.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return JSONResponse(False,None, self.vmcconn.lastJSONResponse)

        json_response = response.json()
        return JSONResponse(True, json_response)

    def getSDDCCGWRules(self) -> JSONResponse:
        """Retrieve all CGW firewall rules"""
        myURL = (self.vmcconn.proxy_url + f'/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules')
        response = self.vmcconn.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return JSONResponse(False,None, self.vmcconn.lastJSONResponse)

        json_response = response.json()
        return JSONResponse(True, json_response)

