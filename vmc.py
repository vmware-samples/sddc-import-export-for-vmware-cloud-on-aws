# VMC connection module
################################################################################
### Copyright 2020-2022 VMware, Inc.
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

class EdgeInterfaceStats():
    """T0 interface statistics"""
    def __init__(self, interface_id: str) -> None:
        self.rx_total_bytes = 0
        self.rx_total_packets = 0
        self.rx_dropped_packets = 0
        self.tx_total_bytes = 0
        self.tx_total_packets = 0
        self.tx_dropped_packets = 0
        self.interface_id = None
        self.last_update_timestamp = None

class VMCConnection():
    """Connection to VMware Cloud on AWS"""
    def __init__(self, org_id: str, sddc_id: str, refresh_token: str = None,oauth_id: str = None, oauth_secret: str = None, ProdURL: str = 'https://vmc.vmware.com', CSPProdURL: str = 'https://console.cloud.vmware.com') -> None:
        # If refresh token gets passed, we use it for authentication
        print(f'refresh:{refresh_token}')
        print(f'oi:{oauth_id}, os: {oauth_secret}' )
        if refresh_token is not None:
            self.auth_mode = 'token'
            self.refresh_token = refresh_token
        # If refresh token is null, both oauth_id and oauth_secret need to be passed 
        elif oauth_id is not None and oauth_secret is not None:
            self.auth_mode = 'oauth'
            self.oauth_id = oauth_id
            self.oauth_secret = oauth_secret
        else:
            raise Exception("refresh_token or oauth credentials are required.")


        self.initVars(ProdURL, CSPProdURL, org_id, sddc_id)

        self.getAccessToken()
        if self.access_token is None:
            raise Exception("Could not load access token")

        if sddc_id is None:
            print('No SDDC ID found, call getNSXTproxy before continuing')
        else:
            self.getNSXTproxy()

    def initVars(self, ProdURL: str, CSPProdURL: str, org_id: str, sddc_id: str) -> None:
        """Initialize the common variables between both refresh token and OAuth"""
        self.access_token = None
        self.access_token_expiration = None
        self.ProdURL = ProdURL
        self.CSPProdURL = CSPProdURL
        self.lastJSONResponse = None
        self.org_id = org_id
        self.sddc_id = sddc_id
        self.proxy_url = None
        self.proxy_url_short = None

    def getAccessToken(self,myRefreshToken: str = None) -> str:
        """ Gets the Access Token using the Refresh Token """
        if self.auth_mode == 'token':
            if myRefreshToken is None:
                myRefreshToken = self.refresh_token

            if self.org_id is None:
                print('No org ID found.')
                return None

            params = {'api_token': myRefreshToken}
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            response = requests.post(f'{self.CSPProdURL}/csp/gateway/am/api/auth/api-tokens/authorize', params=params, headers=headers)
            if response.status_code != 200:
                print (f'Token Auth API Call Status {response.status_code}, text:{response.text}')
                return None

            jsonResponse = response.json()
        elif self.auth_mode == "oauth":
            params = {'grant_type': 'client_credentials'}
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            response = requests.post(f'{self.CSPProdURL}/csp/gateway/am/api/auth/authorize', params=params,auth=(self.oauth_id, self.oauth_secret), headers=headers)
            if response.status_code != 200:
                print (f'OAUth API Call Status {response.status_code}, text:{response.text}')
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
    def __init__(self, org_id: str, sddc_id: str, refresh_token: str = None, oauth_id: str = None, oauth_secret: str = None) -> None:
        self.org_id = org_id
        self.sddc_id = sddc_id
        self.vmcconn = VMCConnection(org_id, sddc_id, refresh_token=refresh_token, oauth_id=oauth_id, oauth_secret=oauth_secret)
        self.edge_interface_stats = {}
        self.debug_mode = False

    def get_sddc_cgw_rule(self, rule_id: str) -> JSONResponse:
        """Retrieve a single CGW rule"""
        myURL = (self.vmcconn.proxy_url + f'/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules/{rule_id}')
        response = self.vmcconn.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return JSONResponse(False,None, self.vmcconn.lastJSONResponse)

        json_response = response.json()
        return JSONResponse(True, json_response)

    def get_sddc_cgw_rules(self) -> JSONResponse:
        """Retrieve all CGW firewall rules"""
        myURL = (self.vmcconn.proxy_url + f'/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules')
        response = self.vmcconn.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return JSONResponse(False,None, self.vmcconn.lastJSONResponse)

        json_response = response.json()
        return JSONResponse(True, json_response)

    def get_sddc_cgw_rules(self) -> JSONResponse:
        """Retrieve all CGW firewall rules"""
        myURL = (self.vmcconn.proxy_url + f'/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules')
        response = self.vmcconn.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return JSONResponse(False,None, self.vmcconn.lastJSONResponse)

        json_response = response.json()
        return JSONResponse(True, json_response)

    def get_t0_interfaces(self) -> JSONResponse:
        """Retrieve all T0 interfaces"""
        myURL = (self.vmcconn.proxy_url + f'/policy/api/v1/infra/tier-0s/vmc/locale-services/default/interfaces')
        response = self.vmcconn.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return JSONResponse(False,None, self.vmcconn.lastJSONResponse)

        json_response = response.json()
        return JSONResponse(True, json_response)

    def get_edge_clusters(self) -> JSONResponse:
        """Retrieve all edge clusters"""
        myURL = (self.vmcconn.proxy_url + '/policy/api/v1/infra/sites/default/enforcement-points/vmc-enforcementpoint/edge-clusters')
        response = self.vmcconn.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return JSONResponse(False,None, self.vmcconn.lastJSONResponse)

        json_response = response.json()
        return JSONResponse(True, json_response)

    def get_edge_cluster_nodes(self, edgeClusterID: str) -> JSONResponse:
        """Retrieve all cluster nodes in edgeClusterID"""
        myURL = (self.vmcconn.proxy_url + f'/policy/api/v1/infra/sites/default/enforcement-points/vmc-enforcementpoint/edge-clusters/{edgeClusterID}/edge-nodes')
        response = self.vmcconn.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return JSONResponse(False,None, self.vmcconn.lastJSONResponse)

        json_response = response.json()
        return JSONResponse(True, json_response)

    def get_interface_stats(self, interface: str, edgeNodePath: str) -> JSONResponse:
        """Retrieve stats"""
        myURL  = (self.vmcconn.proxy_url + f'/policy/api/v1/infra/tier-0s/vmc/locale-services/default/interfaces/{interface}/statistics?enforcement_point_path=/infra/sites/default/enforcement-points/vmc-enforcementpoint&edge_path={edgeNodePath}')
        response = self.vmcconn.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return JSONResponse(False,None, self.vmcconn.lastJSONResponse)

        json_response = response.json()
        return JSONResponse(True, json_response)

    def load_interface_counters(self) -> bool:
        interfaces = []
        edgeClusterID = None
        edgeNodes = []

        retval = self.get_t0_interfaces()
        if retval.success:
            for interface in retval.json_body["results"]:
                interfaces.append(interface["id"])
            if self.debug_mode:
                #print(json.dumps(retval.json_body, indent=4))
                print(f'Interfaces: {interfaces}')
        else:
            print("Could not retrieve T0 interface URL. Error:", retval.last_response)
            return False

        retval = self.get_edge_clusters()
        if retval.success:
            edgeClusterID = retval.json_body["results"][0]["id"]

            if self.debug_mode:
                #print(json.dumps(retval.json_body, indent=4))
                print(f'Edge Cluster ID: {edgeClusterID}')
        else:
            print("Could not retrieve edge cluster. Error:", retval.last_response)
            return False

        retval = self.get_edge_cluster_nodes(edgeClusterID)
        if retval.success:
            for edge in retval.json_body["results"]:
                edgeNodes.append(edge["id"])
            if self.debug_mode:
                #print(json.dumps(retval.json_body, indent=4))
                print(f'Edge Node IDs: {edgeNodes}')
        else:
            print("Could not retrieve edge cluster nodes. Error:", retval.last_response)
            return False

        for edge in edgeNodes:
            edgeNodePath = f'/infra/sites/default/enforcement-points/vmc-enforcementpoint/edge-clusters/{edgeClusterID}/edge-nodes/{edge}'
            for interface in interfaces:
                if self.debug_mode:
                    print(f'Edge Node Path: {edgeNodePath}, interface: {interface}')
                retval = self.get_interface_stats(interface, edgeNodePath)
                self.edge_interface_stats[interface] = EdgeInterfaceStats(interface)
                if retval.success:
                    stats_json = retval.json_body["per_node_statistics"][0]
                    self.edge_interface_stats[interface].rx_total_bytes += stats_json["rx"]["total_bytes"]
                    self.edge_interface_stats[interface].rx_total_packets += stats_json["rx"]["total_packets"]
                    self.edge_interface_stats[interface].rx_dropped_packets += stats_json["rx"]["dropped_packets"]
                    self.edge_interface_stats[interface].tx_total_bytes += stats_json["tx"]["total_bytes"]
                    self.edge_interface_stats[interface].tx_total_packets += stats_json["tx"]["total_packets"]
                    self.edge_interface_stats[interface].tx_dropped_packets += stats_json["tx"]["dropped_packets"]
                    self.edge_interface_stats[interface].last_update_timestamp = stats_json["last_update_timestamp"]
                    #print(json.dumps(retval.json_body, indent=4))
                else:
                    print("Could not retrieve T0 interface URL. Error:", retval.last_response)
                    return False

        return True