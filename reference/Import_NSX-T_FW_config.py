### Package Imports ####
import requests
import json
### Source SDDC/ORG Details ###
refreshtoken = '782b3de3-1539-411a-804f-85cdb1b0112a'
orgid = 'e74b1b6c-bccc-4367-8857-5b58fa5c481e'
ssddcid = '5c7ad558-df93-4b76-84a3-322e87445ac1'
dsddcid = '46e0b8ed-d7b7-4226-bb4f-60b9d0931a69'
#srevproxyurl = 'https://nsx-52-35-12-202.rp.vmwarevmc.com/vmc/reverse-proxy/api'
#drevproxyurl = 'https://nsx-35-155-169-225.rp.vmwarevmc.com/vmc/reverse-proxy/api'
print("Please hit Enter to accept the defaults.")
refreshtoken = input("Enter the Refresh Token ["+refreshtoken+"]:") or refreshtoken
orgid = input("Enter the Org Id ["+orgid+"]:") or orgid
ssddcid = input("Enter the Source SDDC Id ["+ssddcid+"]:") or ssddcid
dsddcid = input("Enter the Destination SDDC Id ["+dsddcid+"]:") or dsddcid
#srevproxyurl = input("Enter the Source Reverse Proxy URL ["+srevproxyurl+"]:") or srevproxyurl
#drevproxyurl = input("Enter the Destination Reverse Proxy URL ["+drevproxyurl+"]:") or drevproxyurl
### Access Token ###
authurl = 'https://console.cloud.vmware.com/csp/gateway/am/api/auth/api-tokens/authorize?refresh_token=%s' % (refreshtoken)
headers = {'Accept': 'application/json'}
payload = {}
authresp = requests.post(authurl,headers=headers,data=payload)
authjson = json.loads(authresp.text)
token = authjson["access_token"]
### Get Source ReverseProxy URL ###
infourl = 'https://vmc.vmware.com/vmc/api/orgs/%s/sddcs/%s' %(orgid,ssddcid)
headers = {'csp-auth-token': token, 'content-type': 'application/json'}
payload = {}
sddcresp = requests.get(infourl,headers=headers,data=payload)
sddcjson = json.loads(sddcresp.text)
srevproxyurl = sddcjson["resource_config"]["nsx_api_public_endpoint_url"]
### Get Destination ReverseProxy URL ###
infourl = 'https://vmc.vmware.com/vmc/api/orgs/%s/sddcs/%s' %(orgid,dsddcid)
headers = {'csp-auth-token': token, 'content-type': 'application/json'}
payload = {}
sddcresp = requests.get(infourl,headers=headers,data=payload)
sddcjson = json.loads(sddcresp.text)
drevproxyurl = sddcjson["resource_config"]["nsx_api_public_endpoint_url"]
### Source SDDC URL's ###
smgwgroupsurl = '%s/orgs/%s/sddcs/%s/sks-nsxt-manager/policy/api/v1/infra/domains/mgw/groups' %(srevproxyurl,orgid,ssddcid)
scgwgroupsurl = '%s/orgs/%s/sddcs/%s/sks-nsxt-manager/policy/api/v1/infra/domains/cgw/groups' %(srevproxyurl,orgid,ssddcid)
scgwurl = '%s/orgs/%s/sddcs/%s/sks-nsxt-manager/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules' %(srevproxyurl,orgid,ssddcid)
smgwurl = '%s/orgs/%s/sddcs/%s/sks-nsxt-manager/policy/api/v1/infra/domains/mgw/gateway-policies/default/rules' %(srevproxyurl,orgid,ssddcid)
sservicesurl = '%s/orgs/%s/sddcs/%s/sks-nsxt-manager/policy/api/v1/infra/services' %(srevproxyurl,orgid,ssddcid)
sdfwurl = '%s/orgs/%s/sddcs/%s/sks-nsxt-manager/policy/api/v1/infra/domains/cgw/communication-maps' %(srevproxyurl,orgid,ssddcid)
### Destination SDDC URL's ###
dmgwgroupsurl = '%s/orgs/%s/sddcs/%s/sks-nsxt-manager/policy/api/v1/infra/domains/mgw/groups' %(drevproxyurl,orgid,dsddcid)
dcgwgroupsurl = '%s/orgs/%s/sddcs/%s/sks-nsxt-manager/policy/api/v1/infra/domains/cgw/groups' %(drevproxyurl,orgid,dsddcid)
dcgwurl = '%s/orgs/%s/sddcs/%s/sks-nsxt-manager/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules' %(drevproxyurl,orgid,dsddcid)
dmgwurl = '%s/orgs/%s/sddcs/%s/sks-nsxt-manager/policy/api/v1/infra/domains/mgw/gateway-policies/default/rules' %(drevproxyurl,orgid,dsddcid)
dmgwupdurl = '%s/orgs/%s/sddcs/%s/sks-nsxt-manager/policy/api/v1/infra/domains/mgw/gateway-policies/default/rules' %(drevproxyurl,orgid,dsddcid)
dcgwupdurl = '%s/orgs/%s/sddcs/%s/sks-nsxt-manager/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules' %(drevproxyurl,orgid,dsddcid)
dservicesurl = '%s/orgs/%s/sddcs/%s/sks-nsxt-manager/policy/api/v1/infra/services' %(drevproxyurl,orgid,dsddcid)
ddfwurl = '%s/orgs/%s/sddcs/%s/sks-nsxt-manager/policy/api/v1/infra/domains/cgw/communication-maps' %(drevproxyurl,orgid,dsddcid)
headers = {'csp-auth-token': token, 'content-type': 'application/json'}
sfwDump = open("sourceRules.json", "a+")
### Get Source MGW Groups ###
mgroupsresp = requests.get(smgwgroupsurl,headers=headers)
mg = json.loads(mgroupsresp.text)
mgroups = mg["results"]
sfwDump.write(mgroupsresp.text)
#print('MGW Groups: ')
#f = open("migrationSummary.txt", "w+")
f = open("migrationSummary.txt", "a+")
print('Beginning the Firewall Rules Migration now....... ')
### Create Destination MGW Groups ###
payload = {}
print ("Created Management Gateway Groups: ")
for group in mgroups:
    if group["_create_user"]!= "admin" and group["_create_user"]!="admin;admin":
        payload["id"]=group["id"]
        payload["resource_type"]=group["resource_type"]
        payload["display_name"]=group["display_name"]
        payload["expression"]=group["expression"]
        mgwgroupsurl= '%s/%s' %(dmgwgroupsurl,group["id"])
        json_data = json.dumps(payload)
        creategrpresp = requests.put(mgwgroupsurl,headers=headers,data=json_data)
        print(creategrpresp.text)
        f.write(creategrpresp.text)
        payload = {}
### Get Source CGW Groups ###
cgroupsresp = requests.get(scgwgroupsurl,headers=headers)
cg = json.loads(cgroupsresp.text)
cgroups = cg["results"]
sfwDump.write(cgroupsresp.text)
#print('CGW Groups: ')
#for group in cgroups:
#    print(group["display_name"])
#    print(group["expression"])
### Create Destination CGW Groups ###
print('Created Compute Gateway Groups: ')
payload = {}
for group in cgroups:
    if group["_create_user"]!= "admin" and group["_create_user"]!="admin;admin":
        payload["id"]=group["id"]
        payload["resource_type"]=group["resource_type"]
        payload["display_name"]=group["display_name"]
        payload["expression"]=group["expression"]
        cgwgroupsurl= '%s/%s' %(dcgwgroupsurl,group["id"])
        json_data = json.dumps(payload)
        creategrpresp = requests.put(cgwgroupsurl,headers=headers,data=json_data)
        print(creategrpresp.text)
        f.write(creategrpresp.text)
        payload = {}
        
### Get Source SDDC Firewall Services ###
servicesresp = requests.get(sservicesurl,headers=headers)
srv = json.loads(servicesresp.text)
services = srv["results"]
sfwDump.write(servicesresp.text)
#print('Source Services: ')
### Create Destination SDDC Firewall Services ###
print('Created Firewall Services in destination SDDC: ')
payload = {}
for service in services:
    if service["_create_user"]!= "admin" and service["_create_user"]!="admin;admin" and service["_create_user"]!="system":
        payload["id"]=service["id"]
        payload["resource_type"]=service["resource_type"]
        payload["display_name"]=service["display_name"]
        payload["service_entries"]=service["service_entries"]
        servicessurl= '%s/%s' %(dservicesurl,service["id"])
        json_data = json.dumps(payload)
        createsrvresp = requests.put(servicessurl,headers=headers,data=json_data)
        print(createsrvresp.text)
        f.write(createsrvresp.text)
        payload = {}
### Get Management Gateway Firewall Rules ###    
mgwresponse = requests.get(smgwurl,headers=headers)
m = json.loads(mgwresponse.text)
#print('MGW Rules: ')
mgwrules = m["results"]
sfwDump.write(mgwresponse.text)
#for rule in mgwrules:
#    print(rule["display_name"])
#    print(rule["source_groups"])
#    print(rule["destination_groups"])
#    print(rule["services"])
#    print(rule["action"])
    
### Create Destination MGW FW Rules ###
payload = {}
for rule in mgwrules:
    if rule["_create_user"]!= "admin" and rule["_create_user"]!="admin;admin" and rule["_create_user"]!="system":
        payload["id"]=rule["id"]
        if rule.get("tags"):
            payload["tags"] = rule["tags"]
        if rule.get("description"):
            payload["description"] = rule["description"]
        payload["source_groups"] = rule["source_groups"]
        payload["resource_type"]=rule["resource_type"]
        payload["display_name"]=rule["display_name"]
        payload["scope"]=rule["scope"]
        payload["action"]=rule["action"]
        payload["services"]=rule["services"]
        payload["destination_groups"]=rule["destination_groups"]
        mgwfwurl= '%s/%s' %(dmgwupdurl,rule["id"])
        json_data = json.dumps(payload)
        createfwruleresp = requests.put(mgwfwurl,headers=headers,data=json_data)
        print(createfwruleresp.text)
        f.write(createfwruleresp.text)
        payload = {}
    
### Get Compute Gateway Firewall Rules ###
cgwresponse = requests.get(scgwurl,headers=headers)
c = json.loads(cgwresponse.text)
#print('CGW Rules: ')
cgwrules = c["results"]
sfwDump.write(cgwresponse.text)
#for rule in cgwrules:
#    print(rule["display_name"])
#    print(rule["source_groups"])
#    print(rule["destination_groups"])
#    print(rule["services"])
#    print(rule["action"])
    
### Create Destination Compute Gateway Firewall Rules ###
print('Created Compute Gateway Firewall Rules: ')
payload = {}
for rule in cgwrules:
    if rule["_create_user"]!= "admin" and rule["_create_user"]!="admin;admin" and rule["_create_user"]!="system":
        payload["id"]=rule["id"]
        if rule.get("tags"):
            payload["tags"] = rule["tags"]
        if rule.get("description"):
            payload["description"] = rule["description"]
        payload["source_groups"] = rule["source_groups"]
        payload["resource_type"]=rule["resource_type"]
        payload["display_name"]=rule["display_name"]
        payload["scope"]=rule["scope"]
        payload["action"]=rule["action"]
        payload["services"]=rule["services"]
        payload["destination_groups"]=rule["destination_groups"]
        cgwfwurl= '%s/%s' %(dcgwupdurl,rule["id"])
        json_data = json.dumps(payload)
        createfwruleresp = requests.put(cgwfwurl,headers=headers,data=json_data)
        print(createfwruleresp.text)
        f.write(createfwruleresp.text)
        payload = {}
        
### Get Source Distributed Firewall Rules ###
dfwresponse = requests.get(sdfwurl,headers=headers)
d = json.loads(dfwresponse.text)
#print('DFW Comms Map: ')
cmaps = d["results"]
sfwDump.write(dfwresponse.text)
print('Created Distributed Firewall Rules: ')
payload = {}
for cmap in cmaps:
    requrl = "%s/%s" %(sdfwurl,cmap["id"])
    cmapDetails = requests.get(requrl,headers=headers)
    cmapd = json.loads(cmapDetails.text)
    #print(cmapd)
    commEnts = cmapd["communication_entries"]
    sfwDump.write(cmapDetails.text)
    payload = {}
    payload["resource_type"] = cmapd["resource_type"]
    payload["id"] = cmapd["id"]
    payload["display_name"] = cmapd["display_name"]
    payload["category"] = cmapd["category"]
    payload["precedence"] = cmapd["precedence"]
   # payload["communication_entries"] = cmapd["communication_entries"]
    json_data = json.dumps(payload)
    drequrl = "%s/%s" %(ddfwurl,cmap["id"])
    createDfwRuleresp = requests.put(drequrl,headers=headers,data=json_data)
    print(createDfwRuleresp.text)
    f.write(createDfwRuleresp.text)
    payload = {}
    for commEnt in commEnts:
        payload["id"] = commEnt["id"]
        payload["display_name"] = commEnt["display_name"]
        payload["resource_type"] = commEnt["resource_type"]
        payload["source_groups"] = commEnt["source_groups"]
        payload["destination_groups"] = commEnt["destination_groups"]
        payload["scope"] = commEnt["scope"]
        payload["action"] = commEnt["action"]
        payload["services"] = commEnt["services"]
        centrequrl = "%s/%s/communication-entries/%s" %(ddfwurl,cmap["id"],commEnt["id"])
        json_data = json.dumps(payload)
        centDetails = requests.put(centrequrl,headers=headers,data=json_data)
        print(centDetails.text)
        f.write(centDetails.text)
        payload = {}
f.close()
print("############## Finished migrating the rules ##############")