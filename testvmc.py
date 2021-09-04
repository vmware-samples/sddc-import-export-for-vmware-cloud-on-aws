from vmc import VMCConnection

refresh_token = ''
org_id = ''
sddc_id = ''
vmcconn = VMCConnection(refresh_token,org_id,sddc_id)
access_token = vmcconn.getAccessToken()
print(access_token)
proxy = vmcconn.getNSXTproxy()
print(proxy)