from vmc import VMCConnection, VMCSDDC, JSONResponse

refresh_token = ''
org_id = ''
sddc_id = ''
#vmcconn = VMCConnection(refresh_token,org_id,sddc_id)
vmcsddc = VMCSDDC(refresh_token, org_id, sddc_id)
#print(vmcsddc.vmcconn.proxy_url)
#retval = vmcsddc.exportSDDCCGWRule()
retval = vmcsddc.getSDDCCGWRule('easyavi_inbound_vsHttps')
if retval.success:
    print(retval.json_body)
else:
    print("Could not retrieve CGW firewall rule. Error:", retval.last_response)

retval = vmcsddc.getSDDCCGWRules()
if retval.success:
    print(retval.json_body)
else:
    print("Could not retrieve CGW firewall rules. Error:", retval.last_response)
#print(json_response)
#access_token = vmcconn.getAccessToken()
#print(access_token)
#proxy = vmcconn.getNSXTproxy()
#print(proxy)