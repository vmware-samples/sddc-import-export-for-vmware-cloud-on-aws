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

sfwDump = open("sourceRules.json", "a+")
### Get Source MGW Groups ###
print("{\"MGWGroups\": [")
mgroupsresp = requests.get(smgwgroupsurl,headers=headers)
mg = json.loads(mgroupsresp.text)
mgroups = mg["results"]
if mg["result_count"] > pageSize:
    curCursor = mg["cursor"]
    smgwgroupsurl = '%s/policy/api/v1/infra/domains/mgw/groups?page_size=%s&cursor=%s' %(srevproxyurl,pageSize,curCursor)
    while "cursor" in mg:
        mgroupsresp = requests.get(smgwgroupsurl,headers=headers)
        mg = json.loads(mgroupsresp.text)
        mgroups = mg["results"]
        if "cursor" in mg:
            curCursor = mg["cursor"]
        smgwgroupsurl = '%s/policy/api/v1/infra/domains/mgw/groups?page_size=%s&cursor=%s' %(srevproxyurl,pageSize,curCursor)
        ### Filter out system groups ###
        index = 0
        count = 0
        for group in mgroups:
            if group["_create_user"]!= "admin" and group["_create_user"]!="admin;admin":
                count = count + 1
        for group in mgroups:
            if group["_create_user"]!= "admin" and group["_create_user"]!="admin;admin":
                #print("Index..... Item Value: "+repr(index),mgroups[index])
                print(json.dumps(group,indent=4),end = "")
                if(count-1 > index):
                    print(",")
                index = index + 1
index = 0
count = 0
for group in mgroups:
    if group["_create_user"]!= "admin" and group["_create_user"]!="admin;admin":
	    count = count + 1

for group in mgroups:
            if group["_create_user"]!= "admin" and group["_create_user"]!="admin;admin":
                #print("Index..... Item Value: "+repr(index),mgroups[index])
                print(json.dumps(group,indent=4),end="")
                if(count-1 > index):
                    print(",")
                index = index + 1
print("],")

### Get Source CGW Groups ###
cgroupsresp = requests.get(scgwgroupsurl,headers=headers)
cg = json.loads(cgroupsresp.text)
cgroups = cg["results"]

### Filter out system groups ###
print("\"CGWGroups\": [")
if cg["result_count"] > pageSize:
    curCursor = cg["cursor"]
    scgwgroupsurl = '%s/policy/api/v1/infra/domains/cgw/groups?page_size=%s&cursor=%s' %(srevproxyurl,pageSize,curCursor)
    while "cursor" in cg:
        cgroupsresp = requests.get(scgwgroupsurl,headers=headers)
        cg = json.loads(cgroupsresp.text)
        cgroups = cg["results"]
        if "cursor" in cg:
            curCursor = cg["cursor"]
        scgwgroupsurl = '%s/policy/api/v1/infra/domains/cgw/groups?page_size=%s&cursor=%s' %(srevproxyurl,pageSize,curCursor)
        ### Filter out system groups ###
        index = 0
        count = 0
        for group in cgroups:
            if group["_create_user"]!= "admin" and group["_create_user"]!="admin;admin":
                count = count + 1
        for group in cgroups:
            if group["_create_user"]!= "admin" and group["_create_user"]!="admin;admin":
                print(json.dumps(group,indent=4),end="")
                if(count-1 > index):
                    print(",")
                index = index + 1
index = 0
count = 0
for group in cgroups:
    if group["_create_user"]!= "admin" and group["_create_user"]!="admin;admin":
	    count = count + 1
for group in cgroups:
    if group["_create_user"]!= "admin" and group["_create_user"]!="admin;admin":
        print(json.dumps(group,indent=4),end="")
        if(count-1 > index):
            print(",")
        index = index + 1
print("],")
### Get Source SDDC Firewall Services ###
servicesresp = requests.get(sservicesurl,headers=headers)
srv = json.loads(servicesresp.text)
services = srv["results"]
user_service_count = 0
### Filter out system Services ###
for service in services:
    if service["_create_user"]!= "admin" and service["_create_user"]!="admin;admin" and service["_create_user"]!="system":
        user_service_count = user_service_count + 1
#print("Result Count for Services: "+repr(user_service_count))
if(user_service_count > 0):
    print("\"Services\": [")
if srv["result_count"] > pageSize:
    curCursor = srv["cursor"]
    sservicesurl = '%s/policy/api/v1/infra/services?page_size=%s&cursor=%s' %(srevproxyurl,pageSize,curCursor)
    while "cursor" in srv:
        servicesresp = requests.get(sservicesurl,headers=headers)
        srv = json.loads(servicesresp.text)
        services = srv["results"]
        if "cursor" in srv:
            curCursor = srv["cursor"]
        sservicesurl = '%s/policy/api/v1/infra/services?page_size=%s&cursor=%s' %(srevproxyurl,pageSize,curCursor)
        ### Filter out system services ###
        index = 0
        count = 0
        for service in services:
            if service["_create_user"]!= "admin" and service["_create_user"]!="admin;admin" and service["_create_user"]!="system":
                count = count + 1
        for service in services:
            if service["_create_user"]!= "admin" and service["_create_user"]!="admin;admin" and service["_create_user"]!="system":
                print(json.dumps(service,indent=4),end="")
                if(count-1 > index):
                    print(",")
                index = index + 1

index = 0
count = 0
for service in services:
    if service["_create_user"]!= "admin" and service["_create_user"]!="admin;admin" and service["_create_user"]!="system":
	    count = count + 1				
for service in services:
    if service["_create_user"]!= "admin" and service["_create_user"]!="admin;admin" and service["_create_user"]!="system":
        print(json.dumps(service,indent=4))
        if(count-1 > index):
            print(",")
        index = index + 1
if(user_service_count > 0):
    print("],")

### Get Management Gateway Firewall Rules ###
mgwresponse = requests.get(smgwurl,headers=headers)
m = json.loads(mgwresponse.text)
mgwrules = m["results"]

### Filter out system Rules ###
curCursor = ''
print("\"MGWRules\": [")
index = 0
count = 0
for rule in mgwrules:
    if rule["_create_user"]!= "admin" and rule["_create_user"]!="admin;admin" and rule["_create_user"]!="system":
	    count = count + 1
for rule in mgwrules:
    if rule["_create_user"]!= "admin" and rule["_create_user"]!="admin;admin" and rule["_create_user"]!="system":
        print(json.dumps(rule,indent=4),end="")
        if(count-1 > index):
            print(",")
        index = index + 1
print("],")
### Get Compute Gateway Firewall Rules ###
cgwresponse = requests.get(scgwurl,headers=headers)
c = json.loads(cgwresponse.text)
cgwrules = c["results"]

### Filter out system Rules ###
print("\"CGWRules\": [")
index = 0
count = 0
for rule in cgwrules:
    if rule["_create_user"]!= "admin" and rule["_create_user"]!="admin;admin" and rule["_create_user"]!="system":
	    count = count + 1
for rule in cgwrules:
    if rule["_create_user"]!= "admin" and rule["_create_user"]!="admin;admin" and rule["_create_user"]!="system":
        print(json.dumps(rule,indent=4),end="")
        if(count-1 > index):
            print(",")
        index = index + 1
print("],")
### Get Source Distributed Firewall Rules ###
#print("DFW URL: "+sdfwurl)
dfwresponse = requests.get(sdfwurl,headers=headers)
d = json.loads(dfwresponse.text)
#print('DFW Comms Map: '+str(d))
cmaps = d["results"]
print("\"DFWRules\": [")
index = 0
count = 0
for cmap in cmaps:
    requrl = "%s/%s" %(sdfwurl,cmap["id"])
    cmapDetails = requests.get(requrl,headers=headers)
    count = count + 1
for cmap in cmaps:
    requrl = "%s/%s" %(sdfwurl,cmap["id"])
    cmapDetails = requests.get(requrl,headers=headers)
    cmapd = json.loads(cmapDetails.text)
    print(cmapDetails.text,end="")
    if(count-1 > index):
        print(",")
    index = index + 1
print("],")
    
### Get VPN IKE Profiles ###

ikeprofresponse = requests.get(ikeprofurl,headers=headers)
ikep = json.loads(ikeprofresponse.text)
ikeprofiles = ikep["results"]

### Filter out system profiles ###
curCursor = ''
print("\"IKEProfiles\": [")
index = 0
count = 0
for ikeprofile in ikeprofiles:
    if ikeprofile["_create_user"]!= "admin" and ikeprofile["_create_user"]!="admin;admin" and ikeprofile["_create_user"]!="system":
	    count = count + 1
for ikeprofile in ikeprofiles:
    if ikeprofile["_create_user"]!= "admin" and ikeprofile["_create_user"]!="admin;admin" and ikeprofile["_create_user"]!="system":
        print(json.dumps(ikeprofile,indent=4),end="")
        if(count-1 > index):
            print(",")
    index = index + 1
print("],")
		
### Get VPN Tunnel Profiles ###

tunprofresponse = requests.get(tunnelprofurl,headers=headers)
tunp = json.loads(tunprofresponse.text)
tunprofiles = tunp["results"]

### Filter out system profiles ###
curCursor = ''
print("\"TunnelProfiles\": [")
index = 0
count = 0
for tunprofile in tunprofiles:
    if tunprofile["_create_user"]!= "admin" and tunprofile["_create_user"]!="admin;admin" and tunprofile["_create_user"]!="system":
	    count = count + 1
for tunprofile in tunprofiles:
    if tunprofile["_create_user"]!= "admin" and tunprofile["_create_user"]!="admin;admin" and tunprofile["_create_user"]!="system":
        print(json.dumps(tunprofile,indent=4),end="")
        if(count-1 > index):
            print(",")
    index = index + 1
print("],")

### Get BGP Neighbors for Route Based VPN's  ###

bgpnresponse = requests.get(bgpneighborurl,headers=headers)
bgn = json.loads(bgpnresponse.text)
bgpns = bgn["results"]

### Filter out system BGP Neighbors ###
curCursor = ''
print("\"BGPNeighbors\": [")
index = 0
count = 0
for bgpn in bgpns:
    if bgpn["_create_user"]!= "admin" and bgpn["_create_user"]!="admin;admin" and bgpn["_create_user"]!="system":
	    count = count + 1
for bgpn in bgpns:
    if bgpn["_create_user"]!= "admin" and bgpn["_create_user"]!="admin;admin" and bgpn["_create_user"]!="system":
        print(json.dumps(bgpn,indent=4),end="")
        if(count-1 > index):
            print(",")
    index = index + 1
print("],")

### Get L2VPN Sessions ###

l2vpnsresponse = requests.get(l2vpnsessionurl,headers=headers)
l2v = json.loads(l2vpnsresponse.text)
l2vpns = l2v["results"]

### Filter out system profiles ###
curCursor = ''
print("\"L2VPNSessions\": [")
index = 0
count = 0
for l2vpn in l2vpns:
    if l2vpn["_create_user"]!= "admin" and l2vpn["_create_user"]!="admin;admin" and l2vpn["_create_user"]!="system":
	    count = count + 1
for l2vpn in l2vpns:
    if l2vpn["_create_user"]!= "admin" and l2vpn["_create_user"]!="admin;admin" and l2vpn["_create_user"]!="system":
        print(json.dumps(l2vpn,indent=4),end="")
        if(count-1 > index):
            print(",")
    index = index + 1
print("],")

### Get L3VPN Sessions ###

l3vpnsresponse = requests.get(l3vpnsessionurl,headers=headers)
l3v = json.loads(l3vpnsresponse.text)
l3vpns = l3v["results"]

### Filter out system profiles ###
curCursor = ''
print("\"L3VPNSessions\": [")
index = 0
count = 0
for l3vpn in l3vpns:
    if l3vpn["_create_user"]!= "admin" and l3vpn["_create_user"]!="admin;admin" and l3vpn["_create_user"]!="system":
	    count = count + 1

for l3vpn in l3vpns:
    if l3vpn["_create_user"]!= "admin" and l3vpn["_create_user"]!="admin;admin" and l3vpn["_create_user"]!="system":
        session_id = l3vpn["id"]
        l3vpnsessionpskurl = '%s/policy/api/v1/infra/tier-0s/vmc/locale-services/default/ipsec-vpn-services/default/sessions/%s?action=show_sensitive_data' %(srevproxyurl,session_id)
        l3vpnpskresponse = requests.get(l3vpnsessionpskurl,headers=headers)
        l3vpsk = json.loads(l3vpnpskresponse.text)
        l3vpn["psk"] = l3vpsk["psk"]
        print(json.dumps(l3vpn,indent=4),end="")
        if(count-1 > index):
            print(",")
    index = index + 1
print("]}")