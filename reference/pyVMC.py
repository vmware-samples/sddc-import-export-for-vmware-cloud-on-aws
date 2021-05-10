#!/usr/bin/env python3
# The shebang above is to tell the shell which interpreter to use. This make the file executable without "python3" in front of it (otherwise I had to use python3 pyvmc.py)
# I also had to change the permissions of the file to make it run. "chmod +x pyVMC.py" did the trick.
# I also added "export PATH="MY/PYVMC/DIRECTORY":$PATH" (otherwise I had to use ./pyvmc.y)
# For git BASH on Windows, you can use something like this #!/C/Users/usr1/AppData/Local/Programs/Python/Python38/python.exe

# Python Client for VMware Cloud on AWS

################################################################################
### Copyright (C) 2019-2020 VMware, Inc.  All rights reserved.
### SPDX-License-Identifier: BSD-2-Clause
################################################################################


"""

Welcome to PyVMC ! 

VMware Cloud on AWS API Documentation is available at: https://code.vmware.com/apis/920/vmware-cloud-on-aws
CSP API documentation is available at https://console.cloud.vmware.com/csp/gateway/api-docs
vCenter API documentation is available at https://code.vmware.com/apis/366/vsphere-automation


You can install python 3.8 from https://www.python.org/downloads/windows/ (Windows) or https://www.python.org/downloads/mac-osx/ (MacOs).

You can install the dependent python packages locally (handy for Lambda) with:
pip3 install requests or pip3 install requests -t . --upgrade
pip3 install configparser or pip3 install configparser -t . --upgrade
pip3 install PTable or pip3 install PTable -t . --upgrade

With git BASH on Windows, you might need to use 'python -m pip install' instead of pip3 install

"""

import requests                         # need this for Get/Post/Delete
import configparser                     # parsing config file
import time
import sys
from prettytable import PrettyTable

config = configparser.ConfigParser()
config.read("./config.ini")
strProdURL      = config.get("vmcConfig", "strProdURL")
strCSPProdURL   = config.get("vmcConfig", "strCSPProdURL")
Refresh_Token   = config.get("vmcConfig", "refresh_Token")
ORG_ID          = config.get("vmcConfig", "org_id")
SDDC_ID         = config.get("vmcConfig", "sddc_id")




class data():
    sddc_name       = ""
    sddc_status     = ""
    sddc_region     = ""
    sddc_cluster    = ""
    sddc_hosts      = 0
    sddc_type       = ""

def getAccessToken(myKey):
    """ Gets the Access Token using the Refresh Token """
    params = {'refresh_token': myKey}
    headers = {'Content-Type': 'application/json'}
    response = requests.post('https://console.cloud.vmware.com/csp/gateway/am/api/auth/api-tokens/authorize', params=params, headers=headers)
    jsonResponse = response.json()
    access_token = jsonResponse['access_token']
    return access_token

def getConnectedAccounts(tenantid, sessiontoken):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = strProdURL + "/vmc/api/orgs/" + tenantid + "/account-link/connected-accounts"
    response = requests.get(myURL, headers=myHeader)
    jsonResponse = response.json()
    orgtable = PrettyTable(['OrgID'])
    orgtable.add_row([tenantid])
    print(str(orgtable))
    table = PrettyTable(['Account Number','id'])
    for i in jsonResponse:
        table.add_row([i['account_number'],i['id']])
    return table

def getCompatibleSubnets(tenantid,sessiontoken,linkedAccountId,region):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = strProdURL + "/vmc/api/orgs/" + tenantid + "/account-link/compatible-subnets"
    params = {'org': tenantid, 'linkedAccountId': linkedAccountId,'region': region}
    response = requests.get(myURL, headers=myHeader,params=params)
    jsonResponse = response.json()
    vpc_map = jsonResponse['vpc_map']
    table = PrettyTable(['vpc','description'])
    subnet_table = PrettyTable(['vpc_id','subnet_id','subnet_cidr_block','name','compatible'])
    for i in vpc_map:
        myvpc = jsonResponse['vpc_map'][i]
        table.add_row([myvpc['vpc_id'],myvpc['description']])
        for j in myvpc['subnets']:
            subnet_table.add_row([j['vpc_id'],j['subnet_id'],j['subnet_cidr_block'],j['name'],j['compatible']])
    print(table)
    return subnet_table

def getSDDCS(tenantid, sessiontoken):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = strProdURL + "/vmc/api/orgs/" + tenantid + "/sddcs"
    response = requests.get(myURL, headers=myHeader)
    jsonResponse = response.json()
    orgtable = PrettyTable(['OrgID'])
    orgtable.add_row([tenantid])
    print(str(orgtable))
    table = PrettyTable(['Name', 'Cloud', 'Status', 'Hosts', 'ID'])
    for i in jsonResponse:
        hostcount = 0
        myURL = strProdURL + "/vmc/api/orgs/" + tenantid + "/sddcs/" + i['id']
        response = requests.get(myURL, headers=myHeader)
        mySDDCs = response.json()
        if mySDDCs['resource_config']:
            hosts = mySDDCs['resource_config']['esx_hosts']
            if hosts:
                for j in hosts:
                    hostcount = hostcount + 1
        table.add_row([i['name'], i['provider'],i['sddc_state'], hostcount, i['id']])
    return table


#-------------------- Show hosts in an SDDC
def getCDChosts(sddcID, tenantid, sessiontoken):

    myHeader = {'csp-auth-token': sessiontoken}
    myURL = strProdURL + "/vmc/api/orgs/" + tenantid + "/sddcs/" + sddcID

    response = requests.get(myURL, headers=myHeader)

    # grab the names of the CDCs
    jsonResponse = response.json()

    # get the vC block (this is a bad hack to get the rest of the host name
    # shown in vC inventory)
    cdcID = jsonResponse['resource_config']['vc_ip']
    cdcID = cdcID.split("vcenter")
    cdcID = cdcID[1]
    cdcID = cdcID.split("/")
    cdcID = cdcID[0]

    # get the hosts block
    hosts = jsonResponse['resource_config']['esx_hosts']
    table = PrettyTable(['Name', 'Status', 'ID'])
    for i in hosts:
        hostName = i['name'] + cdcID
        table.add_row([hostName, i['esx_state'], i['esx_id']])
    print(table)
    return

#-------------------- Display the users in our org
def showORGusers(tenantid, sessiontoken):
    myHeader = {'csp-auth-token': sessiontoken}
    #using @ as our search term...
    myURL = strCSPProdURL + "/csp/gateway/am/api/orgs/" + tenantid + "/users/search?userSearchTerm=%40"
    response = requests.get(myURL, headers=myHeader)
    jsonResponse = response.json()
    if str(response.status_code) != "200":
        print("\nERROR: " + str(jsonResponse))
    else:
        # get the results block
        users = jsonResponse['results']
        table = PrettyTable(['First Name', 'Last Name', 'User Name'])
        for i in users:
            table.add_row([i['user']['firstName'],i['user']['lastName'],i['user']['username']])
        print(table)
    return

def getSDDCVPNInternetIP(proxy_url, sessiontoken):
    """ Gets the Public IP used for VPN by the SDDC """
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    # removing 'sks-nsxt-manager' from proxy url to get correct URL
    myURL = proxy_url_short + "cloud-service/api/v1/infra/sddc-user-config"
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    vpn_internet_IP = json_response['vpn_internet_ips'][0]
    return vpn_internet_IP

def getSDDCState(org_id, sddc_id, sessiontoken):
    """ Gets the overall status of the SDDDC """
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = "{}/vmc/api/orgs/{}/sddcs/{}".format(strProdURL, org_id, sddc_id)
    response = requests.get(myURL, headers=myHeader)
    sddc_state = response.json()
    table = PrettyTable(['Name', 'Id', 'Status', 'Type', 'Region', 'Deployment Type'])
    table.add_row([sddc_state['name'], sddc_state['id'], sddc_state['sddc_state'], sddc_state['sddc_type'], sddc_state['resource_config']['region'], sddc_state['resource_config']['deployment_type']])
    return table

def getNSXTproxy(org_id, sddc_id, sessiontoken):
    """ Gets the Reverse Proxy URL """
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = "{}/vmc/api/orgs/{}/sddcs/{}".format(strProdURL, org_id, sddc_id)
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    proxy_url = json_response['resource_config']['nsx_api_public_endpoint_url']
    return proxy_url

def getSDDCnetworks(proxy_url, sessiontoken):
    """ Gets the SDDC Networks """
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/tier-1s/cgw/segments")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_networks = json_response['results']
    table = PrettyTable(['Name', 'id', 'Type', 'Network', 'Default Gateway'])
    
    for i in sddc_networks:
        if ( i['type'] == "DISCONNECTED"):
            table.add_row([i['display_name'], i['id'], i['type'],"-", "-"])
        else: 
            table.add_row([i['display_name'], i['id'], i['type'], i['subnets'][0]['network'], i['subnets'][0]['gateway_address']])
    return table

def newSDDCnetworks(proxy_url, sessiontoken, display_name, gateway_address, dhcp_range, domain_name, routing_type):
    """ Creates a new SDDC Network. L2 VPN networks are not currently supported. """
    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/tier-1s/cgw/segments/" + display_name)
    # print(myURL)
    if routing_type == "DISCONNECTED" :
        json_data = {
                "subnets":[{"gateway_address":gateway_address}],
                "type":routing_type,
                "display_name":display_name,
                "advanced_config":{"connectivity":"OFF"},
                "id":display_name
                }
        response = requests.put(myURL, headers=myHeader, json=json_data)
        json_response_status_code = response.status_code
        if json_response_status_code == 200 :
            print("The following network has been created:")
            table = PrettyTable(['Name', 'Gateway', 'Routing Type'])
            table.add_row([display_name, gateway_address, routing_type])
            return table
        else :
            print("There was an error. Try again.")
            return
    else:
        if dhcp_range == "none" :
            json_data = {
                "subnets":[{"gateway_address":gateway_address}],
                "type":routing_type,
                "display_name":display_name,
                "advanced_config":{"connectivity":"ON"},
                "id":display_name
                }
            response = requests.put(myURL, headers=myHeader, json=json_data)
            json_response_status_code = response.status_code
            if json_response_status_code == 200 :
                print("The following network has been created:")
                table = PrettyTable(['Name', 'Gateway', 'Routing Type'])
                table.add_row([display_name, gateway_address, routing_type])
                return table
            else :
                print("There was an error. Try again.")
                return
        else :
            json_data = {
                "subnets":[{"dhcp_ranges":[dhcp_range],
                "gateway_address":gateway_address}],
                "type":routing_type,
                "display_name":display_name,
                "domain_name":domain_name,
                "advanced_config":{"connectivity":"ON"},
                "id":display_name
                }
            response = requests.put(myURL, headers=myHeader, json=json_data)
            json_response_status_code = response.status_code
            if json_response_status_code == 200 :
                print("The following network has been created:")
                table = PrettyTable(['Name', 'Gateway', 'DHCP', 'Domain Name', 'Routing Type'])
                table.add_row([display_name, gateway_address, dhcp_range, domain_name, routing_type])
                return table
            else :
                print("There was an error. Try again.")
                return

def removeSDDCNetworks(proxy_url, sessiontoken, network_id):
    """ Remove an SDDC Network """
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/tier-1s/cgw/segments/" + network_id)
    response = requests.delete(myURL, headers=myHeader)
    json_response = response.status_code
    # print(json_response)
    # Unfortunately, the response status code is always 200 whether or not we delete an existing or non-existing network segment.
    if json_response == 200 :
        print("The network " + network_id + " has been deleted")
    else :
        print("There was an error. Try again.")
    return

def getSDDCNAT(proxy_url, sessiontoken):
    """ Gets the SDDC Nat Rules """
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/tier-1s/cgw/nat/USER/nat-rules")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    json_response_status_code = response.status_code
    if json_response_status_code == 200:
        sddc_NAT = json_response['results']
        table = PrettyTable(['ID', 'Name', 'Public IP', 'Ports', 'Internal IP', 'Enabled?'])
        for i in sddc_NAT:
            if 'destination_network' in i:
                table.add_row([i['id'], i['display_name'], i['destination_network'], i['translated_ports'], i['translated_network'], i['enabled']])
            else:
                table.add_row([i['id'], i['display_name'], i['translated_network'], "any", i['source_network'], i['enabled']])
        return table
    else:
        print("There was an issue. Try again.")
        return

def getSDDCNATStatistics(proxy_url, sessiontoken, nat_id):
    ### Displays stats for a specific NAT rule. Note the results are a table with 2 entries.  ###
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/tier-1s/cgw/nat/USER/nat-rules/" + nat_id + "/statistics" )
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    json_response = response.json()
    json_response_status_code = response.status_code
    if json_response_status_code == 200:
        sddc_NAT_stats = json_response['results'][0]['rule_statistics']
        table = PrettyTable(['NAT Rule', 'Active Sessions', 'Total Bytes', 'Total Packets'])
        for i in sddc_NAT_stats:
            #  For some reason, the API returns an entry with null values and one with actual data. So I am removing this entry. 
            if (i['active_sessions'] == 0) and (i['total_bytes'] == 0) and (i['total_packets'] == 0):
                # What this code does is simply check if all entries are empty and skip (pass below) before writing the stats.
                pass
            else:
                table.add_row([nat_id, i['active_sessions'], i['total_bytes'], i['total_packets']])
        return table
    else:
        print("There was an issue.")
        return

def newSDDCNAT(proxy_url, sessiontoken, display_name, action, translated_network, source_network, service, translated_port, logging, status):
    """ Creates a new NAT rule """
    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/tier-1s/cgw/nat/USER/nat-rules/" + display_name)
    if action == "any" or action == "REFLEXIVE":
        json_data = {
        "action": "REFLEXIVE",
        "translated_network": translated_network,
        "source_network": source_network,
        "sequence_number": 0,
        "logging": logging,
        "enabled": status,
        "scope":["/infra/labels/cgw-public"],
        "firewall_match":"MATCH_INTERNAL_ADDRESS",
        "id": display_name}
        response = requests.put(myURL, headers=myHeader, json=json_data)
        json_response_status_code = response.status_code
        return json_response_status_code
    else:
        json_data = {
        "action": "DNAT",
        "destination_network": translated_network,
        "translated_network": source_network,
        "translated_ports": translated_port,
        "service":("/infra/services/"+service),
        "sequence_number": 0,
        "logging": logging,
        "enabled": status,
        "scope":["/infra/labels/cgw-public"],
        "firewall_match":"MATCH_INTERNAL_ADDRESS",
        "id": display_name}
        response = requests.put(myURL, headers=myHeader, json=json_data)
        json_response_status_code = response.status_code
        return json_response_status_code

def removeSDDCNAT(proxy_url, sessiontoken, id):
    """ Remove a NAT rule """
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/tier-1s/cgw/nat/USER/nat-rules/" + id)
    response = requests.delete(myURL, headers=myHeader)
    return response

def getSDDCVPN(proxy_url, sessiontoken):
    """ Gets the configured Site-to-Site VPN """
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/tier-0s/vmc/locale-services/default/ipsec-vpn-services/default/sessions")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    json_response_status_code = response.status_code
    if json_response_status_code == 200:
        sddc_VPN = json_response['results']
        table = PrettyTable(['Name', 'ID', 'Local Address', 'Remote Address'])
        for i in sddc_VPN:
            table.add_row([i['display_name'], i['id'], i['local_endpoint_path'].strip("/infra/tier-0s/vmc/locale-services/default/ipsec-vpn-services/default/local-endpoints/"), i['peer_address']])
        return table
    else:
        print("There was an issue.")
        return

def getSDDCVPNIpsecProfiles(proxy_url, sessiontoken):
    """ Gets the IPSecProfiles """
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/ipsec-vpn-ike-profiles")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_VPN_ipsec_profiles = json_response['results']
    table = PrettyTable(['Name', 'ID', 'IKE Version', 'Digest', 'DH Group', 'Encryption'])
    for i in sddc_VPN_ipsec_profiles:
        table.add_row([i['display_name'], i['id'], i['ike_version'], i['digest_algorithms'], i['dh_groups'], i['encryption_algorithms']])
    return table

def getSDDCVPNIpsecTunnelProfiles(proxy_url, sessiontoken):
    """ Gets the IPSec tunnel Profiles """
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/ipsec-vpn-tunnel-profiles")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_VPN_ipsec_tunnel_profiles = json_response['results']
    table = PrettyTable(['Name', 'ID', 'Digest', 'DH Group', 'Encryption'])
    for i in sddc_VPN_ipsec_tunnel_profiles:
        table.add_row([i['display_name'], i['id'], i['digest_algorithms'], i['dh_groups'], i['encryption_algorithms']])
    return table

def getSDDCVPNIpsecEndpoints(proxy_url, sessiontoken):
    """ Gets the IPSec Local Endpoints """
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/tier-0s/vmc/locale-services/default/ipsec-vpn-services/default/local-endpoints")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_VPN_ipsec_endpoints = json_response['results']
    table = PrettyTable(['Name', 'ID', 'Address'])
    for i in sddc_VPN_ipsec_endpoints:
        table.add_row([i['display_name'], i['id'], i['local_address']])
    return table

def getSDDCCGWRule(proxy_url, sessiontoken):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_CGWrules = json_response['results']
    table = PrettyTable(['id', 'Name','Source','Destination', 'Action', 'Applied To', 'Sequence Number'])
    for i in sddc_CGWrules:
        # a, b and c are used to strip the infra/domain/cgw terms from the strings for clarity.
        a = i['source_groups']
        a = [z.replace('/infra/domains/cgw/groups/','') for z in a]
        a = [z.replace('/infra/tier-0s/vmc/groups/','') for z in a]
        b= i['destination_groups']
        b = [z.replace('/infra/domains/cgw/groups/','') for z in b]
        b = [z.replace('/infra/tier-0s/vmc/groups/','') for z in b]
        c= i['scope']
        c = [z.replace('/infra/labels/cgw-','') for z in c]
        table.add_row([i['id'], i['display_name'], a, b, i['action'], c, i['sequence_number']])
    return table

def getSDDCMGWRule(proxy_url, sessiontoken):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/domains/mgw/gateway-policies/default/rules")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_MGWrules = json_response['results']
    table = PrettyTable(['ID', 'Name', 'Source', 'Destination', 'Services', 'Action', 'Sequence Number'])
    for i in sddc_MGWrules:
        # a and b are used to strip the infra/domain/mgw terms from the strings for clarity.
        a = i['source_groups']
        a = [z.replace('/infra/domains/mgw/groups/','') for z in a]
        b= i['destination_groups']
        b = [z.replace('/infra/domains/mgw/groups/','') for z in b]
        c = i['services']
        c = [z.replace('/infra/services/','') for z in c]
        table.add_row([i['id'], i['display_name'], a, b, c, i['action'], i['sequence_number']])
    return table

def getSDDCDFWSection(proxy_url, sessiontoken):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/domains/cgw/security-policies/")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_DFWsection = json_response['results']
    table = PrettyTable(['id', 'Name','Category', 'Sequence Number'])
    for i in sddc_DFWsection:
        table.add_row([i['id'], i['display_name'], i['category'], i['sequence_number']])
    return table

def newSDDCDFWSection(proxy_url, sessiontoken, display_name, category):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/domains/cgw/security-policies/" + display_name)
    json_data = {
    "resource_type":"SecurityPolicy",
    "display_name": display_name,
    "id": display_name,
    "category": category,
    }
    response = requests.put(myURL, headers=myHeader, json=json_data)
    json_response_status_code = response.status_code
    return json_response_status_code

def removeSDDCDFWSection(proxy_url, sessiontoken, section_id):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/domains/cgw/security-policies/" + section_id)
    response = requests.delete(myURL, headers=myHeader)
    json_response_status_code = response.status_code
    return json_response_status_code

def getSDDCDFWRule(proxy_url, sessiontoken, section):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/domains/cgw/security-policies/" + section + "/rules")
    response = requests.get(myURL, headers=myHeader)
    json_response_status_code = response.status_code
    if json_response_status_code != 200:
        print("No section found.")
    else:
        json_response = response.json()
        sddc_DFWrules = json_response['results']
        table = PrettyTable(['ID', 'Name', 'Source', 'Destination', 'Services', 'Action', 'Sequence Number'])
        for i in sddc_DFWrules:
            # a and b are used to strip the infra/domain/mgw terms from the strings for clarity.
            a = i['source_groups']
            a = [z.replace('/infra/domains/cgw/groups/','') for z in a]
            a = [z.replace('/infra/tier-0s/vmc/groups/','') for z in a]
            b= i['destination_groups']
            b = [z.replace('/infra/domains/cgw/groups/','') for z in b]
            b = [z.replace('/infra/tier-0s/vmc/groups/','') for z in b]
            c = i['services']
            c = [z.replace('/infra/services/','') for z in c]
            table.add_row([i['id'], i['display_name'], a, b, c, i['action'], i['sequence_number']])
        return table

def newSDDCDFWRule(proxy_url, sessiontoken, display_name, source_groups, destination_groups, services, action, section, sequence_number):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/domains/cgw/security-policies/" + section + "/rules/" + display_name)
    json_data = {
    "action": action,
    "destination_groups": destination_groups,
    "direction": "IN_OUT",
    "disabled": False,
    "display_name": display_name,
    "id": display_name,
    "ip_protocol": "IPV4_IPV6",
    "logged": False,
    "profiles": [ "ANY" ],
    "resource_type": "Rule",
    "services": services,
    "source_groups": source_groups,
    "sequence_number": sequence_number
    }
    response = requests.put(myURL, headers=myHeader, json=json_data)
    json_response_status_code = response.status_code
    return json_response_status_code

def removeSDDCDFWRule(proxy_url, sessiontoken, section, rule_id):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/domains/cgw/security-policies/" + section + "/rules/" + rule_id)
    response = requests.delete(myURL, headers=myHeader)
    json_response_status_code = response.status_code
    return json_response_status_code

def newSDDCCGWRule(proxy_url, sessiontoken, display_name, source_groups, destination_groups, services, action, scope, sequence_number):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules/" + display_name)
    json_data = {
    "action": action,
    "destination_groups": destination_groups,
    "direction": "IN_OUT",
    "disabled": False,
    "display_name": display_name,
    "id": display_name,
    "ip_protocol": "IPV4_IPV6",
    "logged": False,
    "profiles": [ "ANY" ],
    "resource_type": "Rule",
    "scope": scope,
    "services": services,
    "source_groups": source_groups,
    "sequence_number": sequence_number
    }
    response = requests.put(myURL, headers=myHeader, json=json_data)
    json_response_status_code = response.status_code
    return json_response_status_code

def removeSDDCCGWRule(proxy_url, sessiontoken, rule_id):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules/" + rule_id)
    response = requests.delete(myURL, headers=myHeader)
    json_response_status_code = response.status_code
    return json_response_status_code


def newSDDCMGWRule(proxy_url, sessiontoken, display_name, source_groups, destination_groups, services, action, sequence_number):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/domains/mgw/gateway-policies/default/rules/" + display_name)
    json_data = {
    "action": action,
    "destination_groups": destination_groups,
    "direction": "IN_OUT",
    "disabled": False,
    "display_name": display_name,
    "id": display_name,
    "ip_protocol": "IPV4_IPV6",
    "logged": False,
    "profiles": [ "ANY" ],
    "resource_type": "Rule",
    "scope": ["/infra/labels/mgw"],
    "services": services,
    "source_groups": source_groups,
    "sequence_number": sequence_number
    }
    response = requests.put(myURL, headers=myHeader, json=json_data)
    json_response_status_code = response.status_code
    return json_response_status_code

def removeSDDCMGWRule(proxy_url, sessiontoken, rule_id):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/domains/mgw/gateway-policies/default/rules/" + rule_id)
    response = requests.delete(myURL, headers=myHeader)
    json_response_status_code = response.status_code
    return json_response_status_code


def getSDDCVPNSTATS(proxy_url, sessiontoken, tunnelID):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/policy/api/v1/infra/tier-0s/vmc/locale-services/default/ipsec-vpn-services/default/sessions/" + tunnelID + "/statistics")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_VPN_statistics = json_response['results'][0]['policy_statistics'][0]['tunnel_statistics']
    table = PrettyTable(['Status', 'Packets In', 'Packets Out'])
    for i in sddc_VPN_statistics:
        table.add_row([i['tunnel_status'], i['packets_in'], i['packets_out']])
    return table

def getSDDCPublicIP(proxy_url, sessiontoken):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/cloud-service/api/v1/infra/public-ips")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_public_ips = json_response['results']
    table = PrettyTable(['IP', 'id', 'Notes'])
    for i in sddc_public_ips:
        table.add_row([i['ip'], i['id'], i['display_name']])
    return table

def setSDDCPublicIP(proxy_url, sessiontoken, notes, ip_id):
    """ Update the description of an existing  public IP for compute workloads."""
    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/cloud-service/api/v1/infra/public-ips/" + ip_id)
    json_data = {
    "display_name" : notes
    }
    response = requests.put(myURL, headers=myHeader, json=json_data)
    json_response_status_code = response.status_code
    return json_response_status_code

def newSDDCPublicIP(proxy_url, sessiontoken, notes):
    """ Gets a new public IP for compute workloads. Requires a description to be added to the public IP."""
    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    myURL = (proxy_url_short + "cloud-service/api/v1/infra/public-ips/" + notes)
    json_data = {
    "display_name" : notes
    }
    response = requests.put(myURL, headers=myHeader, json=json_data)
    json_response_status_code = response.status_code
    return json_response_status_code

def removeSDDCPublicIP(proxy_url, sessiontoken, ip_id):
    """ Removes a public IP. """
    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/cloud-service/api/v1/infra/public-ips/" + ip_id)
    response = requests.delete(myURL, headers=myHeader)
    json_response_status_code = response.status_code
    return json_response_status_code


def getSDDCMTU(proxy_url,sessiontoken):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/cloud-service/api/v1/infra/external/config")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_MTU = json_response['intranet_mtu']
    return sddc_MTU

def setSDDCMTU(proxy_url,sessiontoken,mtu):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/cloud-service/api/v1/infra/external/config")
    json_data = {
    "intranet_mtu" : mtu
    }
    response = requests.put(myURL, headers=myHeader, json=json_data)
    json_response_status_code = response.status_code
    return json_response_status_code

def getSDDCShadowAccount(proxy_url,sessiontoken):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/cloud-service/api/v1/infra/accounts")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_shadow_account = json_response['shadow_account']
    return sddc_shadow_account

def getSDDCBGPAS(proxy_url,sessiontoken):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/cloud-service/api/v1/infra/direct-connect/bgp")
    response = requests.get(myURL, headers=myHeader)
    SDDC_BGP = response.json()
    SDDC_BGP_AS = SDDC_BGP['local_as_num']
    return SDDC_BGP_AS

def setSDDCBGPAS(proxy_url,sessiontoken,asn):
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    # removing 'sks-nsxt-manager' from proxy url to get correct URL
    myURL = (proxy_url_short + "cloud-service/api/v1/infra/direct-connect/bgp")
    json_data = {
    "local_as_num": asn
    }
    response = requests.patch(myURL, headers=myHeader, json=json_data)
    json_response_status_code = response.status_code
    return json_response_status_code
    
def getSDDCBGPVPN(proxy_url,sessiontoken):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/cloud-service/api/v1/infra/direct-connect/bgp")
    response = requests.get(myURL, headers=myHeader)
    SDDC_BGP = response.json()
    SDDC_BGP_VPN = SDDC_BGP['route_preference']
    
    if SDDC_BGP_VPN == "VPN_PREFERRED_OVER_DIRECT_CONNECT":
        return "The preferred path is over VPN, with Direct Connect as a back-up."
    else:
        return "The preferred path is over Direct Connect, with VPN as a back-up."


def getSDDCConnectedVPC(proxy_url,sessiontoken):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/cloud-service/api/v1/infra/linked-vpcs")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_connected_vpc = json_response['results'][0]
    mySecondURL = (proxy_url + "/cloud-service/api/v1/infra/linked-vpcs/" + sddc_connected_vpc['linked_vpc_id'] + "/connected-services")
    response_second = requests.get(mySecondURL, headers=myHeader)
    sddc_connected_vpc_services = response_second.json()
    table = PrettyTable(['Customer-Owned Account', 'Connected VPC ID', 'Subnet', 'Availability Zone', 'ENI', 'Service Access'])
    table.add_row([sddc_connected_vpc['linked_account'], sddc_connected_vpc['linked_vpc_id'], sddc_connected_vpc['linked_vpc_subnets'][0]['cidr'], sddc_connected_vpc['linked_vpc_subnets'][0]['availability_zone'], sddc_connected_vpc['active_eni'],sddc_connected_vpc_services['results'][0]['enabled']])
    return table

def setSDDCConnectedServices(proxy_url,sessiontoken, value):
    myHeader = {'csp-auth-token': sessiontoken}
    myURL = (proxy_url + "/cloud-service/api/v1/infra/linked-vpcs")
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_connected_vpc = json_response['results'][0]
    mySecondURL = (proxy_url + "/cloud-service/api/v1/infra/linked-vpcs/" + sddc_connected_vpc['linked_vpc_id'] + "/connected-services/s3")
    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': sessiontoken}
    json_data = {
    "name": "s3" ,
    "enabled": value
    }
    thirdresponse = requests.put(mySecondURL, headers=myHeader, json=json_data)
    json_response_status_code = thirdresponse.status_code
    return json_response_status_code

def getSDDCGroups(proxy_url,sessiontoken,gw):
    """ Gets the SDDC Groups. Use 'mgw' or 'cgw' as the parameter """
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    # removing 'sks-nsxt-manager' from proxy url to get correct URL
    myURL = proxy_url_short + "policy/api/v1/infra/domains/" + gw + "/groups"
    # print(myURL)
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    # print(json_response)
    sddc_group = json_response['results']
    table = PrettyTable(['ID', 'Name'])
    for i in sddc_group:
        table.add_row([i['id'], i['display_name']])
    # print(table)
    return table

def getSDDCGroup(proxy_url,sessiontoken,gw,group_id):
    """ Gets a single SDDC Group. Use 'mgw' or 'cgw' as the parameter """
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    # removing 'sks-nsxt-manager' from proxy url to get correct URL
    myURL = proxy_url_short + "policy/api/v1/infra/domains/" + gw + "/groups/" + group_id
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    # Checking for groups with defined criteria with the following command. 
    if 'expression' in json_response:
        group_criteria = json_response['expression'][0]
        if group_criteria["resource_type"] == "IPAddressExpression":
            group_IP_list = group_criteria['ip_addresses']
            print("The group " + group_id + " is based on the IP addresses criteria:")
            # print(group_IP_list,sep='\n') would work best with Python3.
            print(group_IP_list)
        elif group_criteria["resource_type"] == "ExternalIDExpression":
            group = json_response['expression']
            if group[0]['member_type'] == "VirtualMachine":
                myNewURL = proxy_url_short + "policy/api/v1/infra/domains/" + gw + "/groups/" + group_id + "/members/virtual-machines"
                new_response = requests.get(myNewURL, headers=myHeader)
                new_second_response = new_response.json()
                new_second_extra = new_second_response['results']
                new_table = PrettyTable(['Name'])
                for i in new_second_extra:
                    new_table.add_row([i['display_name']])
                print("\n The following Virtual Machines are part of the Group.")
                print(new_table)        
        elif group_criteria["resource_type"] == "Condition":
            group = json_response['expression']
            print("The group " + group_id + " is based on these criteria:")
            table = PrettyTable(['Member Type', 'Key', 'Operator', 'Value'])
            for i in group:
                table.add_row([i['member_type'], i['key'], i['operator'], i['value']])
            print(table)
            if group[0]['member_type'] == "VirtualMachine":
                myNewURL = proxy_url_short + "policy/api/v1/infra/domains/" + gw + "/groups/" + group_id + "/members/virtual-machines"
                new_response = requests.get(myNewURL, headers=myHeader)
                new_second_response = new_response.json()
                new_second_extra = new_second_response['results']
                new_table = PrettyTable(['Name'])
                for i in new_second_extra:
                    new_table.add_row([i['display_name']])
                print("\n The following Virtual Machines are part of the Group.")
                print(new_table)
            else:
                myNewURL = proxy_url_short + "policy/api/v1/infra/domains/" + gw + "/groups/" + group_id + "/members/ip-addressesa"
                new_response = requests.get(myNewURL, headers=myHeader)
                new_second_response = new_response.json()
                new_second_extra = new_second_response['results']
                new_table = PrettyTable(['Name'])
                for i in new_second_extra:
                    new_table.add_row([i['display_name']])
                print("\n The following IP addresses are part of the Group.")
                print(new_table)
        else:
            print("Incorrect syntax. Try again.")
    else:
        print("This group has no criteria defined.")
    return

def removeSDDCGroup(proxy_url, sessiontoken, gw, group_id):
    """ Remove an SDDC Group """
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    # removing 'sks-nsxt-manager' from proxy url to get correct URL
    myURL = proxy_url_short + "policy/api/v1/infra/domains/" + gw + "/groups/" + group_id
    response = requests.delete(myURL, headers=myHeader)
    json_response = response.status_code
    print(json_response)
    if json_response == 200 :
        print("The group " + group_id + " has been deleted")
    else :
        print("There was an error. Try again.")
    return json_response

def newSDDCGroupIPaddress(proxy_url,sessiontoken,gw,group_id,ip_addresses):
    """ Creates a single SDDC Group based on IP addresses. Use 'mgw' or 'cgw' as the parameter """
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    # removing 'sks-nsxt-manager' from proxy url to get correct URL
    myURL = proxy_url_short + "policy/api/v1/infra/domains/" + gw + "/groups/" + group_id
    json_data = {
    "expression" : [ {
      "ip_addresses" : ip_addresses,
      "resource_type" : "IPAddressExpression"
    } ],
    "id" : group_id,
    "display_name" : group_id,
    "resource_type" : "Group"}
    response = requests.put(myURL, headers=myHeader, json=json_data)
    json_response_status_code = response.status_code
    return json_response_status_code

def newSDDCGroupCriteria(proxy_url,sessiontoken,gw,group_id,member_type,key,operator,value):
    """ Creates a single SDDC Group based on a criteria. Use 'cgw' as the parameter """
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    # removing 'sks-nsxt-manager' from proxy url to get correct URL
    myURL = proxy_url_short + "policy/api/v1/infra/domains/" + gw + "/groups/" + group_id
    json_data = {
    "expression" : [ {
      "member_type" : member_type,
      "key" : key,
      "operator" : operator,
      "value" : value,
      "resource_type" : "Condition"
    } ],
    "id" : group_id,
    "display_name" : group_id,
    }
    response = requests.put(myURL, headers=myHeader, json=json_data)
    json_response_status_code = response.status_code
    return json_response_status_code

def getVMExternalID(proxy_url,sessiontoken,vm_name):
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    VMlist_url = (proxy_url_short + "policy/api/v1/infra/realized-state/enforcement-points/vmc-enforcementpoint/virtual-machines")
    response = requests.get(VMlist_url, headers=myHeader)
    response_dictionary = response.json()
    extracted_dictionary = response_dictionary['results']
    # Below, we're extracting the Python dictionary for the specific VM and then we extract the external_ID/ Instance UUID from the dictionary.
    extracted_VM = next(item for item in extracted_dictionary if item["display_name"] == vm_name)
    extracted_VM_external_id = extracted_VM['external_id']
    return extracted_VM_external_id

def getVMs(proxy_url,sessiontoken):
    """ Gets a list of all compute VMs, with their power state and their external ID. """
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    VMlist_url = (proxy_url_short + "policy/api/v1/infra/realized-state/enforcement-points/vmc-enforcementpoint/virtual-machines")
    response = requests.get(VMlist_url, headers=myHeader)
    response_dictionary = response.json()
    extracted_dictionary = response_dictionary['results']
    table = PrettyTable(['Display_Name', 'Status', 'External_ID'])
    for i in extracted_dictionary:
        table.add_row([i['display_name'], i['power_state'], i['external_id']])
    return table

def newSDDCGroupVM(proxy_url,sessiontoken,gw,group_id,vm_list):
    """ Creates a single SDDC Group based on a list of VM external_id. Use 'cgw' as the parameter """
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    # removing 'sks-nsxt-manager' from proxy url to get correct URL
    myURL = proxy_url_short + "policy/api/v1/infra/domains/" + gw + "/groups/" + group_id
    json_data = {
    "expression" : [ {
        "member_type" : "VirtualMachine",
        "external_ids" : vm_list,
        "resource_type" : "ExternalIDExpression"
    } ],
    "id" : group_id,
    "display_name" : group_id,
    }
    response = requests.put(myURL, headers=myHeader, json=json_data)
    json_response_status_code = response.status_code
    return json_response_status_code
    
def getSDDCServices(proxy_url,sessiontoken):
    """ Gets the SDDC Services """
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    # removing 'sks-nsxt-manager' from proxy url to get correct URL
    myURL = proxy_url_short + "policy/api/v1/infra/services"
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_services = json_response['results']
    table = PrettyTable(['ID', 'Name'])
    for i in sddc_services:
        table.add_row([i['id'], i['display_name']])
    return table

def getSDDCService(proxy_url,sessiontoken,service_id):
    """ Gets the SDDC Services """
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    # removing 'sks-nsxt-manager' from proxy url to get correct URL
    myURL = proxy_url_short + "policy/api/v1/infra/services/" + service_id 
    response = requests.get(myURL, headers=myHeader)
    json_response_status_code = response.status_code
    if json_response_status_code != 200:
        print("This service does not exist.")
    else:
        json_response = response.json()
        service_entries = json_response['service_entries']
        table = PrettyTable(['ID', 'Name', 'Protocol', 'Source Ports', 'Destination Ports'])
        for i in service_entries:
            table.add_row([i['id'], i['display_name'], i['l4_protocol'], i['source_ports'], i['destination_ports']])
        return table

def newSDDCService(proxy_url,sessiontoken,service_id,service_entries):
    """ Create a new SDDC Service based on service_entries """
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    # removing 'sks-nsxt-manager' from proxy url to get correct URL
    myURL = proxy_url_short + "policy/api/v1/infra/services/" + service_id 
    json_data = {
    "service_entries":service_entries,
    "id" : service_id,
    "display_name" : service_id,
    }
    response = requests.put(myURL, headers=myHeader, json=json_data)
    json_response_status_code = response.status_code
    return json_response_status_code

# def newSDDCServiceEntry(proxy_url,sessiontoken,service_entry_id,source_port,destination_port,l4_protocol):
#    """ Create a new SDDC Service Entry """
#    myHeader = {'csp-auth-token': sessiontoken}
#    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
#    # removing 'sks-nsxt-manager' from proxy url to get correct URL
#    myURL = proxy_url_short + "policy/api/v1/infra/services/" + service_id
#    json_data = {
#    "l4_protocol": l4_protocol,
#    "source_ports": source_port_list,
#    "destination_ports" : destination_port_list,
#    "resource_type" : "L4PortSetServiceEntry",
#    "id" : service_entry_id,
#    "display_name" : service_entry_id     }


def removeSDDCService(proxy_url, sessiontoken,service_id):
    """ Remove an SDDC Service """
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    # removing 'sks-nsxt-manager' from proxy url to get correct URL
    myURL = proxy_url_short + "policy/api/v1/infra/services/" + service_id
    response = requests.delete(myURL, headers=myHeader)
    json_response = response.status_code
    print(json_response)
    if json_response == 200 :
        print("The group " + service_id + " has been deleted")
    else :
        print("There was an error. Try again.")
    return


def getSDDCDNS_Zones(proxy_url,sessiontoken):
    """ Gets the SDDC Zones """
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    # removing 'sks-nsxt-manager' from proxy url to get correct URL
    myURL = proxy_url_short + "policy/api/v1/infra/dns-forwarder-zones"
    response = requests.get(myURL, headers=myHeader)
    json_response = response.json()
    sddc_dns = json_response['results']
    table = PrettyTable(['ID', 'Name','DNS Domain Names','upstream_servers'])
    for i in sddc_dns:
        table.add_row([i['id'], i['display_name'], i['dns_domain_names'], i['upstream_servers']])
    return table

def getSDDCDNS_Services(proxy_url,sessiontoken,gw):
    """ Gets the DNS Services. Use 'mgw' or 'cgw' as the parameter """
    myHeader = {'csp-auth-token': sessiontoken}
    proxy_url_short = proxy_url.rstrip("sks-nsxt-manager")
    # removing 'sks-nsxt-manager' from proxy url to get correct URL
    myURL = proxy_url_short + "policy/api/v1/infra/tier-1s/" + gw + "/dns-forwarder"
    response = requests.get(myURL, headers=myHeader)
    sddc_dns_service = response.json()
    table = PrettyTable(['ID', 'Name', 'Listener IP'])
    table.add_row([sddc_dns_service['id'], sddc_dns_service['display_name'], sddc_dns_service['listener_ip']])
    return table

def createLotsNetworks(proxy_url, sessiontoken,network_number):
    """ Creates lots of networks! """
    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': sessiontoken}
    for x in range(0,network_number):
        display_name = "network-name"+str(x)
        myURL = (proxy_url + "/policy/api/v1/infra/tier-1s/cgw/segments/" + display_name)
    #  '/tier-1s/cgw' might only be applicable for multi tier-1s architecture. To be confirmed.
    # print(myURL)
        json_data = {
                "subnets":[{"gateway_address":"10.200."+str(x)+".1/24"}],
                "type":"ROUTED",
                "display_name":display_name,
                "advanced_config":{"connectivity":"ON"},
                "id":"network-test"+str(x)
                }
        response = requests.put(myURL, headers=myHeader, json=json_data)
        json_response_status_code = response.status_code
    

# --------------------------------------------
# ---------------- Main ----------------------
# --------------------------------------------

if len(sys.argv) > 1:
    intent_name = sys.argv[1].lower()
else:
    intent_name = ""

session_token = getAccessToken(Refresh_Token)
proxy = getNSXTproxy(ORG_ID, SDDC_ID, session_token)

if intent_name == "create-lots-networks":
    number = int(sys.argv[2])
    createLotsNetworks(proxy,session_token,number)
elif intent_name == "show-dns-zones":
    print(getSDDCDNS_Zones(proxy,session_token))
elif intent_name == "show-sddc-hosts":
    print(getCDChosts(SDDC_ID, ORG_ID, session_token))
elif intent_name == "show-sddcs":
    print(getSDDCS(ORG_ID, session_token))
elif intent_name == "show-org-users":
    print(showORGusers(ORG_ID, session_token))
elif intent_name == "show-vms":
    print(getVMs(proxy,session_token))
elif intent_name == "show-connected-accounts":
    print(getConnectedAccounts(ORG_ID,session_token))
elif intent_name == "show-compatible-subnets":
    n = (len(sys.argv))
    if ( n < 4):
        print("Usage: show-compatible-subnets linkedAccountId region")
    else:
        print(getCompatibleSubnets(ORG_ID,session_token,sys.argv[2],sys.argv[3]))
elif intent_name == "get-access-token":
    print(session_token)
elif intent_name == "show-vpn":
    if len(sys.argv) == 2:
        SDDCVPN = getSDDCVPN(proxy, session_token)
        print(SDDCVPN)
    elif len(sys.argv) == 3:
        VPN_ID = sys.argv[2]
        SDDC_VPN_STATS = getSDDCVPNSTATS(proxy,session_token,VPN_ID)
        print(SDDC_VPN_STATS)
    else:
        print("Incorrect syntax. Check the help.")
elif intent_name == "new-vpn":
    vpn_name = input("Enter the VPN Name: ")
    remote_private_ip = input('Enter the remote private IP:')
    remote_public_ip = input('Enter the remote public IP:')
    source_networks = input('Enter your source networks, separated by commas (for example: 192.168.10.0/24,192.168.20.0/24)')
    destination_networks = input('Enter your destination networks, separated by commas (for example: 192.168.10.0/24,192.168.20.0/24)')
    print(vpn_name + remote_private_ip + remote_public_ip)
elif intent_name == "show-vpn-ipsec-profile":
    vpn_ipsec_profile = getSDDCVPNIpsecProfiles(proxy, session_token)
    print(vpn_ipsec_profile)
elif intent_name == "show-vpn-ipsec-tunnel-profile":
    vpn_ipsec_tunnel_profile = getSDDCVPNIpsecTunnelProfiles(proxy, session_token)
    print(vpn_ipsec_tunnel_profile)
elif intent_name == "show-vpn-ipsec-endpoints":
    vpn_ipsec_endpoints = getSDDCVPNIpsecEndpoints(proxy, session_token)
    print(vpn_ipsec_endpoints)
elif intent_name == "show-network":
    print(getSDDCnetworks(proxy, session_token))
elif intent_name == "new-network":
    if sys.argv[3].lower() == "routed" and len(sys.argv) == 7:
        # DHCP-Enabled Network
        display_name = sys.argv[2]
        routing_type = "ROUTED"
        gateway_address = sys.argv[4]
        dhcp_range = sys.argv[5]
        domain_name = sys.argv[6]
        newSDDC = newSDDCnetworks(proxy, session_token, display_name, gateway_address, dhcp_range, domain_name, routing_type)
        print(newSDDC)
    elif sys.argv[3].lower() == "disconnected" :
        # Disconnected Network
        display_name = sys.argv[2]
        routing_type = "DISCONNECTED"
        gateway_address = sys.argv[4]
        dhcp_range = ""
        domain_name = ""
        newSDDC = newSDDCnetworks(proxy, session_token, display_name, gateway_address, dhcp_range, domain_name, routing_type)
        print(newSDDC)
    elif sys.argv[3].lower() == "routed" and len(sys.argv) == 5:
        # Static Network
        display_name = sys.argv[2]
        gateway_address = sys.argv[4]
        dhcp_range = "none"
        domain_name = ""
        routing_type = "ROUTED"
        newSDDC = newSDDCnetworks(proxy, session_token, display_name, gateway_address, dhcp_range, domain_name, routing_type)
        print(newSDDC)
    else:
        print("Incorrect syntax. Try again or check the help.")
elif intent_name == "remove-network":
    network_id = sys.argv[2]
    print(removeSDDCNetworks(proxy, session_token,network_id))
elif intent_name == "show-nat":
    if len(sys.argv) == 2:
        print(getSDDCNAT(proxy, session_token))
    elif len(sys.argv) == 3:
        NATid = sys.argv[2]
        NATStats = getSDDCNATStatistics(proxy,session_token,NATid)
        print(NATStats)
    else: 
        print("Incorrect syntax. Try again or check the help.")
elif intent_name == "new-nat-rule":
    display_name = sys.argv[2]
    action = sys.argv[3]
    if action == "any" or action == "REFLEXIVE":
        translated_network = sys.argv[4]
        source_network = sys.argv[5]
        service = ""
        translated_port = ""
        if len(sys.argv) >= 7:
            logging = sys.argv[6]
        else:
            logging = "false"
        if len(sys.argv) >= 8:
            status = sys.argv[7]
        else:
            status = "true"
        print(newSDDCNAT(proxy, session_token, display_name, action, translated_network, source_network, service, translated_port, logging, status))
    elif action == "DNAT": 
        translated_network = sys.argv[4]
        source_network = sys.argv[5]
        service = sys.argv[6]
        translated_port = sys.argv[7]
        if len(sys.argv) >= 9:
            logging = sys.argv[8]
        else:
            logging = "false"
        if len(sys.argv) >= 10:
            status = sys.argv[9]
        else:
            status = "true"
        print(newSDDCNAT(proxy, session_token, display_name, action, translated_network, source_network, service, translated_port, logging, status))
    else :
        print("There was an error. Make sure you follow the instructions.")
elif intent_name == "remove-nat-rule":
    if len(sys.argv) == 3:
        id = sys.argv[2]
        result = removeSDDCNAT(proxy, session_token, id)
        print(result)
        print("\n")
        print(getSDDCNAT(proxy, session_token))
    else:
        print("Incorrect syntax. Try again or check the help.")
elif intent_name == "show-cgw-rule":
    print(getSDDCCGWRule(proxy, session_token))
elif intent_name == "show-mgw-rule":
    print(getSDDCMGWRule(proxy, session_token))
elif intent_name == "show-dfw-section-rules":
    if len(sys.argv) == 2:
        print("Incorrect syntax. Specify the section name.")
    if len(sys.argv) == 3:
        section = sys.argv[2]
        print(getSDDCDFWRule(proxy, session_token,section))
elif intent_name == "new-dfw-rule":
    sequence_number = 0
    display_name = sys.argv[2]
    sg_string = sys.argv[3]
    dg_string = sys.argv[4]
    group_index = '/infra/domains/cgw/groups/'
    scope_index = '/infra/labels/cgw-'
    list_index = '/infra/services/'
    if sg_string.lower() == "connected_vpc":
        source_groups = ["/infra/tier-0s/vmc/groups/connected_vpc"]
    elif sg_string.lower() == "directconnect_prefixes":
        source_groups = ["/infra/tier-0s/vmc/groups/directConnect_prefixes"]
    elif sg_string.lower() == "s3_prefixes":
        source_groups = ["/infra/tier-0s/vmc/groups/s3_prefixes"]
    elif sg_string.lower() == "any":
        source_groups = ["ANY"]
    else:
        sg_list = sg_string.split(",")
        source_groups= [group_index + x for x in sg_list]
    if dg_string.lower() == "connected_vpc":
        destination_groups = ["/infra/tier-0s/vmc/groups/connected_vpc"]
    elif dg_string.lower() == "directconnect_prefixes":
        destination_groups = ["/infra/tier-0s/vmc/groups/directConnect_prefixes"]
    elif dg_string.lower() == "s3_prefixes":
        destination_groups = ["/infra/tier-0s/vmc/groups/s3_prefixes"]
    elif dg_string.lower() == "any":
        destination_groups = ["ANY"]
    else:
        dg_list = dg_string.split(",")
        destination_groups = [group_index + x for x in dg_list]
    services_string = sys.argv[5]
    if services_string.lower() == "any":
        services = ["ANY"]
    else:
        services_list = services_string.split(",")
        services = [list_index + x for x in services_list]
    action = sys.argv[6].upper()
    section = sys.argv[7]
    if len(sys.argv) == 9:
        sequence_number = sys.argv[8]
        new_rule = newSDDCDFWRule(proxy, session_token, display_name, source_groups, destination_groups, services, action, section, sequence_number)
    else:
        new_rule = newSDDCDFWRule(proxy, session_token, display_name, source_groups, destination_groups, services, action, section, sequence_number)
    if new_rule == 200:
        print("\n The rule has been created.")
        print(getSDDCDFWRule(proxy,session_token, section))
    else:
        print("Incorrect syntax. Try again.")
elif intent_name == "remove-dfw-rule":
    if len(sys.argv) != 4:
        print("Incorrect syntax. ")
    else:
        section_id = sys.argv[2]
        rule_id = sys.argv[3]
        if removeSDDCDFWRule(proxy, session_token, section_id, rule_id) == 200:
            print("The rule " + rule_id + " has been deleted")
            print(getSDDCDFWRule(proxy,session_token, section_id))
        else :
            print("Issues deleting the security rule. Check the syntax.")
elif intent_name == "show-dfw-section":
    print(getSDDCDFWSection(proxy, session_token))
elif intent_name == "new-dfw-section":
    if len(sys.argv) >= 5:
        print("Wrong syntax, try again.")
    if len(sys.argv) == 3:
        name = sys.argv[2]
        category = "Application"
        status_code = newSDDCDFWSection(proxy, session_token, name, category)
        if status_code == 200:
            print("Success:")
            print("\nThe section " + name + " has been created in the " + category + " category.")
            print(getSDDCDFWSection(proxy, session_token))
        else:
            print("There was an error. Check the syntax.")
    if len(sys.argv) == 4:
        name = sys.argv[2]
        category = sys.argv[3]
        status_code = newSDDCDFWSection(proxy, session_token, name, category)
        if status_code == 200:
            print("Success:")
            print("\nThe section " + name + " has been created in the " + category + " category.")
            print(getSDDCDFWSection(proxy, session_token))
        else:
            print("There was an error. Check the syntax.")
elif intent_name == "remove-dfw-section":
    if len(sys.argv) != 3:
        print("Incorrect syntax. ")
    else:
        section_id = sys.argv[2]
        if removeSDDCDFWSection(proxy, session_token, section_id) == 200:
            print("The section " + section_id + " has been deleted.")
            print(getSDDCDFWSection(proxy,session_token))
        else :
            print("Issues deleting the DFW section. Check the syntax.")
elif intent_name == "show-mtu":
    print("The MTU over the Direct Connect is " + str(getSDDCMTU(proxy,session_token)) + " Bytes.")
elif intent_name == "set-mtu":
    if len(sys.argv) != 3:
        print("Incorrect syntax.")
    mtu = sys.argv[2]
    if int(mtu) < 1500 or int(mtu) > 8900:
        print("Incorrect syntax. The MTU should be between 1500 and 8900 bytes.")
    else:
        setMTU = setSDDCMTU(proxy,session_token,mtu)
        if setMTU == 200:
            print("The MTU has been updated:")
            print("\nThe MTU over the Direct Connect is now set to " + str(getSDDCMTU(proxy,session_token)) + " Bytes.")
        else:
            print("There was an error. Check the syntax.")
elif intent_name == "show-shadow-account":
    print("The SDDC is deployed in the " + str(getSDDCShadowAccount(proxy,session_token)) + " AWS Shadow Account.")
elif intent_name == "show-sddc-bgp-as":
    print("The SDDC BGP Autonomous System is ASN " + getSDDCBGPAS(proxy,session_token) + ".")
elif intent_name == "set-sddc-bgp-as":
    if len(sys.argv) != 3:
        print("Incorrect syntax.")
    else:
        asn = sys.argv[2]
        setasn = setSDDCBGPAS(proxy,session_token,asn)
        print(setasn)
        if setasn == 200:
            print("The BGP AS has been updated:")
            print("The SDDC BGP Autonomous System is ASN " + getSDDCBGPAS(proxy,session_token) + ".")
        else:
            print("There was an error. Check the syntax.")
            print("The SDDC BGP Autonomous System is ASN " + getSDDCBGPAS(proxy,session_token) + ".")
elif intent_name == "show-sddc-bgp-vpn":
    print(getSDDCBGPVPN(proxy,session_token))
elif intent_name == "show-sddc-connected-vpc":
    print(getSDDCConnectedVPC(proxy,session_token))
elif intent_name == "set-sddc-connected-services":
    value = sys.argv[2]
    if setSDDCConnectedServices(proxy,session_token,value) == 200 and value == 'true':
        print("S3 access from the SDDC is over the ENI.")
    elif setSDDCConnectedServices(proxy,session_token,value) == 200 and value == 'false':
        print("S3 access from the SDDC is over the Internet.")
    else:
        print("Make sure you use a 'true' or 'false' parameter")
elif intent_name == "show-sddc-public-ip":
    print(getSDDCPublicIP(proxy,session_token))
elif intent_name == "new-sddc-public-ip":
    if len(sys.argv) != 3:
        print("Incorrect syntax. Please add a description of the public IP address.")
    else :
        notes = sys.argv[2]
        if newSDDCPublicIP(proxy, session_token, notes) == 200:
            print(getSDDCPublicIP(proxy,session_token))
        else :
            print("Issues creating a Public IP.")
elif intent_name == "set-public-ip":
    if len(sys.argv) != 4:
        print("Incorrect syntax. Please add the new description of the public IP address.")
    else:
        public_ip = sys.argv[2]
        notes = sys.argv[3]
        if setSDDCPublicIP(proxy, session_token, notes, public_ip) == 200:
            print(getSDDCPublicIP(proxy,session_token))
        else :
            print("Issues updating a Public IP. Check the syntax.")
elif intent_name == "remove-sddc-public-ip":
    if len(sys.argv) != 3:
        print("Incorrect syntax. ")
    else:
        public_ip = sys.argv[2]
        if removeSDDCPublicIP(proxy, session_token, public_ip) == 200:
            print(getSDDCPublicIP(proxy,session_token))
        else :
            print("Issues deleting the Public IP. Check the syntax.")
elif intent_name == "show-vpn-internet-ip":
    public_ip = getSDDCVPNInternetIP(proxy, session_token)
    print(public_ip)
elif intent_name == "show-sddc-state":
    sddc_state = getSDDCState(ORG_ID, SDDC_ID, session_token)
    print("\nThis is your current environment:")
    print(sddc_state)
elif intent_name == "new-mgw-rule":
    sequence_number = 0
    display_name = sys.argv[2]
    # String and List Manipulation:
    sg_string = sys.argv[3]
    dg_string = sys.argv[4]
    group_index = '/infra/domains/mgw/groups/'
    list_index = '/infra/services/'
    if sg_string.lower() == "any":
        source_groups = ["ANY"]
    else:
        sg_string = sg_string.upper()
        sg_list = sg_string.split(",")
        source_groups= [group_index + x for x in sg_list]
    
    # String and List Manipulation:
    # We take the input argument (NSX-MANAGER or VCENTER or ESXI nodes)

    if dg_string.lower() == "any":
        destination_groups = ["ANY"]
    else:
        dg_string = dg_string.upper()
        dg_list = dg_string.split(",")
        destination_groups= [group_index + x for x in dg_list]


    services_string = sys.argv[5]
    if services_string.lower() == "any":
        services = ["ANY"]
    else:
        services_list = services_string.split(",")
        print(services_list)
        services = [list_index + x for x in services_list]
    action = sys.argv[6].upper()
    if len(sys.argv) == 8:
        sequence_number = sys.argv[7]
        new_rule = newSDDCMGWRule(proxy, session_token, display_name, source_groups, destination_groups, services, action, sequence_number)
        print(new_rule)
    else:
        new_rule = newSDDCMGWRule(proxy, session_token, display_name, source_groups, destination_groups, services, action, sequence_number)
    if new_rule == 200:
        print("\n The rule has been created.")
        print(getSDDCMGWRule(proxy,session_token))
        print(new_rule)
    else:
        print("Incorrect syntax. Try again.")
elif intent_name == "new-cgw-rule":
    sequence_number = 0
    display_name = sys.argv[2]
    sg_string = sys.argv[3]
    dg_string = sys.argv[4]
    group_index = '/infra/domains/cgw/groups/'
    scope_index = '/infra/labels/cgw-'
    list_index = '/infra/services/'
    if sg_string.lower() == "connected_vpc":
        source_groups = ["/infra/tier-0s/vmc/groups/connected_vpc"]
    elif sg_string.lower() == "directconnect_prefixes":
        source_groups = ["/infra/tier-0s/vmc/groups/directConnect_prefixes"]
    elif sg_string.lower() == "s3_prefixes":
        source_groups = ["/infra/tier-0s/vmc/groups/s3_prefixes"]
    elif sg_string.lower() == "any":
        source_groups = ["ANY"]
    else:
        sg_list = sg_string.split(",")
        source_groups = [group_index + x for x in sg_list]
    if dg_string.lower() == "connected_vpc":
        destination_groups = ["/infra/tier-0s/vmc/groups/connected_vpc"]
    elif dg_string.lower() == "directconnect_prefixes":
        destination_groups = ["/infra/tier-0s/vmc/groups/directConnect_prefixes"]
    elif dg_string.lower() == "s3_prefixes":
        destination_groups = ["/infra/tier-0s/vmc/groups/s3_prefixes"]
    elif dg_string.lower() == "any":
        destination_groups = ["ANY"]
    else:
        dg_list = dg_string.split(",")
        destination_groups= [group_index + x for x in dg_list]
    services_string = sys.argv[5]
    if services_string.lower() == "any":
        services = ["ANY"]
    else:
        services_list = services_string.split(",")
        services = [list_index + x for x in services_list]
    action = sys.argv[6].upper()
    scope_string = sys.argv[7].lower()
    scope_list = scope_string.split(",")
    scope = [scope_index + x for x in scope_list]
    if len(sys.argv) == 9:
        sequence_number = sys.argv[8]
        new_rule = newSDDCCGWRule(proxy, session_token, display_name, source_groups, destination_groups, services, action, scope, sequence_number)
    else:
        new_rule = newSDDCCGWRule(proxy, session_token, display_name, source_groups, destination_groups, services, action, scope, sequence_number)
    if new_rule == 200:
        print("\n The rule has been created.")
        print(getSDDCCGWRule(proxy,session_token))
    else:
        print("Incorrect syntax. Try again.")
elif intent_name == "remove-cgw-rule":
    if len(sys.argv) != 3:
        print("Incorrect syntax. ")
    else:
        rule_id = sys.argv[2]
        if removeSDDCCGWRule(proxy, session_token, rule_id) == 200:
            print("The rule " + rule_id + " has been deleted")
            print(getSDDCCGWRule(proxy,session_token))
        else :
            print("Issues deleting the security rule. Check the syntax.")
elif intent_name == "remove-mgw-rule":
    if len(sys.argv) != 3:
        print("Incorrect syntax. ")
    else:
        rule_id = sys.argv[2]
        if removeSDDCMGWRule(proxy, session_token, rule_id) == 200:
            print(getSDDCMGWRule(proxy,session_token))
        else :
            print("Issues deleting the security rule. Check the syntax.")
elif intent_name == "new-group":
    gw = sys.argv[2].lower()
    group_id = sys.argv[3]
    if gw == "mgw" and len(sys.argv) == 4:
        ip_addresses = []
        ip_address = ''
        # Start a loop that will run until the user enters 'done'.
        while ip_address != 'done':
        # Ask the user for a name.
            ip_address = input("Please enter IP address (for example, \"172.16.10.20\") or type 'done' when your list is finished:")
        # Add the new name to our list.
            if ip_address != "done":
                ip_addresses.append(ip_address)
        newSDDCGroup = newSDDCGroupIPaddress(proxy,session_token,gw,group_id,ip_addresses)
        print(newSDDCGroup)
    if gw == "mgw" and len(sys.argv) == 5:
        ip_addresses_string = sys.argv [4]
        ip_addresses = ip_addresses_string.split(",")
        newSDDCGroup = newSDDCGroupIPaddress(proxy,session_token,gw,group_id,ip_addresses)
        print(newSDDCGroup) 
    if gw == "cgw":
        group_criteria = sys.argv[4].lower()
        if group_criteria not in ["ip-based", "member-based", "criteria-based"]:
            print("Incorrect syntax. Make sure you use one of the 3 methods to define a CGW group: ip-based, member-based or criteria-based.")
        else:
            if group_criteria == "ip-based" and len(sys.argv) == 5:
                ip_addresses = []
            # Set new_name to something other than 'quit'.
                ip_address = ''
            # Start a loop that will run until the user enters 'quit'.
                while ip_address != 'done':
            # Ask the user for a name.
                    ip_address = input("Please enter IP address (\"172.16.10.20\") or type 'done' when your list is finished: ")
            # Add the new name to our list.
                    if ip_address != "done":
                        ip_addresses.append(ip_address)
                newSDDCGroup = newSDDCGroupIPaddress(proxy,session_token,gw,group_id,ip_addresses)
                print(newSDDCGroup)
            elif group_criteria == "ip-based" and len(sys.argv) == 6:
                ip_addresses_string = sys.argv [5]
                ip_addresses = ip_addresses_string.split(",")
                newSDDCGroup = newSDDCGroupIPaddress(proxy,session_token,gw,group_id,ip_addresses)
                print(newSDDCGroup)
            elif group_criteria == "criteria-based" and len(sys.argv) == 5:
            # Only support for Virtual_Machine based criteria for now.
                # member_type = input("Please enter your criteria type:")
                member_type = "VirtualMachine"
                key = input("Please enter the criteria (Name, Tag, OSName or ComputerName): ")
                if key not in ["Name", "Tag", "OSName", "ComputerName"]:
                    print("Incorrect syntax. Check again.")
                else:
                    operator=input("Please enter the operator (EQUALS, NOTEQUALS, CONTAINS, STARTSWITH, ENDSWITH): ")
                    if operator not in ["EQUALS", "NOTEQUALS", "CONTAINS", "STARTSWITH", "ENDSWITH"]:
                        print("Incorrect syntax. Check again.")
                    if key == "Tag" and operator == "NOTEQUALS":
                        print("Incorrect syntax. The tag method does not support the NOTEQUALS Operator. Try again.")
                    else:
                        value=input("Enter the value of your membership criteria: ")
                        newSDDCGroup = newSDDCGroupCriteria(proxy,session_token,gw,group_id,member_type,key,operator,value)
                        print(newSDDCGroup)
            elif group_criteria == "criteria-based" and len(sys.argv) == 8:
            # Only support for Virtual_Machine based criteria for now.
                # member_type = input("Please enter your criteria type:")
                member_type = "VirtualMachine"
                key = sys.argv[5]
                operator = sys.argv[6]
                value = sys.argv[7]
                if key not in ["Name", "Tag", "OSName", "ComputerName"]:
                    print("Incorrect syntax. Check again.")
                elif operator not in ["EQUALS", "NOTEQUALS", "CONTAINS", "STARTSWITH", "ENDSWITH"]:
                    print("Incorrect syntax. Check again.")
                else:
                    newSDDCGroup = newSDDCGroupCriteria(proxy,session_token,gw,group_id,member_type,key,operator,value)
                    print(newSDDCGroup)
            elif group_criteria == "member-based" and len(sys.argv) == 5:
            # v1 will be based on a list of VMs. Will not include segment-based for the time being,
                vm_list = []
            # Set new_name to something other than 'quit'.
                vm_name = ''
            # Start a loop that will run until the user enters 'quit'.
                while vm_name != 'done':
            # Ask the user for a name.
                    vm_name = input("Please enter the name of the VM or type 'done' when your list is finished: ")
            # Add the new name to our list.
                    if vm_name != "done":
                        vm_id = getVMExternalID(proxy,session_token,vm_name)
                        vm_list.append(vm_id)
                newSDDCGroup = newSDDCGroupVM(proxy,session_token,gw,group_id,vm_list)
                print(newSDDCGroup)
            elif group_criteria == "member-based" and len(sys.argv) == 6:
                vm_name_string = sys.argv[5]
                vm_name_list = vm_name_string.split(",")
                ## iterate through list or through previous string to get list of external ids
                vm_external_id_list = [getVMExternalID(proxy,session_token,x) for x in vm_name_list]
                # vm_id = getVMExternalID(proxy,session_token,vm_name)
                newSDDCGroup = newSDDCGroupVM(proxy,session_token,gw,group_id,vm_external_id_list)
                print(newSDDCGroup)
            else:
                print("Incorrect syntax. Try again.")
elif intent_name == "show-group":
    if len(sys.argv) == 2:
        mgw_groups = getSDDCGroups(proxy, session_token, "mgw")
        print(("\nHere are the Management Groups:"))
        print(mgw_groups)
        cgw_groups = getSDDCGroups(proxy, session_token, "cgw")
        print(("\nHere are the Comnpute Groups:"))
        print(cgw_groups)
    elif len(sys.argv) == 3:
        gw = sys.argv[2].lower()
        sddc_groups = getSDDCGroups(proxy, session_token, gw)
        print(sddc_groups)
    elif len(sys.argv) == 4:
        group_id = sys.argv[3]
        gw = sys.argv[2].lower()
        sddc_groups = getSDDCGroup(proxy,session_token,gw,group_id)
    else:
        print("Incorrect syntax. Try again or check the help.")
elif intent_name == "remove-group":
    if len(sys.argv) != 4:
        print("This command did not work. Follow the instructions")
    else:
        gw = sys.argv[2].lower()
        group_id = sys.argv[3]
        sddc_group_delete = removeSDDCGroup(proxy,session_token,gw,group_id)
elif intent_name == "show-dns-services":
    if len(sys.argv) == 2:
        mgw_dns_services = getSDDCDNS_Services(proxy, session_token, "mgw")
        print("\nHere are the Management DNS Services:")
        print(mgw_dns_services)
        cgw_dns_services = getSDDCDNS_Services(proxy, session_token, "cgw")
        print("\nHere are the Compute DNS Services:")
        print(cgw_dns_services)
    elif len(sys.argv) == 3:
        gw = sys.argv[2].lower()
        sddc_dns_services = getSDDCDNS_Services(proxy, session_token, gw)
        print(sddc_dns_services)
    else:
        print("Incorrect syntax. Try again or check the help.")
elif intent_name == "show-services" or intent_name == "show-service":
    if len(sys.argv) == 2:
        sddc_services = getSDDCServices(proxy,session_token)
        print(sddc_services)
    elif len(sys.argv) == 3:
        service_id = sys.argv[2]
        sddc_service = getSDDCService(proxy,session_token,service_id)
        print(sddc_service)
    else:
        print("This command did not work. Follow the instructions")
elif intent_name == "new-service":
    if len(sys.argv) == 2:
        service_id = input("Please input the name of the service:")
        service_entry_list = []
            # Start a loop that will run until the user enters 'quit'.
            # Ask the user for a name.
        destination_port = ""
        while destination_port != 'done':
            destination_port_list = []
            source_port_list = []
            service_entry_id = input("Please enter the Service Entry ID:")
            l4_protocol = input("Please enter the L4 Protocol:")
            source_port = ""
            destination_port = ""
            while source_port != 'done':
                source_port = input("Plese enter the Source Ports or type 'done' when your list is finished:")
                if source_port != "done":
                    source_port_list.append(source_port)
            while (destination_port != 'next') and (destination_port != "done"):
                source_port = ""
                destination_port = input("Plese enter the Destination Ports, type 'next' when you want to define another service entry or 'done' if you have finished:")
                if (destination_port != 'next') and (destination_port != "done"):
                    destination_port_list.append(destination_port)
            # print(service_id)
            # print(destination_port_list)
            # print(source_port_list)
            # print(l4_protocol)
            service_entry = {
                "l4_protocol": l4_protocol,
                "source_ports": source_port_list,
                "destination_ports" : destination_port_list,
                "resource_type" : "L4PortSetServiceEntry",
                "id" : service_entry_id,
                "display_name" : service_entry_id     }
            service_entry_list.append(service_entry)
            # print(service_entry)
            # print(service_entry_list)
        newSDDCService(proxy,session_token,service_id,service_entry_list)
        sddc_service = getSDDCService(proxy,session_token,service_id)
        print(sddc_service)
    elif len(sys.argv) == 4:
        name = sys.argv[2]
        service_entry_string = sys.argv[3]
        service_entry_list = service_entry_string.split(",")
        newSDDCService(proxy,session_token,name,service_entry_list)
        sddc_service = getSDDCService(proxy,session_token,service_id)
        print(sddc_service)
    else:
        print("Incorrect syntax")
# elif intent_name == "new-service-entry":
#    print("This is WIP")
elif intent_name == "remove-service":
    if len(sys.argv) > 3:
        print("This command did not work. Follow the instructions")
    else:
        service_id = sys.argv[2]
        sddc_service_delete = removeSDDCService(proxy,session_token,service_id)
else:
    print("\nWelcome to PyVMC !")
    print("\nHere are the currently supported commands: ")
    print("\nTo get a list of your VMs:")
    print("\tshow-vms")
    print("\nTo display a lit of your SDDCs:")
    print("\tshow-sddcs")
    print("\nTo get a view of your selected SDDC:")
    print("\tshow-sddc-state")
    print("\nTo show the list of organization users:")
    print("\tshow-org-users")
    print("\nTo show your access token:")
    print("\tget-access-token")
    print("\nTo show your current networks:")
    print("\tshow-network")
    print("\nTo create a new network:")
    print("\tnew-network")
    print("\nTo remove a network:")
    print("\tremove-network")
    print("\nTo show the CGW security rules:")
    print("\tshow-cgw-rule")
    print("\nTo create a new CGW security rule")
    print("\tnew-cgw-rule [NAME] [SOURCE-GROUPS] [DESTINATION-GROUPS] [SERVICE] [ACTION] [SCOPE] [SEQUENCE-NUMBER]")
    print("\nTo delete a CGW security rule:")
    print("\tremove-cgw-rule [RULE_ID]")
    print("\nTo show the MGW security rules:")
    print("\tshow-mgw-rule")
    print("\nTo create a new MGW security rule")
    print("\tnew-mgw-rule [NAME] [SOURCE-GROUPS] [DESTINATION-GROUPS] [SERVICE] [ACTION] [SEQUENCE-NUMBER]")
    print("\nTo delete a MGW security rule:")
    print("\tremove-mgw-rule [RULE_ID]")
    print("\nTo show the DFW sections:")
    print("\tshow-dfw-section")
    print("\nTo create a new DFW section")
    print("\tnew-dfw-section [NAME][CATEGORY]")  
    print("\nTo delete a DFW section:")
    print("\tremove-dfw-section [RULE_ID]") 
    print("\nTo show the DFW security rules within a section")
    print("\tshow-dfw-section-rules [SECTION]")
    print("\nTo create a new DFW security rule")
    print("\tnew-dfw-rule [NAME] [SOURCE-GROUPS] [DESTINATION-GROUPS] [SERVICE] [ACTION] [SECTION] [SEQUENCE-NUMBER]")
    print("\nTo delete a DFW rule:")
    print("\tremove-dfw-rule [SECTION_ID][RULE_ID]") 
    print("\nTo show the configured NAT rules:")
    print("\tshow-nat")
    print("\nTo show the statistics for a specific NAT rule:")
    print("\tshow-nat [NAT-RULE-ID] for statistics of a rule")
    print("\nTo create a new NAT rule:")
    print("\tnew-nat-rule")
    print("\nTo remove a NAT rule:")
    print("\tremove-nat-rule")
    print("\nTo create a new group:")
    print("\tnew-group [CGW/MGW] [Group_ID]")
    print("\nTo show existing groups:")
    print("\tshow-group [CGW/MGW] [Group_ID]")
    print("\nTo remove a group:")
    print("\tremove-group [CGW/MGW][Group_ID]")
    print("\nTo show services:")
    print("\tshow-services")
    print("\nTo show a specific service:")
    print("\tshow-services [SERVICE-ID]")
    print("\nTo create a new service:")
    print("\tnew-service")
    print("\nTo remove a service")
    print("\tremove-service [SERVICE-ID]")
    print("\nTo show DNS zones:")
    print("\tshow-dns-zones")
    print("\nTo show DNS services:")
    print("\tshow-dns-services")
    print("\nTo show the public IP used for VPN services:")
    print("\tshow-vpn-internet-ip")
    print("\nTo show the configured VPN:")
    print("\tshow-vpn")
    print("\nTo show the VPN statistics:")
    print("\tshow-vpn [VPN_ID]")
    print("\nTo show the VPN IPSEC profiles:")
    print("\tshow-vpn-ipsec-profile")
    print("\nTo show the VPN IPSEC tunnel profiles:")
    print("\tshow-vpn-ipsec-tunnel-profile")
    print("\nTo show the VPN IPSec endpoints:")
    print("\tshow-vpn-ipsec-endpoints")
    print("\nTo show the Shadow AWS Account VMC is deployed in:")
    print("\tshow-shadow-account")
    print("\nTo show the BGP AS number:")
    print("\tshow-sddc-bgp-as")
    print("\nTo update the BGP AS number:")
    print("\tset-bgp-as [ASN]")
    print("\nTo show whether DX is preferred over VPN:")
    print("\tshow-sddc-bgp-vpn")
    print("\nTo show the VPC connected to the SDDC:")
    print("\tshow-sddc-connected-vpc")
    print("\nTo show the MTU configured over the Direct Connect:")
    print("\tshow-mtu")
    print("\nTo set the MTU configured over the Direct Connect:")
    print("\tset-mtu")
    print("\nTo change whether to use S3 over the Internet or via the ENI:")
    print("\tset-sddc-connected-services")
    print("\nTo show the public IPs:")
    print("\tshow-sddc-public-ip")
    print("\nTo request a new public IP:")
    print("\tnew-sddc-public-ip")
    print("\nTo remove an existing public IP:")
    print("\tremove-sddc-public-ip")
    print("\nTo update the description of an existing public IP:")
    print("\tset-sddc-public-ip")
    print("\nTo show native AWS accounts connected to the SDDC:")
    print("\tshow-connected-accounts")
    print("\nTo show compatible native AWS subnets connected to the SDDC:")
    print("\tshow-compatible-subnets [LINKEDACCOUNTID] [REGION]")

    


"""

Roadmap:

- Create New Service Entry
- Show New Service Entry
- Add DHCP Relay CRUD
- Add DNS Config Config (DNS Read Only right now.)
- Add Port Mirroring CRUD
- Add IPFIX CRUD
- Update Service Read to support non-TCP/UDP based rules

"""
