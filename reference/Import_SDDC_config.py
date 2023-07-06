### Package Imports ####
import requests
import json
import argparse


### Ready arguments from command line ###
parser = argparse.ArgumentParser(description='Export user created NSX-T Firewall rules and objects for a given VMC SDDC.')
parser.add_argument('orgid')
parser.add_argument('sddcid')
parser.add_argument('refreshtoken')

args = parser.parse_args()

### Access Token ###
authurl = 'https://console.cloud.vmware.com/csp/gateway/am/api/auth/api-tokens/authorize?refresh_token=%s' %(args.refreshtoken)
headers = {'Accept': 'application/json'}
payload = {}
authresp = requests.post(authurl,headers=headers,data=payload)
authjson = json.loads(authresp.text)
token = authjson["access_token"]

### Get ReverseProxy URL ###
infourl = 'https://vmc.vmware.com/vmc/api/orgs/%s/sddcs/%s' %(args.orgid,args.sddcid)
headers = {'csp-auth-token': token, 'content-type': 'application/json'}
payload = {}
sddcresp = requests.get(infourl,headers=headers,data=payload)
sddcjson = json.loads(sddcresp.text)
srevproxyurl = sddcjson["resource_config"]["nsx_api_public_endpoint_url"]


curCursor = ''
pageSize = 1000
### Source SDDC URL's ###
smgwgroupsurl = '%s/policy/api/v1/infra/domains/mgw/groups?page_size=%s&cursor=%s' %(srevproxyurl,pageSize,curCursor)
scgwgroupsurl = '%s/policy/api/v1/infra/domains/cgw/groups?page_size=%s&cursor=%s' %(srevproxyurl,pageSize,curCursor)
scgwurl = '%s/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules' %(srevproxyurl)
smgwurl = '%s/policy/api/v1/infra/domains/mgw/gateway-policies/default/rules' %(srevproxyurl)
sservicesurl = '%s/policy/api/v1/infra/services?page_size=%s&cursor=%s' %(srevproxyurl,pageSize,curCursor)
sdfwurl = '%s/policy/api/v1/infra/domains/cgw/communication-maps' %(srevproxyurl)
ikeprofurl = '%s/policy/api/v1/infra/ipsec-vpn-ike-profiles' %(srevproxyurl)
tunnelprofurl = '%s/policy/api/v1/infra/ipsec-vpn-tunnel-profiles' %(srevproxyurl)
bgpneighborurl =  '%s/policy/api/v1/infra/tier-0s/vmc/locale-services/default/bgp/neighbors' %(srevproxyurl)
l3vpnsessionurl = '%s/policy/api/v1/infra/tier-0s/vmc/locale-services/default/ipsec-vpn-services/default/sessions' %(srevproxyurl)
l2vpnsessionurl = '%s/policy/api/v1/infra/tier-0s/vmc/locale-services/default/l2vpn-services/default/sessions' %(srevproxyurl)

headers = {'csp-auth-token': token, 'content-type': 'application/json'}

f = open('cslabm12temp.json',) 
  
# returns JSON object as  
# a dictionary 
data = json.load(f) 
  
# Iterating through the json 
# list 
#for i in data['MGWGroups']: 
#    print(i)
#print(data['MGWGroups'])
#print(data['Services'])
#print(data['MGWRules'])
#print(data['CGWRules'])
#print(data['DFWRules'])
print(data['IKEProfiles'][0]['resource_type'])
payload = {}
ikeps = data['IKEProfiles']
for ikep in ikeps:
    payload["id"]=ikep["id"]
    payload["encryption_algorithms"]=ikep["encryption_algorithms"]
    payload["ike_version"]=ikep["ike_version"]
    payload["dh_groups"]=ikep["dh_groups"]
    payload["sa_life_time"]=ikep["sa_life_time"]
    payload["resource_type"]=ikep["resource_type"]
    payload["display_name"]=ikep["display_name"]
    payload["marked_for_delete"]=ikep["marked_for_delete"]
    payload["overridden"]=ikep["overridden"]
    ikepurl= '%s/%s' %(ikeprofurl,ikep["id"])
    json_data = json.dumps(payload)
    createikepresp = requests.put(ikepurl,headers=headers,data=json_data)
    print(createikepresp.text)
    payload = {}
print(data['TunnelProfiles'][0]['resource_type'])
payload = {}
tunps = data['TunnelProfiles']
for tunp in tunps:
    payload["id"]=tunp["id"]
    payload["df_policy"]=tunp["df_policy"]
    payload["enable_perfect_forward_secrecy"]=tunp["enable_perfect_forward_secrecy"]
    payload["dh_groups"]=tunp["dh_groups"]
    payload["digest_algorithms"]=tunp["digest_algorithms"]
    payload["encryption_algorithms"]=tunp["encryption_algorithms"]
    payload["sa_life_time"]=tunp["sa_life_time"]
    payload["resource_type"]=tunp["resource_type"]
    payload["display_name"]=tunp["display_name"]
    tunpurl= '%s/%s' %(tunnelprofurl,tunp["id"])
    json_data = json.dumps(payload)
    createtunpresp = requests.put(tunpurl,headers=headers,data=json_data)
    print(createtunpresp.text)
    payload = {}
print(data['BGPNeighbors'][0]['resource_type'])
payload = {}
bgpns = data['BGPNeighbors']
for bgpn in bgpns:
    payload["id"]=bgpn["id"]
    payload["neighbor_address"]=bgpn["neighbor_address"]
    payload["remote_as_num"]=bgpn["remote_as_num"]
    payload["route_filtering"]=bgpn["route_filtering"]
    payload["keep_alive_time"]=bgpn["keep_alive_time"]
    payload["hold_down_time"]=bgpn["hold_down_time"]
    payload["allow_as_in"]=bgpn["allow_as_in"]
    payload["maximum_hop_limit"]=bgpn["maximum_hop_limit"]
    payload["resource_type"]=bgpn["resource_type"]
    payload["display_name"]=bgpn["display_name"]
    payload["marked_for_delete"]=bgpn["marked_for_delete"]
    payload["overridden"]=bgpn["overridden"]
    bgpnurl= '%s/%s' %(bgpneighborurl,bgpn["id"])
    json_data = json.dumps(payload)
    createbgpnresp = requests.put(bgpnurl,headers=headers,data=json_data)
    print(createbgpnresp.text)
    payload = {}

print(data['L3VPNSessions'][0]['resource_type'])

payload = {}
l3vpns = data['L3VPNSessions']
for l3vpn in l3vpns:
    payload["id"]=l3vpn["id"]
    if l3vpn.get("tunnel_interfaces"):
        tunint = []
        ipsubnets = []
        ipaddresses = []
        for intf in l3vpn["tunnel_interfaces"]:
            #print("l3vpn: "+repr(l3vpn))
            tunint_temp = {}
            for ipsub in intf["ip_subnets"]:
                ipsub_temp = {}
                for ipaddr in ipsub["ip_addresses"]:
                    ipaddresses.append(ipaddr)
                ipsub_temp["ip_addresses"] = ipaddresses
                ipsub_temp["prefix_length"] = ipsub["prefix_length"]
            ipsubnets.append(ipsub_temp)
            #print("IP Subnets"+repr(ipsubnets))
            tunint_temp["ip_subnets"]=ipsubnets
            tunint_temp["resource_type"]=intf["resource_type"]
            tunint_temp["id"]=intf["id"]
            tunint_temp["display_name"]=intf["display_name"]
            tunint.append(tunint_temp)
    payload["tunnel_interfaces"] = tunint
    #print("Tunnel Interfaces"+repr(tunint))	
            		
    if l3vpn.get("rules"):
        payload["rules"]=l3vpn["rules"]
    if l3vpn.get("authentication_mode"):
        payload["authentication_mode"]=l3vpn["authentication_mode"]
    if l3vpn.get("compliance_suite"):
        payload["compliance_suite"]=l3vpn["compliance_suite"]
    if l3vpn.get("connection_initiation_mode"):
        payload["connection_initiation_mode"]=l3vpn["connection_initiation_mode"]
    if l3vpn.get("display_name"):
        payload["display_name"]=l3vpn["display_name"]
    payload["enabled"]=l3vpn["enabled"]
    if l3vpn.get("local_endpoint_path"):
        payload["local_endpoint_path"]=l3vpn["local_endpoint_path"]
    if l3vpn.get("peer_address"):
        payload["peer_address"]=l3vpn["peer_address"]
    if l3vpn.get("peer_id"):
        payload["peer_id"]=l3vpn["peer_id"]	
    if l3vpn.get("psk"):
    payload["psk"]=l3vpn["psk"]
    payload["resource_type"]=l3vpn["resource_type"]
    if l3vpn.get("tunnel_profile_path"):
        payload["tunnel_profile_path"]=l3vpn["tunnel_profile_path"]
    if l3vpn.get("ike_profile_path"):
        payload["ike_profile_path"]=l3vpn["ike_profile_path"]
    if l3vpn.get("dpd_profile_path"):
        payload["dpd_profile_path"]=l3vpn["dpd_profile_path"]
    #print("Payload: "+repr(payload))
    l3vpnurl= '%s/%s' %(l3vpnsessionurl,l3vpn["id"])
    json_data = json.dumps(payload)
    createl3vpnresp = requests.put(l3vpnurl,headers=headers,data=json_data)
    print(createl3vpnresp.text)
    payload = {}
	
print(data['L2VPNSessions'][0]['resource_type'])
payload = {}
l2vpns = data['L2VPNSessions']
for l2vpn in l2vpns:
    payload["id"]=l2vpn["id"]
    payload["transport_tunnels"]=l2vpn["transport_tunnels"]
    payload["enabled"]=l2vpn["enabled"]
    payload["tunnel_encapsulation"]=l2vpn["tunnel_encapsulation"]
    payload["resource_type"]=l2vpn["resource_type"]
    payload["display_name"]=l2vpn["display_name"]
    payload["overridden"]=l2vpn["overridden"]
    l2vpnurl= '%s/%s' %(l2vpnsessionurl,l2vpn["id"])
    json_data = json.dumps(payload)
    createl2vpnresp = requests.put(l2vpnurl,headers=headers,data=json_data)
    print(createl2vpnresp.text)
    payload = {}
# Closing file 
f.close() 