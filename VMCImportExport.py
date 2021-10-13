# SDDC Import/Export for VMware Cloud on AWS


################################################################################
### Copyright 2020-2021 VMware, Inc.
### SPDX-License-Identifier: BSD-2-Clause
################################################################################


import configparser                     # parsing config file
import datetime
import glob
import json
import requests                         # need this for Get/Post/Delete
import os
import re
import time
import sys

from pathlib import Path
from prettytable import PrettyTable
from zipfile import ZipFile

class VMCImportExport:
    """A class to handle importing and exporting portions of a VMC SDDC"""

    def __init__(self,configPath="./config_ini/config.ini", vmcConfigPath="./config_ini/vmc.ini", awsConfigPath="./config/aws.ini", vCenterConfigPath="./config_ini/vcenter.ini"):
        self.access_token = None
        self.proxy_url = None
        self.proxy_url_short = None
        self.lastJSONResponse = None
        self.source_org_display_name = ""
        self.dest_org_display_name = ""
        self.source_sddc_name = ""
        self.source_sddc_version = ""
        self.source_sddc_state = ""
        self.source_sddc_info = ""
        self.sddc_info_hide_sensitive_data = True
        self.gov_cloud_urls = False
        self.dest_sddc_name = ""
        self.dest_sddc_version = ""
        self.dest_sddc_state = ""
        self.configPath = configPath
        self.vmcConfigPath = vmcConfigPath
        self.awsConfigPath = awsConfigPath
        self.vCenterConfigPath = vCenterConfigPath
        self.export_folder = ""
        self.import_folder = ""
        self.sync_mode = False
        self.export_path = ""
        self.import_path = ""
        self.append_sddc_id_to_zip = False
        self.export_zip_name = ""
        self.export_history = False
        self.export_purge_before_run = False
        self.export_purge_after_zip = False
        self.max_export_history_files = 10
        self.export_type = 'os'
        self.aws_s3_export_access_id = ""
        self.aws_s3_export_access_secret = ""
        self.aws_s3_export_bucket = ""
        self.cgw_groups_import_exclude_list = []
        self.cgw_import_exclude_list = []
        self.mgw_groups_import_exclude_list = []
        self.mgw_import_exclude_list = []
        self.network_import_exclude_list = []
        self.export_vcenter_folders = False
        self.import_vcenter_folders = False
        self.user_search_results_json = ""
        self.convertedServiceRolePayload = ""
        self.RoleSyncSourceUserEmail = ""
        self.RoleSyncDestUserEmails = {}
        self.ConfigLoader()

    def ConfigLoader(self):
        """Load all configuration variables from config.ini"""
        config = configparser.ConfigParser()
        vmcConfig = configparser.ConfigParser()
        awsConfig = configparser.ConfigParser()
        vCenterConfig = configparser.ConfigParser()
        config.read(self.configPath)
        vmcConfig.read(self.vmcConfigPath)
        awsConfig.read(self.awsConfigPath)
        vCenterConfig.read(self.vCenterConfigPath)

        self.gov_cloud_urls           = self.loadConfigFlag(vmcConfig,"vmcConfig","gov_cloud_urls")
        if self.gov_cloud_urls is True:
            self.strProdURL               = vmcConfig.get("vmcConfig", "strGovProdURL")
            self.strCSPProdURL            = vmcConfig.get("vmcConfig", "strGovCSPProdURL")
        else:
            self.strProdURL               = vmcConfig.get("vmcConfig", "strProdURL")
            self.strCSPProdURL            = vmcConfig.get("vmcConfig", "strCSPProdURL")
        self.source_refresh_token     = vmcConfig.get("vmcConfig", "source_refresh_token")
        self.source_org_id            = vmcConfig.get("vmcConfig", "source_org_id")
        self.source_sddc_id           = vmcConfig.get("vmcConfig", "source_sddc_id")
        self.dest_refresh_token       = vmcConfig.get("vmcConfig", "dest_refresh_token")
        self.dest_org_id              = vmcConfig.get("vmcConfig", "dest_org_id")
        self.dest_sddc_id             = vmcConfig.get("vmcConfig", "dest_sddc_id")
        self.import_mode              = config.get("importConfig","import_mode").lower()
        self.export_folder            = config.get("exportConfig","export_folder")
        self.import_folder            = config.get("importConfig","import_folder")
        self.export_path              = Path(self.export_folder)
        self.import_path              = Path(self.import_folder)
        self.sync_mode                = self.loadConfigFlag(config,"importConfig","sync_mode")
        self.export_history           = self.loadConfigFlag(config,"exportConfig","export_history")
        self.export_purge_before_run  = self.loadConfigFlag(config,"exportConfig","export_purge_before_run")
        self.export_purge_after_zip   = self.loadConfigFlag(config,"exportConfig","export_purge_after_zip")
        self.append_sddc_id_to_zip    = self.loadConfigFlag(config,"exportConfig","append_sddc_id_to_zip")

        self.max_export_history_files = int(config.get("exportConfig", "max_export_history_files"))
        self.export_type          = self.loadConfigFilename(config,"exportConfig","export_type")
        self.import_mode_live_warning = self.loadConfigFlag(config,"importConfig","import_mode_live_warning")

        # vCenter
        self.srcvCenterURL          =  vCenterConfig.get("vCenterConfig","srcvCenterURL")
        self.srcvCenterUsername     =  vCenterConfig.get("vCenterConfig","srcvCenterUsername")
        self.srcvCenterPassword     =  vCenterConfig.get("vCenterConfig","srcvCenterPassword")
        self.srcvCenterDatacenter   =  vCenterConfig.get("vCenterConfig","srcvCenterDatacenter")
        self.srcvCenterSSLVerify    =  self.loadConfigFlag(vCenterConfig,"vCenterConfig","srcvCenterSSLVerify")

        self.destvCenterURL         =  vCenterConfig.get("vCenterConfig","destvCenterURL")
        self.destvCenterUsername    =  vCenterConfig.get("vCenterConfig","destvCenterUsername")
        self.destvCenterPassword    =  vCenterConfig.get("vCenterConfig","destvCenterPassword")
        self.destvCenterDatacenter  =  vCenterConfig.get("vCenterConfig","destvCenterDatacenter")
        self.destvCenterSSLVerify   =  self.loadConfigFlag(vCenterConfig,"vCenterConfig","destvCenterSSLVerify")

        self.export_vcenter_folders = self.loadConfigFlag(config,"exportConfig","export_vcenter_folders")
        self.import_vcenter_folders = self.loadConfigFlag(config,"importConfig","import_vcenter_folders")

        self.vcenter_folders_filename = self.loadConfigFilename(config,"exportConfig","vcenter_folders_filename")

        #NSX manager
        self.srcNSXmgrURL               =  vCenterConfig.get("nsxConfig","srcNSXmgrURL")
        self.srcNSXmgrUsername          =  vCenterConfig.get("nsxConfig","srcNSXmgrUsername")
        self.srcNSXmgrPassword          =  vCenterConfig.get("nsxConfig","srcNSXmgrPassword")
        self.srcNSXmgrSSLVerify         =  self.loadConfigFlag(vCenterConfig,"nsxConfig","srcNSXmgrSSLVerify")

        #CGW
        self.cgw_export               = self.loadConfigFlag(config,"exportConfig","cgw_export")
        self.cgw_export_filename      = self.loadConfigFilename(config,"exportConfig","cgw_export_filename")
        self.cgw_import               = self.loadConfigFlag(config,"importConfig","cgw_import")
        self.cgw_import_filename      = self.loadConfigFilename(config,"importConfig","cgw_import_filename")
        self.cgw_import_exclude_list  = self.loadConfigRegex(config,"importConfig","cgw_import_exclude_list",'|')
        self.cgw_groups_import_exclude_list = self.loadConfigRegex(config,"importConfig","cgw_groups_import_exclude_list",'|')

        #MGW
        self.mgw_export          = self.loadConfigFlag(config,"exportConfig","mgw_export")
        self.mgw_export_filename = self.loadConfigFilename(config,"exportConfig","mgw_export_filename")
        self.mgw_import          = self.loadConfigFlag(config,"importConfig","mgw_import")
        self.mgw_import_filename = self.loadConfigFilename(config,"importConfig","mgw_import_filename")
        self.mgw_import_exclude_list = self.loadConfigRegex(config,"importConfig","mgw_import_exclude_list",'|')
        self.mgw_groups_import_exclude_list = self.loadConfigRegex(config,"importConfig","mgw_groups_import_exclude_list",'|')

        #Network segments - CGW
        self.network_export              = self.loadConfigFlag(config,"exportConfig","network_export")
        self.network_export_filename     = self.loadConfigFilename(config,"exportConfig","network_export_filename")
        self.network_dhcp_static_binding_export = self.loadConfigFilename(config,"exportConfig","network_dhcp_static_binding_export")
        self.network_dhcp_static_binding_filename = self.loadConfigFilename(config,"exportConfig","network_dhcp_static_binding_filename")
        self.CGWDHCPbindings = []
        self.network_import              = self.loadConfigFlag(config,"importConfig","network_import")
        self.network_import_filename     = self.loadConfigFilename(config,"importConfig","network_import_filename")
        self.network_dhcp_static_binding_import = self.loadConfigFlag(config,"importConfig","network_dhcp_static_binding_import")
        self.network_import_max_networks = int(config.get("importConfig", "network_import_max_networks"))
        self.network_import_exclude_list = self.loadConfigRegex(config,"importConfig","network_import_exclude_list",'|')

        #Public IP
        self.public_export           = self.loadConfigFlag(config,"exportConfig","public_export")
        self.public_export_filename  = self.loadConfigFilename(config,"exportConfig","public_export_filename")
        self.public_import           = self.loadConfigFlag(config,"importConfig","public_import")
        self.public_import_filename  = self.loadConfigFilename(config,"importConfig","public_import_filename")
        self.public_ip_old_new_filename = self.loadConfigFilename(config,"importConfig","public_ip_old_new_filename")

        #NAT
        self.nat_export           = self.loadConfigFlag(config,"exportConfig","nat_export")
        self.nat_export_filename  = self.loadConfigFilename(config,"exportConfig","nat_export_filename")
        self.nat_import           = self.loadConfigFlag(config,"importConfig","nat_import")
        self.nat_import_filename  = self.loadConfigFilename(config,"importConfig","nat_import_filename")

        #VPN
        self.vpn_export             = self.loadConfigFlag(config,"exportConfig","vpn_export")
        self.vpn_import             = self.loadConfigFlag(config,"importConfig","vpn_import")
        self.vpn_ike_filename       = self.loadConfigFilename(config,"importConfig","vpn_ike_filename")
        self.vpn_dpd_filename       = self.loadConfigFilename(config,"importConfig","vpn_dpd_filename")
        self.vpn_tunnel_filename    = self.loadConfigFilename(config,"importConfig","vpn_tunnel_filename")
        self.vpn_bgp_filename       = self.loadConfigFilename(config,"importConfig","vpn_bgp_filename")
        self.vpn_local_bgp_filename = self.loadConfigFilename(config,"importConfig","vpn_local_bgp_filename")
        self.vpn_l3_filename        = self.loadConfigFilename(config,"importConfig","vpn_l3_filename")
        self.vpn_l2_filename        = self.loadConfigFilename(config,"importConfig","vpn_l2_filename")
        self.vpn_disable_on_import  = self.loadConfigFlag(config,"importConfig","vpn_disable_on_import")

        #Service Access
        self.service_access_export  = self.loadConfigFlag(config,"exportConfig","service_access_export")
        self.service_access_import  = self.loadConfigFlag(config,"importConfig","service_access_import")
        self.service_access_filename = self.loadConfigFilename(config,"importConfig","service_access_filename")

        #Services
        self.services_filename      = self.loadConfigFilename(config,"importConfig","services_filename")

        #CGW groups
        self.cgw_groups_filename     = self.loadConfigFilename(config,"importConfig","cgw_groups_filename")

        #MGW groups
        self.mgw_groups_filename     = self.loadConfigFilename(config,"importConfig","mgw_groups_filename")

        #AWS
        self.aws_s3_export_access_id = self.loadConfigFilename(awsConfig,"awsConfig","aws_s3_export_access_id")
        self.aws_s3_export_access_secret = self.loadConfigFilename(awsConfig,"awsConfig","aws_s3_export_access_secret")
        self.aws_s3_export_bucket = self.loadConfigFilename(awsConfig,"awsConfig","aws_s3_export_bucket")

        #DFW
        self.dfw_export             = self.loadConfigFlag(config,"exportConfig","dfw_export")
        self.dfw_export_filename    = self.loadConfigFilename(config,"exportConfig","dfw_export_filename")
        self.dfw_detailed_export_filename = self.loadConfigFilename(config,"exportConfig","dfw_detailed_export_filename")
        self.dfw_import             = self.loadConfigFlag(config,"importConfig","dfw_import")
        self.dfw_import_filename    = self.loadConfigFilename(config,"importConfig","dfw_import_filename")
        self.dfw_detailed_import_filename = self.loadConfigFilename(config,"importConfig","dfw_detailed_import_filename")

        #SDDC Info
        self.sddc_info_filename     = self.loadConfigFilename(config,"exportConfig","sddc_info_filename")
        self.sddc_info_hide_sensitive_data = self.loadConfigFlag(config,"exportConfig","sddc_info_hide_sensitive_data")

        #CSP
        self.RoleSyncSourceUserEmail = config.get("exportConfig","role_sync_source_user_email")
        self.RoleSyncDestUserEmails = config.get("importConfig","role_sync_dest_user_emails").split('|')

    def purgeJSONfiles(self):
        """Removes the JSON export files before a new export"""
        files = glob.glob(self.export_folder + '/*.json')
        retval = True
        for filePath in files:
            try:
                os.remove(filePath)
                print('Deleted',filePath)
            except:
                print('Error deleting',filePath)
                retval = False
        return retval

    def zipJSONfiles(self):
        """Creates a zipfile of exported JSON files"""
        files = glob.glob(self.export_folder + '/*.json')
        curtime = datetime.datetime.now()
        #filename example: 2020-12-02_09-57-13_json-export.zip
        fname =  curtime.strftime("%Y-%m-%d_%H-%M-%S") + '_' + 'json-export.zip'
        if self.append_sddc_id_to_zip is True:
            fname = self.source_sddc_id + "_" + fname
        self.export_zip_name = fname
        try:
            ZipPath = self.export_folder + '/' + fname
            with ZipFile(ZipPath,'w') as zip:
                for file in files:
                    zip.write(file,os.path.basename(file))
            return True
        except Exception as e:
            print('Error writing zipfile: ', str(e))
            return False

    def unzipJSONfiles(self,sourceZipPath):
        """Unzip a JSON archive"""
        try:
            if os.path.exists(sourceZipPath) is False:
                print(sourceZipPath,'not found.')
                return False

            # This does not obey the import_folder
            with ZipFile(sourceZipPath,mode = 'r') as zip:
                zip.extractall(os.path.dirname(sourceZipPath))
            return True
        except Exception as e:
            print('Zipfile extraction error: ', str(e))
            return False

    def purgeJSONzipfiles(self):
        """Clean up old zipfiles"""
        if self.max_export_history_files == -1:
            print('Maximum zips configured as unlimited.')
            return True
        retval = True
        files = glob.glob(self.export_folder + '/*.zip')
        files.sort(key=os.path.getmtime)
        print(len(files), "zipfiles found with a configured maximum of",self.max_export_history_files)
        if len(files) > self.max_export_history_files:
            num_to_purge = len(files) - self.max_export_history_files
            print('Need to purge:',num_to_purge)
            for file in files[0:num_to_purge]:
                try:
                    os.remove(file)
                    print ('Purged', file)
                except Exception as e:
                    retval = False
                    print('Error purging:', file,str(e))
        return retval


    def exportOnPremGroups(self):
        """Exports the Groups to a JSON file"""
        myURL = (self.srcNSXmgrURL + "/policy/api/v1/infra/domains/default/groups")
        response = self.invokeNSXTGET(myURL)
        if response is None or response.status_code != 200:
            return False
        json_response = response.json()
        cgw_groups = json_response['results']
        fname = self.export_path / self.cgw_groups_filename
        with open(fname, 'w') as outfile:
            json.dump(cgw_groups, outfile,indent=4)
        return True


    def exportOnPremServices(self,OnlyUserDefinedServices=False):
        """Exports on-prem services to a JSON file
        Args: bool OnlyUserDefinedServices, default True, if you want to ignore predefined system services
        """
        myURL = (self.srcNSXmgrURL + "/policy/api/v1/infra/services")
        response = self.invokeNSXTGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        sddc_services = json_response['results']
        if OnlyUserDefinedServices is True:
            fname = self.export_path / self.services_filename
            with open(fname, 'w+') as outfile:
                for service in sddc_services:
                    if service["_create_user"]!= "admin" and service["_create_user"]!="admin;admin" and service["_create_user"]!="system":
                        json.dump(service, outfile,indent=4)
        else:
            fname = self.export_path / self.services_filename
            with open(fname, 'w') as outfile:
                json.dump(sddc_services, outfile,indent=4)
        return True

    def exportOnPremDFWRule(self):
        """Exports the on-prem firewall rules to a JSON file"""
        myURL = (self.srcNSXmgrURL + "/policy/api/v1/infra/domains/default/security-policies")
        response = self.invokeNSXTGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        sddc_DFWrules = json_response['results']
        sddc_Detailed_DFWrules = {}
        for cmap in sddc_DFWrules:
            myURL = self.srcNSXmgrURL + "/policy/api/v1/infra/domains/default/security-policies/" + cmap["id"] + "/rules"
            response = self.invokeNSXTGET(myURL)
            if response is None or response.status_code != 200:
                return False
            cmapDetails = response.json()
            sddc_Detailed_DFWrules[cmap["id"]] = cmapDetails
        fname = self.export_path / self.dfw_export_filename
        fname_detailed = self.export_path / self.dfw_detailed_export_filename
        with open(fname, 'w') as outfile:
            json.dump(sddc_DFWrules, outfile,indent=4)
        with open(fname_detailed, 'w') as outfile:
            json.dump(sddc_Detailed_DFWrules, outfile,indent=4)
        return True

    def importOnPremServices(self):
        """Import all services from a JSON file"""
        fname = self.import_path / self.services_filename
        try:
            with open(fname) as filehandle:
                services = json.load(filehandle)
        except:
            print('Import failed - unable to open',fname)
            return

        for service in services:
            json_data = {}
            if service["_create_user"]!="system":
                if self.import_mode == "live":
                    json_data["id"] = service["id"]
                    json_data["resource_type"]=service["resource_type"]
                    json_data["display_name"]=service["display_name"]
                    json_data["service_type"]=service["service_type"]
                    service_entries = []
                    for entry in service["service_entries"]:
                        #print("-------------------------------------------------")
                        #print("entry")
                        modified_entry = {}
                        for k in entry:
                            #print("-------------------------------------------------")
                            #print("sub_entry")
                            #print(k)
                            if k != "path"  and k != "relative_path" and k != "overridden" and k != "_create_time" and k != "_create_user" and k != "_last_modified_time" and k != "_last_modified_user" and k != "_system_owned" and k != "_protection" and k != "_revision":
                                modified_entry[k] = entry[k]
                        service_entries.append(modified_entry)
                    json_data["service_entries"]=service_entries
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                    myURL = self.proxy_url + "/policy/api/v1/infra/services/" + service["id"]
                    #print(myURL)
                    #print(json_data)
                    if self.sync_mode is True:
                        response = requests.patch(myURL, headers=myHeader, json=json_data)
                    else:
                        response = requests.put(myURL, headers=myHeader, json=json_data)
                    if response.status_code == 200:
                        result = "SUCCESS"
                        print('Added {}'.format(json_data['display_name']))
                    else:
                        result = "FAIL"
                        print( f'API Call Status {response.status_code}, text:{response.text}')
                else:
                    print("TEST MODE - Service",service["display_name"],"would have been imported.")

    def importOnPremGroup(self):
        """Import all CGW groups from a JSON file"""
        fname = self.import_path / self.cgw_groups_filename
        try:
            with open(fname) as filehandle:
                groups = json.load(filehandle)
        except:
            print('Import failed - unable to open',fname)
            return False

        payload = {}
        for group in groups:
            skip_vm_expression = False
            skip_group = False
            for e in self.cgw_groups_import_exclude_list:
                m = re.match(e,group["display_name"])
                if m:
                    print(group["display_name"],'skipped - matches exclusion regex', e)
                    skip_group = True
                    break
            if skip_group is True:
                continue
            payload["id"]=group["id"]
            payload["resource_type"]=group["resource_type"]
            payload["display_name"]=group["display_name"]
            if self.import_mode == "live":
                myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/groups/" + group["id"]
                if "expression" in group:
                    group_expression = group["expression"]
                    for item in group_expression:
                        if item["resource_type"] == "ExternalIDExpression":
                            skip_vm_expression = True
                            print(f'CGW Group {group["display_name"]} cannot be imported as it relies on VM external ID.')
                            break
                else:
                    continue
                if skip_vm_expression == False:
                    payload["expression"]=group["expression"]
                    json_data = json.dumps(payload)
                    if self.sync_mode is True:
                        creategrpresp = requests.patch(myURL,headers=myHeader,data=json_data)
                    else:
                        creategrpresp = requests.put(myURL,headers=myHeader,data=json_data)
                    print("CGW Group " + payload["display_name"] + " has been imported.")
                else:
                        continue
            else:
                print("TEST MODE - CGW Group " + payload["display_name"] + " would have been imported.")
            payload = {}
        return True

    def importOnPremDFWRule(self):
        """Import all DFW Rules from a JSON file"""
        fname = self.import_path / self.dfw_import_filename
        fname_detailed = self.import_path / self.dfw_detailed_import_filename
        try:
            with open(fname) as filehandle:
                cmaps = json.load(filehandle)
        except:
            print('Import failed - unable to open',fname)
            return False
        try:
            with open(fname_detailed) as filehandle:
                cmapd = json.load(filehandle)
        except:
            print('Import failed - unable to open',fname_detailed)
            return False

        for cmap in cmaps:
            if cmap["id"]!="default-layer3-section" and cmap["id"]!="default-layer2-section":
                payload = {}
                payload["resource_type"] = cmap["resource_type"]
                payload["id"] = cmap["id"]
                payload["display_name"] = cmap["display_name"]
                payload["category"] = cmap["category"]
                payload["sequence_number"] = cmap["sequence_number"]
                payload["stateful"] = cmap["stateful"]
                if self.import_mode == 'live':
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                    myURL = self.proxy_url_short + "/policy/api/v1/infra/domains/cgw/security-policies/" + cmap["id"]
                    json_data = json.dumps(payload)
                    if self.sync_mode is True:
                        response = requests.patch(myURL,headers=myHeader,data=json_data)
                    else:
                        response = requests.put(myURL,headers=myHeader,data=json_data)
                    self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'

                payload = {}
                cmap_id = cmap["id"]
                commEnts = cmapd[cmap_id]["results"]
                for commEnt in commEnts:
                    payload["id"] = commEnt["id"]
                    payload["display_name"] = commEnt["display_name"]
                    payload["resource_type"] = commEnt["resource_type"]
                    payload["source_groups"] = commEnt["source_groups"]
                    payload["destination_groups"] = commEnt["destination_groups"]
                    payload['source_groups'] = [group.replace('/infra/domains/default/groups', '/infra/domains/cgw/groups') for group in payload['source_groups']]
                    payload['destination_groups'] = [group.replace('/infra/domains/default/groups', '/infra/domains/cgw/groups') for group in payload['destination_groups']]
                    payload["destination_groups"]
                    if "scope" in commEnt:
                        payload["scope"] = commEnt["scope"]
                    payload["action"] = commEnt["action"]
                    payload["services"] = commEnt["services"]
                    payload["sequence_number"] = commEnt["sequence_number"]
                    payload["logged"] = commEnt["logged"]
                    payload["disabled"] = commEnt["disabled"]

                    if self.import_mode == 'live':
                        myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/security-policies/" + cmap["id"] + "/rules/" + commEnt["id"]
                        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                        json_data = json.dumps(payload)
                        if self.sync_mode is True:
                            response = requests.patch(myURL,headers=myHeader,data=json_data)
                        else:
                            response = requests.put(myURL,headers=myHeader,data=json_data)
                        if response.status_code == 200:
                            print("DFW rule " + commEnt["display_name"] + " has been imported.")
                        else:
                            self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
                            print(f'API Call Status {response.status_code}, text:{response.text}')
                    else:
                        print("TEST MODE - DFW rule " + commEnt["display_name"] + " would have been imported.")
        return True

    def exportSDDCCGWnetworks(self):
        """Exports the CGW network segments to a JSON file"""
        myURL = (self.proxy_url + "/policy/api/v1/infra/tier-1s/cgw/segments")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        cgw_networks = json_response['results']
        fname = self.export_path / self.network_export_filename
        with open(fname, 'w') as outfile:
            json.dump(cgw_networks, outfile,indent=4)

        if self.network_dhcp_static_binding_export:
            for network in cgw_networks:
                retval = self.getSDDCCGWDHCPBindings(network['id'])

            fname = self.export_path / self.network_dhcp_static_binding_filename
            with open(fname, 'w') as outfile:
                json.dump(self.CGWDHCPbindings, outfile, indent=4)

        return True

    def getSDDCCGWDHCPBindings( self, segment_id: str):
        """Appends any DHCP static bindings for segment_id to the class variable CGWDHCPbindings"""
        myURL = (self.proxy_url + f'/policy/api/v1/infra/tier-1s/cgw/segments/{segment_id}/dhcp-static-binding-configs')
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        if json_response['result_count'] > 0:
            dhcp_static_bindings = json_response['results']
            self.CGWDHCPbindings.append(dhcp_static_bindings)
        else:
            return False


    def exportSDDCMGWRule(self):
        """Exports the MGW firewall rules to a JSON file"""
        myURL = (self.proxy_url + "/policy/api/v1/infra/domains/mgw/gateway-policies/default/rules")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        sddc_MGWrules = json_response['results']
        fname = self.export_path / self.mgw_export_filename
        with open(fname, 'w') as outfile:
            json.dump(sddc_MGWrules, outfile,indent=4)
        return True

    def exportSDDCCGWRule(self):
        """Exports the CGW firewall rules to a JSON file"""
        myURL = (self.proxy_url + "/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        sddc_CGWrules = json_response['results']
        fname = self.export_path / self.cgw_export_filename
        with open(fname, 'w') as outfile:
            json.dump(sddc_CGWrules, outfile,indent=4)
        return True

    def exportSDDCMGWGroups(self):
        """Exports MGW firewall groups to a JSON file"""
        myURL = (self.proxy_url + "/policy/api/v1/infra/domains/mgw/groups")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        mgw_groups = json_response['results']
        fname = self.export_path / self.mgw_groups_filename
        with open(fname, 'w') as outfile:
            json.dump(mgw_groups, outfile,indent=4)
        return True

    def exportSDDCDFWRule(self):
        """Exports the DFW firewall rules to a JSON file"""
        myURL = (self.proxy_url + "/policy/api/v1/infra/domains/cgw/security-policies")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        sddc_DFWrules = json_response['results']
        sddc_Detailed_DFWrules = {}
        for cmap in sddc_DFWrules:
            myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/security-policies/" + cmap["id"] + "/rules"
            response = self.invokeVMCGET(myURL)
            if response is None or response.status_code != 200:
                return False
            cmapDetails = response.json()
            sddc_Detailed_DFWrules[cmap["id"]] = cmapDetails

        fname = self.export_path / self.dfw_export_filename
        fname_detailed = self.export_path / self.dfw_detailed_export_filename
        with open(fname, 'w') as outfile:
            json.dump(sddc_DFWrules, outfile,indent=4)
        with open(fname_detailed, 'w') as outfile:
            json.dump(sddc_Detailed_DFWrules, outfile,indent=4)
        return True

    def importSDDCDFWRule(self):
        """Import all DFW Rules from a JSON file"""
        fname = self.import_path / self.dfw_import_filename
        fname_detailed = self.import_path / self.dfw_detailed_import_filename
        try:
            with open(fname) as filehandle:
                cmaps = json.load(filehandle)
        except:
            print('Import failed - unable to open',fname)
            return False
        try:
            with open(fname_detailed) as filehandle:
                cmapd = json.load(filehandle)
        except:
            print('Import failed - unable to open',fname_detailed)
            return False

        for cmap in cmaps:
            payload = {}
            payload["resource_type"] = cmap["resource_type"]
            payload["id"] = cmap["id"]
            payload["display_name"] = cmap["display_name"]
            payload["category"] = cmap["category"]
            payload["sequence_number"] = cmap["sequence_number"]
            payload["stateful"] = cmap["stateful"]
            if self.import_mode == 'live':
                myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                myURL = self.proxy_url_short + "/policy/api/v1/infra/domains/cgw/security-policies/" + cmap["id"]
                json_data = json.dumps(payload)
                if self.sync_mode is True:
                    response = requests.patch(myURL,headers=myHeader,data=json_data)
                else:
                    response = requests.put(myURL,headers=myHeader,data=json_data)
                self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'

            payload = {}
            cmap_id = cmap["id"]
            commEnts = cmapd[cmap_id]["results"]
            for commEnt in commEnts:
                payload["id"] = commEnt["id"]
                payload["display_name"] = commEnt["display_name"]
                payload["resource_type"] = commEnt["resource_type"]
                payload["source_groups"] = commEnt["source_groups"]
                payload["destination_groups"] = commEnt["destination_groups"]
                if "scope" in commEnt:
                    payload["scope"] = commEnt["scope"]
                payload["action"] = commEnt["action"]
                payload["services"] = commEnt["services"]
                payload["sequence_number"] = commEnt["sequence_number"]
                payload["logged"] = commEnt["logged"]
                payload["disabled"] = commEnt["disabled"]
                if self.import_mode == 'live':
                    myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/security-policies/" + cmap["id"] + "/rules/" + commEnt["id"]
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                    json_data = json.dumps(payload)
                    if self.sync_mode is True:
                        response = requests.patch(myURL,headers=myHeader,data=json_data)
                    else:
                        response = requests.put(myURL,headers=myHeader,data=json_data)
                    if response.status_code == 200:
                        print("DFW rule " + commEnt["display_name"] + " has been imported.")
                    else:
                        self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
                        print(f'API Call Status {response.status_code}, text:{response.text}')
                else:
                    print("TEST MODE - DFW rule " + commEnt["display_name"] + " would have been imported.")
        return True

    def exportServiceAccess(self):
        """Exports SDDC Service Access config to a JSON file"""

        # First, retrieve the linked VPC ID
        myURL = (self.proxy_url + '/cloud-service/api/v1/infra/linked-vpcs')
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        linked_vpcs = json_response["results"]
        num_vpcs = len(linked_vpcs)
        if num_vpcs != 1:
            print('Unexpected linked VPC count: ',num_vpcs)
            return False
        else:
            linked_vpc = linked_vpcs[0]
            fname = self.export_path / self.service_access_filename
            with open(fname, 'w+') as outfile:
                json.dump(linked_vpc,outfile,indent=4)

            # Use the linked VPC ID to discover connected services
            myURL = (self.proxy_url + '/cloud-service/api/v1/infra/linked-vpcs/' + linked_vpc['linked_vpc_id'] + '/connected-services')
            response = self.invokeVMCGET(myURL)
            if response is None or response.status_code != 200:
                return False

            json_response = response.json()
            connected_services = json_response['results']
            for svc in connected_services:
                fname = self.export_path / (svc['name'] + '-' + self.service_access_filename)
                with open(fname, 'w+') as outfile:
                    json.dump(svc,outfile,indent=4)
        return True

    def exportSDDCServices(self,OnlyUserDefinedServices=False):
        """Exports SDDC services to a JSON file
        Args: bool OnlyUserDefinedServices, default True, if you want to ignore predefined system services
        """
        myURL = (self.proxy_url + "/policy/api/v1/infra/services")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        sddc_services = json_response['results']
        if OnlyUserDefinedServices is True:
            fname = self.export_path / self.services_filename
            with open(fname, 'w+') as outfile:
                for service in sddc_services:
                    if service["_create_user"]!= "admin" and service["_create_user"]!="admin;admin" and service["_create_user"]!="system":
                        json.dump(service, outfile,indent=4)
        else:
            fname = self.export_path / self.services_filename
            with open(fname, 'w') as outfile:
                json.dump(sddc_services, outfile,indent=4)
        return True

    def exportVPN(self):
        successval = True

        retval = self.exportVPNIKEProfiles()
        if retval is False:
            successval = False
            print('IKE Profile export failure: ', self.lastJSONResponse)
        else:
            print('IKE Profiles exported.')

        retval = self.exportVPNDPDProfiles()
        if retval is False:
            successval = False
            print('DPD Profile export failure: ', self.lastJSONResponse)
        else:
            print('DPD Profiles exported.')

        retval = self.exportVPNTunnelProfiles()
        if retval is False:
            successval = False
            print('Tunnel Profile export failure: ', self.lastJSONResponse)
        else:
            print('Tunnel Profiles exported.')

        retval = self.exportVPNBGPNeighbors()
        if retval is False:
            successval = False
            print('BGP neighbor export failure: ', self.lastJSONResponse)
        else:
            print('BGP neighbors exported.')

        retval = self.exportVPNLocalBGP()
        if retval is False:
            successval = False
            print('VPN Local BGP export failure: ', self.lastJSONResponse)
        else:
            print('VPN Local BGP exported.')

        retval = self.exportVPNl2config()
        if retval is False:
            successval = False
            print('L2 VPN export failure: ', self.lastJSONResponse)
        else:
            print('L2 VPN exported.')

        retval = self.exportVPNl3config()
        if retval is False:
            successval = False
            print('L3 VPN export failure: ', self.lastJSONResponse)
        else:
            print('L3 VPN exported.')

        return successval

    def exportVPNDPDProfiles(self):
        myURL = (self.proxy_url_short + "/policy/api/v1/infra/ipsec-vpn-dpd-profiles")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        dpd_profiles = json_response['results']
        fname = self.export_path / self.vpn_dpd_filename
        with open(fname, 'w') as outfile:
            json.dump(dpd_profiles, outfile,indent=4)
        return True

    def exportVPNIKEProfiles(self):
        myURL = (self.proxy_url_short + "/policy/api/v1/infra/ipsec-vpn-ike-profiles")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        ike_profiles = json_response['results']
        fname = self.export_path / self.vpn_ike_filename
        with open(fname, 'w') as outfile:
            json.dump(ike_profiles, outfile,indent=4)
        return True

    def exportVPNTunnelProfiles(self):
        myURL = (self.proxy_url_short + "/policy/api/v1/infra/ipsec-vpn-tunnel-profiles")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        tunnel_profiles = json_response['results']
        fname = self.export_path / self.vpn_tunnel_filename
        with open(fname, 'w') as outfile:
            json.dump(tunnel_profiles, outfile,indent=4)
        return True

    def exportVPNLocalBGP(self):
        myURL = (self.proxy_url_short + "/policy/api/v1/infra/tier-0s/vmc/locale-services/default/bgp")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        #local_bgp = json_response
        fname = self.export_path / self.vpn_local_bgp_filename
        with open(fname, 'w') as outfile:
            json.dump(json_response, outfile,indent=4)
        return True

    def exportVPNBGPNeighbors(self):
        myURL = (self.proxy_url_short + "/policy/api/v1/infra/tier-0s/vmc/locale-services/default/bgp/neighbors")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        bgp_neighbors = json_response['results']
        fname = self.export_path / self.vpn_bgp_filename
        with open(fname, 'w') as outfile:
            json.dump(bgp_neighbors, outfile,indent=4)
        return True

    def getVPNl3sensitivedata(self,l3vpnid):
        """ Retrieve sensitive data such as IPSEC preshared keys from an L3VPN configuration"""
        myHeader = {'csp-auth-token': self.access_token}
        myURL = (self.proxy_url_short + f'/policy/api/v1/infra/tier-0s/vmc/locale-services/default/ipsec-vpn-services/default/sessions/{l3vpnid}?action=show_sensitive_data')
        try:
            response = requests.get(myURL, headers=myHeader)
            if response.status_code != 200:
                self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
                return ""
            else:
                sensitive_l3vpn = json.loads(response.text)
                return sensitive_l3vpn
        except:
            self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
            return ""

    def exportVPNl2config(self):
        myURL = (self.proxy_url_short + "/policy/api/v1/infra/tier-0s/vmc/locale-services/default/l2vpn-services/default/sessions")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        vpn_l2_config = json_response['results']
        fname = self.export_path / self.vpn_l2_filename
        with open(fname, 'w') as outfile:
            json.dump(vpn_l2_config, outfile,indent=4)
        return True

    def exportVPNl3config(self):
        myURL = (self.proxy_url_short + "/policy/api/v1/infra/tier-0s/vmc/locale-services/default/ipsec-vpn-services/default/sessions")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        vpn_l3_config = json_response['results']
        i = 0
        for l3vpn in vpn_l3_config:
            sensitive_l3vpn = self.getVPNl3sensitivedata(l3vpn['id'])
            if sensitive_l3vpn["psk"]:
                vpn_l3_config[i]["psk"] = sensitive_l3vpn["psk"]
            i += 1

        fname = self.export_path / self.vpn_l3_filename
        with open(fname, 'w') as outfile:
            json.dump(vpn_l3_config, outfile,indent=4)
        return True

    def importCGWNetworks(self):
        """Imports CGW network semgements from a JSON file"""
        fname = self.import_path / self.network_import_filename
        try:
            with open(fname) as filehandle:
                networks = json.load(filehandle)
        except:
            print('Import failed - unable to open',fname)
            return

        importResults = {}
        irKey = 0
        for n in networks:
            skip_network = False
            for e in self.network_import_exclude_list:
                m = re.match(e,n["display_name"])
                if m:
                    print(n["display_name"],'skipped - matches exclusion regex', e)
                    skip_network = True
                    break
            if skip_network is True:
                continue
            result = ""
            resultNote = ""

            json_data = {}
            json_data["id"] = n['id']
            json_data["type"] = n['type']
            json_data["display_name"] = n['display_name']

            if "subnets" in n:
                json_data["subnets"] = n['subnets']
            else:
                result = "FAIL"
                resultNote += "No subnets found."

            if "advanced_config" in n:
                json_data["advanced_config"] = n["advanced_config"]

            if self.import_mode == "live":
                myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                myURL = (self.proxy_url + "/policy/api/v1/infra/tier-1s/cgw/segments/" + n['id'])
                if self.sync_mode is True:
                    response = requests.patch(myURL, headers=myHeader, json=json_data)
                else:
                    response = requests.put(myURL, headers=myHeader, json=json_data)

                if response.status_code == 200:
                    result = "SUCCESS"
                    print('Segment {} has been imported.'.format(n['display_name']))
                else:
                    result = "FAIL"
                    resultNote += f'API Call Status {response.status_code}, text:{response.text}'
            else:
                result = "TEST"
                resultNote += "Test mode, no changes made"
            current_result = {'id':n['id'],'display_name':n['display_name'],'result':result,'result_note':resultNote}
            importResults[irKey] = current_result
            irKey +=1
            if self.network_import_max_networks > 0 and (irKey) >= self.network_import_max_networks:
                print(f'Maximum network import value of {self.network_import_max_networks} reached, no further imports will be attempted.')
                break

        table = PrettyTable(['Display Name', 'Result', 'Result Note', 'Segment ID'])
        for i in importResults:
            table.add_row([importResults[i]['display_name'],importResults[i]['result'],importResults[i]['result_note'],importResults[i]['id']])
        return (table)

    def importSDDCServices(self):
        """Import all services from a JSON file"""
        fname = self.import_path / self.services_filename
        try:
            with open(fname) as filehandle:
                services = json.load(filehandle)
        except:
            print('Import failed - unable to open',fname)
            return

        for service in services:
            json_data = {}
            if service["_create_user"]!= "admin" and service["_create_user"]!="admin;admin" and service["_create_user"]!="system":
                if self.import_mode == "live":
                    json_data["id"] = service["id"]
                    json_data["resource_type"]=service["resource_type"]
                    json_data["display_name"]=service["display_name"]
                    json_data["service_type"]=service["service_type"]
                    service_entries = []
                    for entry in service["service_entries"]:
                        #print("-------------------------------------------------")
                        #print("entry")
                        modified_entry = {}
                        for k in entry:
                            #print("-------------------------------------------------")
                            #print("sub_entry")
                            #print(k)
                            if k != "path"  and k != "relative_path" and k != "overridden" and k != "_create_time" and k != "_create_user" and k != "_last_modified_time" and k != "_last_modified_user" and k != "_system_owned" and k != "_protection" and k != "_revision":
                                modified_entry[k] = entry[k]
                        service_entries.append(modified_entry)
                    json_data["service_entries"]=service_entries
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                    myURL = self.proxy_url + "/policy/api/v1/infra/services/" + service["id"]
                    #print(myURL)
                    #print(json_data)
                    if self.sync_mode is True:
                        response = requests.patch(myURL, headers=myHeader, json=json_data)
                    else:
                        response = requests.put(myURL, headers=myHeader, json=json_data)
                    if response.status_code == 200:
                        result = "SUCCESS"
                        print('Added {}'.format(json_data['display_name']))
                    else:
                        result = "FAIL"
                        print( f'API Call Status {response.status_code}, text:{response.text}')
                else:
                    print("TEST MODE - Service",service["display_name"],"would have been imported.")

    def convertServiceRolePayload(self, sourcePayload: str) -> bool:
        """Converts a ServiceRole payload from its default format to the format required to add it to a User. Saves results to convertedServiceRolePayload """
        self.convertedServiceRolePayload = {}
        servicedefs = []
        for servicedef in sourcePayload:
            modified_def = {}
            role = {}
            modified_def['serviceDefinitionId'] =  servicedef['serviceDefinitionId']
            roles = []
            for r in servicedef['serviceRoles']:
                modified_role = {}
                modified_role['name'] = r['name']
                modified_role['roleName'] = r['roleName']
                modified_role['expiresAt'] = r['expiresAt']
                roles.append(modified_role)
            modified_def['rolesToAdd'] = roles
            servicedefs.append( modified_def )

        self.convertedServiceRolePayload['serviceRoles'] = servicedefs
        return True

    def syncRolesToDestinationUsers(self):
        """ Uses the payload built by convertServiceRolePayload to update user accounts"""
        for email in self.RoleSyncDestUserEmails:
            print(f'Looking up destination user {email}')
            retval = self.searchOrgUser(self.dest_org_id,email)
            if retval is False:
                print('API error searching for ' + str(email))
            else:
                if len(self.user_search_results_json['results']) > 0:
                    dest_user_json = self.user_search_results_json['results'][0]
                    userId = dest_user_json['user']['userId']
                    print(f'userId for {email} = {userId}')
                    dest_user_roles = dest_user_json['serviceRoles']
                    myURL =  self.strCSPProdURL + '/csp/gateway/am/api/v3/users/' + userId + '/orgs/' + self.dest_org_id + "/roles"
                    if self.import_mode == "live":
                        response = self.invokeVMCPATCH(myURL,json.dumps(self.convertedServiceRolePayload))
                        if response.status_code == 200:
                            print (f'Role sync success: {self.RoleSyncSourceUserEmail}->{email}')
                        else:
                            self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
                            print(f'API error: {self.lastJSONResponse}')
                    else:
                        print(f'TEST MODE - would have synced {self.RoleSyncSourceUserEmail}->{email}')
                else:
                    print('Could not find user with email ' + email)

    def invokeCSPGET(self,url: str) -> requests.Response:
        try:
            response = requests.get(url,headers= {"Authorization":"Bearer " + self.access_token})
            if response.status_code != 200:
                self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
            return response
        except Exception as e:
                self.lastJSONResponse = e
                return None

    def invokeVMCGET(self,url: str) -> requests.Response:
        """Invokes a VMC On AWS GET request"""
        myHeader = {'csp-auth-token': self.access_token}
        try:
            response = requests.get(url,headers=myHeader)
            if response.status_code != 200:
                self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
            return response
        except Exception as e:
                self.lastJSONResponse = e
                return None

    def invokeVMCPATCH(self, url: str,json_data: str) -> requests.Response:
        """Invokes a VMC on AWS PATCH request"""
        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
        try:
            response = requests.patch(url,headers=myHeader,data=json_data)
            if response.status_code != 200:
                self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
            return response
        except Exception as e:
            self.lastJSONResponse = e
            return None

    def invokeNSXTGET(self,url: str) -> requests.Response:
        myHeader = {"Content-Type": "application/json","Accept": "application/json"}
        try:
            response = requests.get(url,headers=myHeader, auth=(self.srcNSXmgrUsername ,self.srcNSXmgrPassword), verify=self.srcNSXmgrSSLVerify)
            if response.status_code != 200:
                self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
            return response
        except Exception as e:
                self.lastJSONResponse = e
                return None

    def createSDDCCGWGroup(self, group_name: str):
        """Creates a new CGW Group"""
        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
        myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/groups/" + group_name

        json_data = {"display_name":group_name, "id":group_name }
        if self.import_mode == "live":
            group_resp = requests.put(myURL,headers=myHeader,data=json.dumps(json_data))
            if group_resp.status_code == 200:
                print(f'Group {group_name} has been created')
            else:
                print(f'API Call Status {group_resp.status_code}, text:{group_resp.text}')
                print(json_data)
        else:
            print(json_data)
            print(f'TEST MODE: would have added CGW group {group_name}')
            return True

    def deleteAllSDDCCGWGroups(self):
        """ Just what it sounds like - delete every single CGW group. Use with caution"""
        myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/groups"
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False
        json_response = response.json()
        cgw_groups = json_response['results']

        # After grabbing an intial set of results, check for presence of a cursor
        while "cursor" in json_response:
            myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/groups?cursor=" + json_response['cursor']
            response = self.invokeVMCGET(myURL)
            if response is None or response.status_code != 200:
                return False
            json_response = response.json()
            cgw_groups.extend(json_response['results'])

        for grp in cgw_groups:
            retval = self.deleteSDDCCGWGroup(grp['id'])

    def deleteSDDCCGWGroup(self, group_name: str):
        """Creates a CGW Group"""
        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
        myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/groups/" + group_name

        #json_data = {"display_name":group_name, "id":group_name }
        if self.import_mode == "live":
            group_resp = requests.delete(myURL,headers=myHeader)
            if group_resp.status_code == 200:
                print(f'Group {group_name} has been deleted')
            else:
                print(f'API Call Status {group_resp.status_code}, text:{group_resp.text}')
        else:
            print(f'TEST MODE: would have deleted CGW group {group_name}')
            return True

    def exportSDDCCGWGroups(self):
            """Exports the CGW groups to a JSON file"""
            myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/groups"
            response = self.invokeVMCGET(myURL)
            if response is None or response.status_code != 200:
                return False
            json_response = response.json()
            cgw_groups = json_response['results']

            # After grabbing an intial set of results, check for presence of a cursor
            while "cursor" in json_response:
                myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/groups?cursor=" + json_response['cursor']
                response = self.invokeVMCGET(myURL)
                if response is None or response.status_code != 200:
                    return False
                json_response = response.json()
                cgw_groups.extend(json_response['results'])

            fname = self.export_path / self.cgw_groups_filename
            with open(fname, 'w') as outfile:
                json.dump(cgw_groups, outfile,indent=4)

            return True

    def importSDDCCGWRule(self):
        """Import all CGW Rules from a JSON file"""
        fname = self.import_path / self.cgw_import_filename
        try:
            with open(fname) as filehandle:
                cgwrules = json.load(filehandle)
        except:
            print('Import failed - unable to open',fname)
            return False

        payload = {}
        for rule in cgwrules:
            skip_rule = False
            for e in self.cgw_import_exclude_list:
                m = re.match(e,rule["display_name"])
                if m:
                    print(rule["display_name"],'skipped - matches exclusion regex', e)
                    skip_rule = True
                    break
            if skip_rule is True:
                continue

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
                if self.import_mode == "live":
                    json_data = json.dumps(payload)
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                    myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules/" + rule["id"]
                    json_data = json.dumps(payload)
                    if self.sync_mode is True:
                        createfwruleresp = requests.patch(myURL,headers=myHeader,data=json_data)
                    else:
                        createfwruleresp = requests.put(myURL,headers=myHeader,data=json_data)
                    print("Firewall Rule " + payload["display_name"] + " has been imported.")
                else:
                    print("TEST MODE - Firewall Rule " + payload["display_name"] + " would have been imported." )
                payload = {}
        return True


    def importSDDCCGWGroup(self):
        """Import all CGW groups from a JSON file"""
        fname = self.import_path / self.cgw_groups_filename
        try:
            with open(fname) as filehandle:
                groups = json.load(filehandle)
        except:
            print('Import failed - unable to open',fname)
            return False

        payload = {}
        for group in groups:
            skip_vm_expression = False
            skip_group = False
            for e in self.cgw_groups_import_exclude_list:
                m = re.match(e,group["display_name"])
                if m:
                    print(group["display_name"],'skipped - matches exclusion regex', e)
                    skip_group = True
                    break
            if skip_group is True:
                continue
            if group["_create_user"]!= "admin" and group["_create_user"]!="admin;admin":
                payload["id"]=group["id"]
                payload["resource_type"]=group["resource_type"]
                payload["display_name"]=group["display_name"]
                if self.import_mode == "live":
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                    myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/groups/" + group["id"]
                    if "expression" in group:
                        group_expression = group["expression"]
                        for item in group_expression:
                            if item["resource_type"] == "ExternalIDExpression":
                                skip_vm_expression = True
                                print(f'CGW Group {group["display_name"]} cannot be imported as it relies on VM external ID.')
                                break
                    else:
                        continue
                    if skip_vm_expression == False:
                        payload["expression"]=group["expression"]
                        json_data = json.dumps(payload)
                        if self.sync_mode is True:
                            creategrpresp = requests.patch(myURL,headers=myHeader,data=json_data)
                        else:
                            creategrpresp = requests.put(myURL,headers=myHeader,data=json_data)
                        print("CGW Group " + payload["display_name"] + " has been imported.")
                    else:
                        continue
                else:
                        print("TEST MODE - CGW Group " + payload["display_name"] + " would have been imported.")
                payload = {}
        return True

    def importServiceAccess(self):
        """Imports SDDC Service Access config from a JSON file"""

        # First, retrieve the linked VPC ID
        myHeader = {'csp-auth-token': self.access_token}
        myURL = (self.proxy_url + '/cloud-service/api/v1/infra/linked-vpcs')
        try:
            response = requests.get(myURL,headers=myHeader)
            if response.status_code != 200:
                self.lastJSONResponse  = f'API Call Status {response.status_code}, text:{response.text}'
                return False
        except:
            self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
            return False

        json_response = response.json()
        linked_vpcs = json_response["results"]
        num_vpcs = len(linked_vpcs)
        if num_vpcs != 1:
            print('Unexpected linked VPC count: ',num_vpcs)
            return False
        else:
            linked_vpc = linked_vpcs[0]

        linked_vpc_id = linked_vpc['linked_vpc_id']

        # Looking for *-service_access.json
        files = glob.glob(self.import_folder + '/*-' + self.service_access_filename)
        for f in files:
            payload = {}
            with open(f) as filehandle:
                svcaccess = json.load(filehandle)
                payload['name'] = svcaccess['name']
                payload['enabled'] = svcaccess['enabled']
                if self.import_mode == 'live':
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                    myURL = (self.proxy_url + '/cloud-service/api/v1/infra/linked-vpcs/' + linked_vpc_id + '/connected-services/' + payload['name'])
                    json_data = json.dumps(payload)
                    if self.sync_mode is True:
                        svcresp = requests.patch(myURL,headers=myHeader,data=json_data)
                    else:
                        svcresp = requests.put(myURL,headers=myHeader,data=json_data)
                    if svcresp.status_code == 200:
                        print("Service Access " + payload["name"] + " has been imported.")
                    else:
                        print(f'API Call Status {svcresp.status_code}, text:{svcresp.text}')
                        print(json_data)
                else:
                    print("TEST MODE - Service Access " + payload['name']  + " would have been importeed.")

        return True

    def importVPNLocalBGP(self):
        fname = self.import_path / self.vpn_local_bgp_filename
        with open(fname) as filehandle:
            local_bgp = json.load(filehandle)
            payload = {}
            payload["local_as_num"] = local_bgp ["local_as_num"]
            if self.import_mode == 'live':
                myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                myURL = self.proxy_url + "/policy/api/v1/infra/tier-0s/vmc/locale-services/default/bgp"
                json_data = json.dumps(payload)
                # Always using PATCH here because this BGP object always exists in any SDDC
                bgppresp = requests.patch(myURL,headers=myHeader,data=json_data)
                if bgppresp.status_code == 200:
                    print("Local BGP config  has been imported.")
                else:
                    print(f'API Call Status {bgppresp.status_code}, text:{bgppresp.text}')
                    print(json_data)
            else:
                print("TEST MODE - Local BGP config  would have been imported.")


    def importVPNBGPNeighbors(self):
        fname = self.import_path / self.vpn_bgp_filename
        with open(fname) as filehandle:
            bgpdata = json.load(filehandle)
            payload = {}
            for bgpentry in bgpdata:
                if bgpentry["_create_user"]!= "admin" and bgpentry["_create_user"]!="admin;admin" and bgpentry["_create_user"]!="system":
                        payload["id"]=bgpentry["id"]
                        payload["neighbor_address"]=bgpentry["neighbor_address"]
                        payload["remote_as_num"]=bgpentry["remote_as_num"]
                        if "route_filtering" in bgpentry:
                            payload["route_filtering"]=bgpentry["route_filtering"]
                        if "keep_alive_time" in bgpentry:
                            payload["keep_alive_time"]=bgpentry["keep_alive_time"]
                        if "hold_down_time" in bgpentry:
                            payload["hold_down_time"]=bgpentry["hold_down_time"]
                        if "allow_as_in" in bgpentry:
                            payload["allow_as_in"]=bgpentry["allow_as_in"]
                        if "maximum_hop_limit" in bgpentry:
                            payload["maximum_hop_limit"]=bgpentry["maximum_hop_limit"]
                        if "resource_type" in bgpentry:
                            payload["resource_type"]=bgpentry["resource_type"]
                        if "display_name" in bgpentry:
                            payload["display_name"]=bgpentry["display_name"]
                        if "marked_for_delete" in bgpentry:
                            payload["marked_for_delete"]=bgpentry["marked_for_delete"]
                        if "overridden" in bgpentry:
                            payload["overridden"]=bgpentry["overridden"]
                        if self.import_mode == 'live':
                            myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                            myURL = self.proxy_url + "/policy/api/v1/infra/tier-0s/vmc/locale-services/default/bgp/neighbors/" + bgpentry["id"]
                            json_data = json.dumps(payload)
                            if self.sync_mode is True:
                                bgppresp = requests.patch(myURL,headers=myHeader,data=json_data)
                            else:
                                bgppresp = requests.put(myURL,headers=myHeader,data=json_data)
                            if bgppresp.status_code == 200:
                                print("BGP neighbor " + payload["display_name"] + " has been imported.")
                            else:
                                print(f'API Call Status {bgppresp.status_code}, text:{bgppresp.text}')
                                print(json_data)
                        else:
                            print("TEST MODE - BGP Neighbor " +  payload["display_name"] + " created by " + bgpentry["_create_user"] + " would have been imported.")


    def importVPNTunnelProfiles(self):
        fname = self.import_path / self.vpn_tunnel_filename
        with open(fname) as filehandle:
            tunps = json.load(filehandle)
            payload = {}
            for tunp in tunps:
                if tunp["_create_user"]!= "admin" and tunp["_create_user"]!="admin;admin" and tunp["_create_user"]!="system":
                    payload["id"]=tunp["id"]
                    payload["df_policy"]=tunp["df_policy"]
                    payload["enable_perfect_forward_secrecy"]=tunp["enable_perfect_forward_secrecy"]
                    payload["dh_groups"]=tunp["dh_groups"]
                    payload["digest_algorithms"]=tunp["digest_algorithms"]
                    payload["encryption_algorithms"]=tunp["encryption_algorithms"]
                    payload["sa_life_time"]=tunp["sa_life_time"]
                    payload["resource_type"]=tunp["resource_type"]
                    payload["display_name"]=tunp["display_name"]
                    if self.import_mode == 'live':
                        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                        myURL = self.proxy_url + "/policy/api/v1/infra/ipsec-vpn-tunnel-profiles/" + tunp["id"]
                        json_data = json.dumps(payload)
                        if self.sync_mode is True:
                            tunpresp = requests.patch(myURL,headers=myHeader,data=json_data)
                        else:
                            tunpresp = requests.put(myURL,headers=myHeader,data=json_data)
                        if tunpresp.status_code == 200:
                            print("Tunnel Profile " + payload["display_name"] + " has been imported.")
                        else:
                            print(f'API Call Status {tunpresp.status_code}, text:{tunpresp.text}')
                            print(json_data)
                    else:
                        print("TEST MODE - Tunnel Profile " +  payload["display_name"] + " created by " + tunp["_create_user"] + " would have been imported.")

    def importVPNl2config(self):
        fname = self.import_path / self.vpn_l2_filename
        with open(fname) as filehandle:
            l2vpns = json.load(filehandle)
            payload = {}
            for l2vpn in l2vpns:
                payload = {}
                if l2vpn["_create_user"]!= "admin" and l2vpn["_create_user"]!="admin;admin" and l2vpn["_create_user"]!="system":
                    payload["id"]=l2vpn["id"]
                    payload["transport_tunnels"]=l2vpn["transport_tunnels"]
                    if self.vpn_disable_on_import is True:
                        print('vpn_disable_on_import set to True, disabling VPN')
                        payload["enabled"]= False
                    else:
                        payload["enabled"]=l2vpn["enabled"]
                    payload["tunnel_encapsulation"]=l2vpn["tunnel_encapsulation"]
                    payload["resource_type"]=l2vpn["resource_type"]
                    payload["display_name"]=l2vpn["display_name"]
                    if "overridden" in l2vpn:
                        payload["overridden"]=l2vpn["overridden"]
                    json_data = json.dumps(payload)
                    if self.import_mode == 'live':
                        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                        myURL = self.proxy_url + f'/policy/api/v1/infra/tier-0s/vmc/locale-services/default/l2vpn-services/default/sessions/{payload["id"]}'
                        if self.sync_mode is True:
                            l2vpnresp = requests.patch(myURL,headers=myHeader,data=json_data)
                        else:
                            l2vpnresp = requests.put(myURL,headers=myHeader,data=json_data)
                        if l2vpnresp.status_code == 200:
                            print("L2VPN " + payload["id"] + " has been imported.")
                        else:
                            print(f'API Call Status {l2vpnresp.status_code}, text:{l2vpnresp.text}')
                            print(json_data)
                    else:
                        print("TEST MODE - L2VPN " + l2vpn["id"] + " created by " + l2vpn["_create_user"] + " would have been imported.")
        return True


    def importVPNl3config(self):
        fname = self.import_path / self.vpn_l3_filename
        with open(fname) as filehandle:
            l3vpns = json.load(filehandle)
            payload = {}
            for l3vpn in l3vpns:
                payload = {}

                if l3vpn["_create_user"]!= "admin" and l3vpn["_create_user"]!="admin;admin" and l3vpn["_create_user"]!="system":
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
                    if l3vpn.get("rules"):
                        vpnrulesFixed = []
                        vpnrules = l3vpn["rules"]
                        for vpnrule in vpnrules:
                            if "path" in vpnrule:
                                vpnrule.pop("path")
                            if "parent_path" in vpnrule:
                                vpnrule.pop("parent_path")
                            if "policy_path" in vpnrule:
                                vpnrule.pop("policy_path")
                            if "_create_user" in vpnrule:
                                vpnrule.pop("_create_user")
                            if "_create_time" in vpnrule:
                                vpnrule.pop("_create_time")
                            if "_last_modified_user" in vpnrule:
                                vpnrule.pop("_last_modified_user")
                            if "_last_modified_time" in vpnrule:
                                vpnrule.pop("_last_modified_time")
                            if "_system_owned" in vpnrule:
                                vpnrule.pop("_system_owned")
                            if "_revision" in vpnrule:
                                vpnrule.pop("_revision")
                            if "_protection" in vpnrule:
                                vpnrule.pop("_protection")
                            vpnrulesFixed.append(vpnrule)
                        payload["rules"] = vpnrulesFixed
                    if l3vpn.get("authentication_mode"):
                        payload["authentication_mode"]=l3vpn["authentication_mode"]
                    if l3vpn.get("compliance_suite"):
                        payload["compliance_suite"]=l3vpn["compliance_suite"]
                    if l3vpn.get("connection_initiation_mode"):
                        payload["connection_initiation_mode"]=l3vpn["connection_initiation_mode"]
                    if l3vpn.get("display_name"):
                        payload["display_name"]=l3vpn["display_name"]
                    if self.vpn_disable_on_import is True:
                        print('vpn_disable_on_import set to True, disabling VPN')
                        payload["enabled"] = False
                    else:
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
                    json_data = json.dumps(payload)
                    if self.import_mode == 'live':
                        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                        myURL = self.proxy_url + f'/policy/api/v1/infra/tier-0s/vmc/locale-services/default/ipsec-vpn-services/default/sessions/{payload["id"]}'
                        if self.sync_mode is True:
                            l3vpnresp = requests.patch(myURL,headers=myHeader,data=json_data)
                        else:
                            l3vpnresp = requests.put(myURL,headers=myHeader,data=json_data)
                        if l3vpnresp.status_code == 200:
                            print("L3VPN " + payload["id"] + " has been imported.")
                        else:
                            print(f'API Call Status {l3vpnresp.status_code}, text:{l3vpnresp.text}')
                            print(json_data)
                    else:
                        print("TEST MODE - L3VPN " + l3vpn["id"] + " created by " + l3vpn["_create_user"] + " would have been imported.")

    def importVPNIKEProfiles(self):
        """Import all"""
        fname = self.import_path / self.vpn_ike_filename
        with open(fname) as filehandle:
            ikeps = json.load(filehandle)
            payload = {}
            for ikep in ikeps:
                if ikep["_create_user"]!= "admin" and ikep["_create_user"]!="admin;admin" and ikep["_create_user"]!="system":
                    payload["id"]=ikep["id"]
                    payload["encryption_algorithms"]=ikep["encryption_algorithms"]
                    payload["ike_version"]=ikep["ike_version"]
                    payload["dh_groups"]=ikep["dh_groups"]
                    payload["sa_life_time"]=ikep["sa_life_time"]
                    payload["resource_type"]=ikep["resource_type"]
                    payload["display_name"]=ikep["display_name"]
                    payload["marked_for_delete"]=ikep["marked_for_delete"]
                    if "overridden" in ikep:
                        payload["overridden"]=ikep["overridden"]
                    json_data = json.dumps(payload)
                    if self.import_mode == 'live':
                        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                        myURL = self.proxy_url + "/policy/api/v1/infra/ipsec-vpn-ike-profiles/" + ikep["id"]
                        if self.sync_mode is True:
                            createikepresp = requests.patch(myURL,headers=myHeader,data=json_data)
                        else:
                            createikepresp = requests.put(myURL,headers=myHeader,data=json_data)
                        if createikepresp.status_code == 200:
                            print("VPN Profile " + payload["display_name"] + " has been imported.")
                        else:
                            print(f'API Call Status {createikepresp.status_code}, text:{createikepresp.text}')
                            print(json_data)
                    else:
                        print("TEST MODE - IKE Profile " + ikep["display_name"] + " created by " + ikep["_create_user"] + " would have been imported.")

    def importSDDCMGWRule(self):
        """Import all MGW Rules from a JSON file"""
        fname = self.import_path / self.mgw_import_filename
        try:
            with open(fname) as filehandle:
                mgwrules = json.load(filehandle)
        except:
            print('Import failed - unable to open',fname)
            return False

        payload = {}
        for rule in mgwrules:
            skip_rule = False
            for e in self.mgw_import_exclude_list:
                m = re.match(e,rule["display_name"])
                if m:
                    print(rule["display_name"],'skipped - matches exclusion regex', e)
                    skip_rule = True
                    break
            if skip_rule is True:
                continue

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
                if self.import_mode == "live":
                    json_data = json.dumps(payload)
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                    myURL = self.proxy_url + "/policy/api/v1/infra/domains/mgw/gateway-policies/default/rules/" + rule["id"]
                    json_data = json.dumps(payload)
                    if self.sync_mode is True:
                        createfwruleresp = requests.patch(myURL,headers=myHeader,data=json_data)
                    else:
                        createfwruleresp = requests.put(myURL,headers=myHeader,data=json_data)
                    print("Firewall Rule " + payload["display_name"] + " has been imported.")
                else:
                    print("TEST MODE - Firewall Rule " + payload["display_name"] + " would have been imported.")
                payload = {}
        return True

    def importSDDCMGWGroup(self):
        """Import all MGW groups from a JSON file"""
        fname = self.import_path / self.mgw_groups_filename
        try:
            with open(fname) as filehandle:
                groups = json.load(filehandle)
        except:
            print('Import failed - unable to open',fname)
            return False

        payload = {}
        for group in groups:
            skip_group = False
            for e in self.mgw_groups_import_exclude_list:
                m = re.match(e,group["display_name"])
                if m:
                    print(group["display_name"],'skipped - matches exclusion regex', e)
                    skip_group = True
                    break
            if skip_group is True:
                continue

            if group["_create_user"]!= "admin" and group["_create_user"]!="admin;admin":
                payload["id"]=group["id"]
                payload["resource_type"]=group["resource_type"]
                payload["display_name"]=group["display_name"]
                if "expression" in group:
                    payload["expression"]=group["expression"]
                if self.import_mode == "live":
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token }
                    myURL = self.proxy_url + "/policy/api/v1/infra/domains/mgw/groups/" + group["id"]
                    json_data = json.dumps(payload)
                    if self.sync_mode is True:
                        creategrpresp = requests.patch(myURL,headers=myHeader,data=json_data)
                    else:
                        creategrpresp = requests.put(myURL,headers=myHeader,data=json_data)
                    print("MGW Group " + payload["display_name"] + " has been imported.")
                else:
                    print("TEST MODE - MGW Group " + payload["display_name"] + " would have been imported.")
                payload = {}
        return True

    def exportSDDCNat(self):
        """Exports the NAT rules to a JSON file"""
        myURL = (self.proxy_url + "/policy/api/v1/infra/tier-1s/cgw/nat/USER/nat-rules")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        nat_results = json_response['results']
        fname = self.export_path / self.nat_export_filename
        with open(fname, 'w') as outfile:
            json.dump(nat_results, outfile,indent=4)
        return True

    def importSDDCNats(self):
        """Imports SDDC NAT from a JSON file"""
        fname = self.import_path / self.nat_import_filename
        with open(fname) as filehandle:
            nat = json.load(filehandle)

        fname = self.import_path / self.public_ip_old_new_filename
        with open(fname) as filehandle:
            public_ip_old_new = json.load(filehandle)

        for n in nat:
            json_data = {}
            json_data["id"] = n['id']
            json_data["action"] = n["action"]
            json_data["scope"] = n["scope"]
            json_data["enabled"] = n["enabled"]
            json_data["logging"] = n["logging"]
            if "firewall_match" in n:
                json_data["firewall_match"] = n["firewall_match"]
            action = n["action"]
            if self.import_mode == "live":
                if action == "any" or action == "REFLEXIVE":
                    json_data["action"] = action
                    json_data["source_network"] = n["source_network"]
                    old_ip = n["translated_network"]
                    json_data["translated_network"] = public_ip_old_new[old_ip]
                    new_ip_name_dash = json_data["translated_network"].replace(".","-")
                    myURL = (self.proxy_url + "/policy/api/v1/infra/tier-1s/cgw/nat/USER/nat-rules/" + (n['display_name']).replace(" ", "-") + "-" + new_ip_name_dash)
                    myHeader = {'csp-auth-token': self.access_token}
                    response = requests.put(myURL, headers=myHeader, json=json_data)
                    json_response_status_code = response.status_code
                    print("NAT Rule " + n['display_name'] + " has been imported.")
                elif action == "DNAT":
                    old_ip = n["destination_network"]
                    json_data["destination_network"] = public_ip_old_new[old_ip]
                    json_data["translated_network"] = n["translated_network"]
                    json_data["translated_ports"] = n["translated_ports"]
                    json_data["service"] = n["service"]
                    new_ip_name_dash = json_data["destination_network"].replace(".","-")
                    myURL = (self.proxy_url + "/policy/api/v1/infra/tier-1s/cgw/nat/USER/nat-rules/" + (n['display_name']).replace(" ", "-") + "-" + new_ip_name_dash)
                    myHeader = {'csp-auth-token': self.access_token}
                    response = requests.put(myURL, headers=myHeader, json=json_data)
                    json_response_status_code = response.status_code
                    print("NAT Rule " + n['display_name'] + " has been imported.")
                else:
                    print("unknown NAT rule type.")
            else:
                print("TEST MODE - NAT Rule " + n['display_name'] + " would have been imported.")

    def exportSDDCListPublicIP(self):
        """Exports the Public IPs to a JSON file"""
        myURL = (self.proxy_url + "/cloud-service/api/v1/infra/public-ips")
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        sddc_public_ips = json_response['results']
        sddc_dict = [{d['ip']:d['display_name']} for d in sddc_public_ips]
        fname = self.export_path / self.public_export_filename
        with open(fname, 'w') as outfile:
            json.dump(sddc_dict, outfile,indent=4)
        return True

    def importSDDCPublicIPs(self):
        """Import all Public IP addresses from a JSON file"""
        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.access_token}
        proxy_url_short = (self.proxy_url).rstrip("sks-nsxt-manager")
        aDict = {}
        fname = self.import_path / self.public_import_filename
        with open(fname) as filehandle:
            public_ip_list = json.load(filehandle)
            for n in public_ip_list:
                public_name = list(n.values())[0]
                if len(public_name) == 0:
                    public_name = list(n.keys())[0].replace('.','_')
                public_name = public_name.replace(' ','_')
                myURL = (proxy_url_short + "cloud-service/api/v1/infra/public-ips/" + public_name)
                public_ip_request_data = {
                "display_name" : public_name
                }
                if self.import_mode == "live":
                    public_ip_response = requests.put(myURL, headers=myHeader, json=public_ip_request_data)
                    myHeader = {'csp-auth-token': self.access_token}
                    myURL = (self.proxy_url + "/cloud-service/api/v1/infra/public-ips/" + public_name)
                    response = requests.get(myURL, headers=myHeader)
                    json_response = response.json()
                    if "ip" in json_response:
                        new_ip =json_response['ip']
                        old_ip =list(n.keys())[0]
                        aDict[old_ip] = new_ip
                        print("Previous IP " + old_ip + " has been imported and remapped to " + new_ip + ".")
                    else:
                        print("Error: no IP found in JSON:", json_response)
                        new_ip = list(n.keys())[0]
                else:
                    old_ip =list(n.keys())[0]
                    aDict[old_ip] = old_ip
                    print("TEST MODE - Previous IP " + old_ip + " would have been remapped.")
            fname = self.export_path / self.public_ip_old_new_filename
            with open(fname, 'w') as outfile:
                json.dump(aDict, outfile,indent=4)
            return aDict

    def importVPN(self):
        successval = True

        print("Beginning IKE Profiles...")
        retval = self.importVPNIKEProfiles()
        if retval is False:
            successval = False
            print('IKE Profile import failure: ', self.lastJSONResponse)
        else:
            print('IKE Profiles imported.')
        print("Beginning VPN Tunnel Profiles...")
        retval = self.importVPNTunnelProfiles()
        if retval is False:
           successval = False
           print('Tunnel profile import failure: ', self.lastJSONResponse)
        else:
           print('Tunnel profiles imported.')

        print("Beginning BGP Neighbors...")
        retval = self.importVPNBGPNeighbors()
        if retval is False:
           successval = False
           print('BGP neighbors import failure: ', self.lastJSONResponse)
        else:
           print('BGP neighbors imported.')

        print("Beginning Local BGP...")
        retval = self.importVPNLocalBGP()
        if retval is False:
            successval = False
            print('Local BGP import failure: ',self.lastJSONResponse )
        else:
            print('Local BGP configuration imported.')

        print("Beginning L3VPN...")
        retval = self.importVPNl3config()
        if retval is False:
            successval = False
            print('L3VPN import failure: ', self.lastJSONResponse)
        else:
            print('L3VPN configurations imported.')

        print("Beginning L2VPN...")
        retval = self.importVPNl2config()
        if retval is False:
            successval = False
            print('L2VPN import failure: ', self.lastJSONResponse)
        else:
            print('L2VPN configurations imported.')

        return successval

    def getAccessToken(self,myRefreshToken):
        """ Gets the Access Token using the Refresh Token """
        params = {'api_token': myRefreshToken}
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = requests.post(f'{self.strCSPProdURL}/csp/gateway/am/api/auth/api-tokens/authorize', params=params, headers=headers)
        jsonResponse = response.json()
        try:
            self.access_token = jsonResponse['access_token']
        except:
            self.access_token = ""
        return self.access_token

    def getNSXTproxy(self, org_id, sddc_id):
        """ Gets the Reverse Proxy URL """
        myHeader = {'csp-auth-token': self.access_token}
        myURL = "{}/vmc/api/orgs/{}/sddcs/{}".format(self.strProdURL, org_id, sddc_id)
        response = requests.get(myURL, headers=myHeader)
        json_response = response.json()
        try:
            self.proxy_url = json_response['resource_config']['nsx_api_public_endpoint_url']
            self.proxy_url_short = self.proxy_url.replace('/sks-nsxt-manager','')
        except:
            self.proxy_url = ""
            print("Unable to get NSX-T proxy URL. API response:")
            print(json_response)
        return self.proxy_url

    def loadConfigFlag(self,config,section,key):
        """Load a True/False flag from the config file"""
        try:
            configoption = config.get(section,key)
            if configoption.lower() == "true":
                return True
            else:
                return False
        except:
            return None

        return None

    def loadConfigRegex(self,config,section,key,delim):
        """Loads delimited regular expressions from a config file"""
        try:
            expressions = config.get(section,key).strip()
            if len(expressions) == 0:
                expressionList = []
            else:
                expressionList = expressions.split(delim)
        except:
            expressionList = []

        return expressionList

    def loadConfigFilename(self,config,section,key):
        """Loads a JSON filename from the config file, with hard-coded defaults if they are missing."""
        try:
            filename  = config.get(section, key)
            return filename
        except:
            if (key == 'cgw_export_filename'):
                return 'cgw.json'
            elif (key == 'cgw_import_filename'):
                return 'cgw.json'
            elif (key == 'mgw_export_filename'):
                return 'mgw.json'
            elif (key == 'mgw_import_filename'):
                return 'mgw.json'
            elif (key == 'network_export_filename'):
                return 'cgw-network.json'
            elif (key == 'network_import_filename'):
                return 'cgw-network.json'
            elif (key == 'public_export_filename'):
                return 'public.json'
            elif (key == 'public_import_filename'):
                return 'public.json'
            elif (key == 'services_filename'):
                return 'services.json'
            elif (key == 'nat_export_filename'):
                return 'natrules.json'
            elif (key == 'nat_import_filename'):
                return 'natrules.json'
            elif (key == 'cgw_groups_filename'):
                return 'cgw_groups.json'
            elif (key == 'mgw_groups_filename'):
                return 'mgw_groups.json'
            elif (key == 'vpn_ike_filename'):
                return 'vpn-ike.json'
            elif (key == 'vpn_dpd_filename'):
                return 'vpn-dpd.json'
            elif (key == 'vpn_tunnel_filename'):
                return 'vpn-tunnel.json'
            elif (key == 'vpn_bgp_filename'):
                return 'vpn-bgp.json'
            elif (key == 'vpn_l3_filename'):
                return 'vpn-l3.json'
            elif (key == 'vpn_l2_filename'):
                return 'vpn-l2.json'
            elif (key == 'sddc_info_filename'):
                return 'sddc_info.json'
            elif (key == 'service_access_filename'):
                return 'service_access.json'
            elif (key == 'vpn_local_bgp_filename'):
                return 'vpn-local-bgp.json'
            elif (key == 'vcenter_folders_filename'):
                return 'vcenterfolderpaths.json'
            elif (key == 'network_dhcp_static_binding_filename'):
                return 'dhcp-static-binding.json'

    def loadDestOrgData(self):
        """Populate destination org properties"""
        jsonResponse = self.loadOrgData(self.dest_org_id)
        if jsonResponse != "":
            self.dest_org_display_name = jsonResponse['display_name']
            return True
        else:
            return False

    def loadSourceOrgData(self):
        """Populate source org properties"""
        jsonResponse = self.loadOrgData(self.source_org_id)
        if jsonResponse != "":
            self.source_org_display_name = jsonResponse['display_name']
            return True
        else:
            return False

    def loadOrgData(self,orgID):
        """Download the JSON for an organization object"""
        myHeader = {'csp-auth-token': self.access_token}
        myURL = self.strProdURL + "/vmc/api/orgs/" + orgID
        try:
            response = requests.get(myURL,headers=myHeader)
            jsonResponse = response.json()
        except:
            jsonResponse = ""
        return jsonResponse

    def loadDestSDDCData(self):
        """Populate source SDDC properties"""
        jsonResponse = self.loadSDDCData(self.dest_org_id, self.dest_sddc_id)
        if jsonResponse != "":
            self.dest_sddc_name = jsonResponse['name']
            self.dest_sddc_state = jsonResponse['sddc_state']
            self.dest_sddc_version = jsonResponse['resource_config']['sddc_manifest']['vmc_version']
            return True
        else:
            return False


    def loadSourceSDDCData(self):
        """Populate dest SDDC properties"""
        jsonResponse = self.loadSDDCData(self.source_org_id, self.source_sddc_id)
        if jsonResponse != "":
            self.source_sddc_name = jsonResponse['name']
            self.source_sddc_state = jsonResponse['sddc_state']
            self.source_sddc_version = jsonResponse['resource_config']['sddc_manifest']['vmc_version']
            self.source_sddc_info = jsonResponse
        else:
            return False

    def exportSourceSDDCData(self):
        """Save the source SDDC data to a file"""
        fname = self.export_path / self.sddc_info_filename
        json_data = self.source_sddc_info
        if self.sddc_info_hide_sensitive_data is True:
            if "cloud_password" in json_data["resource_config"]:
                json_data["resource_config"].pop("cloud_password")
            if "agent" in json_data["resource_config"]:
                if "key_pair" in json_data["resource_config"]["agent"]:
                    if "key_material" in json_data["resource_config"]["agent"]["key_pair"]:
                        json_data["resource_config"]["agent"]["key_pair"].pop("key_material")
        try:
            with open(fname, 'w') as outfile:
                json.dump(json_data, outfile,indent=4)
                return True
        except:
            return False

    def loadSDDCData(self,orgID,sddcID):
        """Download the JSON for an SDDC object"""
        myHeader = {'csp-auth-token': self.access_token}
        myURL = self.strProdURL + "/vmc/api/orgs/" + orgID + "/sddcs/" + sddcID
        try:
            response = requests.get(myURL,headers=myHeader)
            if response.status_code == 200:
                jsonResponse = response.json()
            else:
                jsonResponse = ""
                self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
        except:
            jsonResponse = ""
        return jsonResponse

    def searchOrgUser(self,orgid,userSearchTerm):
        myURL = (self.strCSPProdURL + "/csp/gateway/am/api/orgs/" + orgid + "/users/search?userSearchTerm=" + userSearchTerm)
        response = self.invokeCSPGET(myURL)
        if response is None or response.status_code != 200:
            print(f'Error: {response.status_code}, {response.text}')
            return False

        self.user_search_results_json = response.json()
        return True