## API authentication module for VMware Cloud on AWS

################################################################################
### Copyright 2020-2023 VMware, Inc.
### SPDX-License-Identifier: BSD-2-Clause
################################################################################

import json
import requests
import datetime

class VMCAuth:
    def __init__(self, strCSPProdURL: str):
        self.access_token = None
        self.access_token_expiration = None
        self.activeRefreshToken = None
        self.strCSPProdURL = strCSPProdURL

    def getAccessToken(self,myRefreshToken):
        """ Gets the Access Token using the Refresh Token """
        self.activeRefreshToken = myRefreshToken
        params = {'api_token': myRefreshToken}
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        try:
            response = requests.post(f'{self.strCSPProdURL}/csp/gateway/am/api/auth/api-tokens/authorize', params=params, headers=headers)
            jsonResponse = response.json()
            self.access_token = jsonResponse['access_token']
            expires_in = jsonResponse['expires_in']
            expirestime = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
            self.access_token_expiration = expirestime
            print(f'Token expires at {expirestime}')
        except:
            self.access_token = None
            self.access_token_expiration = None
            print(jsonResponse)
        return self.access_token

    def check_access_token_expiration(self) -> None:
        """Retrieve a new access token if it is near expiration"""
        if self.access_token_expiration is not None:
            time_to_expire = self.access_token_expiration - datetime.datetime.now()
            if time_to_expire.total_seconds() <= 100:
                print('Access token expired, attempting to refresh...')
                self.getAccessToken(self.activeRefreshToken)