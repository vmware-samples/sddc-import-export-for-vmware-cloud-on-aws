# SDDC Import/Export for VMware Cloud on AWS

################################################################################
### Copyright 2020-2023 VMware, Inc.
### SPDX-License-Identifier: BSD-2-Clause
################################################################################

import configparser                     # parsing config file
import datetime
import glob
import json
import random
import requests                         # need this for Get/Post/Delete
import os
import re
import time
import sys

from pathlib import Path
from prettytable import PrettyTable
from zipfile import ZipFile

import vmc_auth

class VMCImportExport:
    """A class to handle importing and exporting portions of a VMC SDDC"""

    def __init__(self,configPath="./config_ini/config.ini", vmcConfigPath="./config_ini/vmc.ini", awsConfigPath="./config/aws.ini", vCenterConfigPath="./config_ini/vcenter.ini"):
        self.vmc_auth = None
        self.proxy_url = None
        self.proxy_url_short = None
        self.lastJSONResponse = None
        self.source_org_display_name = ""
        self.dest_org_display_name = ""
        self.source_sddc_name = ""
        self.source_sddc_version = ""
        self.source_sddc_state = ""
        self.source_sddc_info = ""
        self.source_sddc_nsx_info = ""
        self.source_sddc_nsx_csp_url = ""
        self.source_sddc_enable_nsx_advanced_addon = False
        self.sddc_info_hide_sensitive_data = True
        self.gov_cloud_urls = False
        self.dest_sddc_name = ""
        self.dest_sddc_version = ""
        self.dest_sddc_state = ""
        self.dest_sddc_enable_nsx_advanced_addon = False
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
        self.cgw_groups_import_error_dict = {}
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
        self.vmc_auth = vmc_auth.VMCAuth(strCSPProdURL=self.strCSPProdURL)
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
        self.enable_ipv6 = self.loadConfigFlag(config, 'importConfig', 'enable_ipv6')

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

        # Services
        self.services_import          = self.loadConfigFlag(config,"importConfig","services_import")

        # Groups
        self.compute_groups_import            = self.loadConfigFlag(config,"importConfig","compute_groups_import")
        self.management_groups_import         = self.loadConfigFlag(config,"importConfig","management_groups_import")

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

        #Multi Tier-1 Compute Gateways
        self.mcgw_export = self.loadConfigFlag(config, "exportConfig", "mcgw_export")
        self.mcgw_export_filename = self.loadConfigFilename(config, "exportConfig", "mcgw_export_filename")
        self.mcgw_static_routes_export = self.loadConfigFlag(config, "exportConfig", "mcgw_static_routes_export")
        self.mcgw_static_routes_export_filename = self.loadConfigFilename(config, "exportConfig", "mcgw_static_routes_export_filename")
        self.mcgw_fw_export = self.loadConfigFlag(config, "exportConfig", "mcgw_fw_export")
        self.mcgw_fw_export_filename = self.loadConfigFilename(config, "exportConfig", "mcgw_fw_export_filename")
        self.mcgw_import = self.loadConfigFlag(config, "importConfig", "mcgw_import")
        self.mcgw_import_filename = self.loadConfigFilename(config, "importConfig", "mcgw_import_filename")
        self.mcgw_static_routes_import = self.loadConfigFlag(config, "importConfig", "mcgw_static_route_import")
        self.mcgw_static_route_import_filename = self.loadConfigFilename(config, "importConfig", "mcgw_static_route_import_filename")
        self.mcgw_fw_import = self.loadConfigFlag(config, "importConfig", "mcgw_fw_import")
        self.mcgw_fw_import_filename = self.loadConfigFilename(config, "importConfig", "mcgw_fw_import_filename")

        #Connected VPC Managed Prefix List MOde
        self.mpl_export = self.loadConfigFlag(config, 'exportConfig', 'mpl_export')
        self.mpl_export_filename = self.loadConfigFilename(config, 'exportConfig', 'mpl_export_filename')
        self.mpl_import = self.loadConfigFlag(config, 'importConfig', 'mpl_import')
        self.mpl_import_filename = self.loadConfigFilename(config, 'importConfig', 'mpl_import_filename')

        #SDDC Route Aggregation Lists and Route Configurations
        self.ral_export = self.loadConfigFlag(config, "exportConfig", "ral_export")
        self.ral_export_filename = self.loadConfigFilename(config, "exportConfig", "ral_export_filename")
        self.route_config_export = self.loadConfigFlag(config, "exportConfig", "route_config_export")
        self.route_config_export_filename = self.loadConfigFilename(config, "exportConfig", "route_config_export_filename")
        self.ral_import = self.loadConfigFlag(config, "importConfig", "ral_import")
        self.ral_import_filename = self.loadConfigFilename(config, "importConfig", "ral_import_filename")
        self.route_config_import = self.loadConfigFlag(config, "importConfig", "route_config_import")
        self.route_config_import_filename = self.loadConfigFilename(config, "importConfig", "route_config_import_filename")

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

        #Flexible Segments
        self.flex_segment_export = self.loadConfigFlag(config, "exportConfig", "flex_segment_export")
        self.flex_segment_export_filename = self.loadConfigFilename(config, "exportConfig", "flex_segment_export_filename")
        self.flex_segment_disc_prof_export_filename = self.loadConfigFilename(config, 'exportConfig', 'flex_segment_disc_prof_export_filename')
        self.flex_segment_import = self.loadConfigFlag(config, "importConfig", "flex_segment_import")
        self.flex_segment_import_filename = self.loadConfigFilename(config, "importConfig", "flex_segment_import_filename")
        self.flex_segment_import_exclude_list = self.loadConfigRegex(config, "importConfig", "flex_segment_import_exclude_list", '|')
        self.flex_segment_disc_prof_import_filename = self.loadConfigFilename(config, 'importConfig', 'flex_segment_disc_prof_import_filename')

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
        self.tier1_vpn_export = self.loadConfigFlag(config, 'exportConfig', 't1_vpn_export')
        self.tier1_vpn_export_filename = self.loadConfigFilename(config, 'exportConfig', 't1_vpn_export_filename')
        self.tier1_vpn_service_filename = self.loadConfigFilename(config, 'exportConfig', 't1_vpn_service_filename')
        self.tier1_vpn_le_filename = self.loadConfigFilename(config, 'exportConfig', 't1_vpn_localendpoint_filename')

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

        #Advanced Firewall
        self.nsx_adv_fw_export      = self.loadConfigFlag(config,"exportConfig","nsx_adv_fw_export")
        self.nsx_adv_fw_import      = self.loadConfigFlag(config,"importConfig","nsx_adv_fw_import")
        self.nsx_adv_fw_allow_enable    = self.loadConfigFlag(config,"importConfig","nsx_adv_fw_allow_enable")

        #SDDC Info
        self.sddc_info_filename     = self.loadConfigFilename(config,"exportConfig","sddc_info_filename")
        self.sddc_info_hide_sensitive_data = self.loadConfigFlag(config,"exportConfig","sddc_info_hide_sensitive_data")

        #CSP
        self.RoleSyncSourceUserEmail = config.get("exportConfig","role_sync_source_user_email")
        self.RoleSyncDestUserEmails = config.get("importConfig","role_sync_dest_user_emails").split('|')

    def error_handling(self, response):
        """Helper function to properly report API errors"""
        code = response.status_code
        print(f'API call failed with status code {code}.')
        if code == 301:
            print(f'Error {code}: "Moved Permanently"')
            print("Request must be reissued to a different controller node.")
            print(
                "The controller node has been replaced by a new node that should be used for this and all future requests.")
        elif code == 307:
            print(f'Error {code}: "Temporary Redirect"')
            print("Request should be reissued to a different controller node.")
            print(
                "The controller node is requesting the client make further requests against the controller node specified in the Location header. Clients should continue to use the new server until directed otherwise by the new controller node.")
        elif code == 400:
            print(f'Error {code}: "Bad Request"')
            print("Request was improperly formatted or contained an invalid parameter.")
        elif code == 401:
            print(f'Error {code}: "Unauthorized"')
            print("The client has not authenticated.")
            print("It's likely your refresh token is out of date or otherwise incorrect.")
        elif code == 403:
            print(f'Error {code}: "Forbidden"')
            print("The client does not have sufficient privileges to execute the request.")
            print("The API is likely in read-only mode, or a request was made to modify a read-only property.")
            print("It's likely your refresh token does not provide sufficient access.")
        elif code == 409:
            print(f'Error {code}: "Temporary Redirect"')
            print(
                "The request can not be performed because it conflicts with configuration on a different entity, or because another client modified the same entity.")
            print(
                "If the conflict arose because of a conflict with a different entity, modify the conflicting configuration. If the problem is due to a concurrent update, re-fetch the resource, apply the desired update, and reissue the request.")
        elif code == 412:
            print(f'Error {code}: "Precondition Failed"')
            print(
                "The request can not be performed because a precondition check failed. Usually, this means that the client sent a PUT or PATCH request with an out-of-date _revision property, probably because some other client has modified the entity since it was retrieved. The client should re-fetch the entry, apply any desired changes, and re-submit the operation.")
        elif code == 500:
            print(f'Error {code}: "Internal Server Error"')
            print(
                "An internal error occurred while executing the request. If the problem persists, perform diagnostic system tests, or contact your support representative.")
        elif code == 503:
            print(f'Error {code}: "Service Unavailable"')
            print(
                "The request can not be performed because the associated resource could not be reached or is temporarily busy. Please confirm the ORG ID and SDDC ID entries in your config.ini are correct.")
        else:
            print(f'Error: {code}: Unknown error')
        try:
            json_response = response.json()
            if 'error_message' in json_response:
                print(json_response['error_message'])
            if 'related_errors' in json_response:
                print("Related Errors")
                for r in json_response['related_errors']:
                    print(r['error_message'])
        except:
            print("No additional information in the error response.")
        return None

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
        self.vmc_auth.check_access_token_expiration()
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
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
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

        self.vmc_auth.check_access_token_expiration()
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
                myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
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

        self.vmc_auth.check_access_token_expiration()
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
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
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
                        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
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
            self.CGWDHCPbindings = []
            for network in cgw_networks:
                retval = self.getSDDCCGWDHCPBindings(network['id'])

            fname = self.export_path / self.network_dhcp_static_binding_filename
            with open(fname, 'w') as outfile:
                json.dump(self.CGWDHCPbindings, outfile, indent=4)
        return True
        
    def getSDDCCGWDHCPBindings( self, segment_id: str):
        """Appends any DHCP static bindings for segment_id to the class variable CGWDHCPbindings"""
        myURL = (self.proxy_url + f'/policy/api/v1/infra/tier-1s/cgw/segments/{segment_id}/dhcp-static-binding-configs')
        #print(myURL)
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False

        json_response = response.json()
        #print(json_response)
        if json_response['result_count'] > 0:
            dhcp_static_bindings = json_response['results']
            self.CGWDHCPbindings.append(dhcp_static_bindings)
            #print(self.CGWDHCPbindings)
        else:
            return False

    def export_flexible_segments(self):
        """Exports the flexible segments to a JSON file"""
        my_url = f'{self.proxy_url}/policy/api/v1/infra/segments'
        response = self.invokeCSPGET(my_url)
        json_response = response.json()
        flex_segments = json_response['results']
        fname = self.export_path / self.flex_segment_export_filename
        with open (fname, 'w') as outfile:
            json.dump(flex_segments, outfile, indent=4)
        return True

    def export_flexible_segment_disc_bindings(self):
        """Exports the MAC and IP Discovery binding maps for each flexible segment to JSON"""
        flex_seg_bind = {}
        flex_seg_url = f'{self.proxy_url}/policy/api/v1/infra/segments'
        flex_seg_resp = self.invokeCSPGET(flex_seg_url)
        flex_seg_json = flex_seg_resp.json()
        flex_seg_json = flex_seg_json['results']
        flex_seg_id = []
        for f in flex_seg_json:
            flex_seg_name = f['id']
            flex_seg_id.append(flex_seg_name)

        for x in flex_seg_id:
            my_url = f'{self.proxy_url}/policy/api/v1/infra/segments/{x}/segment-discovery-profile-binding-maps'
            response = self.invokeCSPGET(my_url)
            json_response = response.json()
            disc_bind_map = json_response['results']
            flex_seg_bind[x] = disc_bind_map

        fname = self.export_path / self.flex_segment_disc_prof_export_filename
        with open (fname, 'w') as outfile:
            json.dump(flex_seg_bind, outfile, indent=4)
        return True
        
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

    def export_mcgw_config(self):
        """Exports Multi-T1 CGW configuration to a JSON file"""
        my_url = f'{self.proxy_url}/policy/api/v1/search?query=resource_type:Tier1'
        response = self.invokeCSPGET(my_url)
        if response is None or response.status_code != 200:
            return False
        json_response = response.json()
        #print(json.dumps(json_response, indent=2))
        search_results = json_response['results']
        mcgw_list = []
        for i in search_results:
            if i['id'] == 'mgw':
                pass
            elif i['id'] == 'cgw':
                pass
            else:
                mcgw_list.append(i['id'])
        mcgw_json = {}
        for x in mcgw_list:
            my_url = f'{self.proxy_url}/policy/api/v1/infra/tier-1s/{x}'
            response = self.invokeCSPGET(my_url)
            if response is None or response.status_code != 200:
                return False
            json_response = response.json()
            mcgw_json[x] = json_response
        fname = self.export_path / self.mcgw_export_filename
        with open(fname, 'w') as outfile:
            json.dump(mcgw_json, outfile, indent=4)
        return True

    def export_mcgw_static_routes(self):
        """Exports any static routes configured on a multi-T1 CGW to a JSON file"""
        my_url = f'{self.proxy_url}/policy/api/v1/search?query=resource_type:Tier1'
        response = self.invokeCSPGET(my_url)
        if response is None or response.status_code != 200:
            return False
        json_response = response.json()
        search_results = json_response['results']
        mcgw_list = []
        for i in search_results:
            if i['id'] == 'mgw':
                pass
            elif i['id'] == 'cgw':
                pass
            else:
                mcgw_list.append(i['id'])
        mcgw_staticroutes_json = {}
        for x in mcgw_list:
            my_url = f'{self.proxy_url}/policy/api/v1/infra/tier-1s/{x}/static-routes'
            response = self.invokeCSPGET(my_url)
            if response is None or response.status_code != 200:
                return False
            json_response = response.json()
            mcgw_staticroutes_json[x] = json_response
        fname = self.export_path / self.mcgw_static_routes_export_filename
        with open(fname, 'w') as outfile:
            json.dump(mcgw_staticroutes_json, outfile, indent=4)
        return True

    def export_mcgw_fw(self):
        """Exports all North/South firewall policies"""
        my_url = f'{self.proxy_url}/policy/api/v1/search?query=resource_type:GatewayPolicy'
        response = self.invokeCSPGET(my_url)
        if response is None or response.status_code != 200:
            return False
        json_response = response.json()
        search_results = json_response['results']
        mcgw_policy_list = []
        for i in search_results:
            if i['id'] == 'default':
                pass
            elif i['parent_path'] == '/infra/domains/default':
                pass
            else:
                mcgw_policy_list.append(i['id'])
        mcgw_fw_policy_json = {}
        for x in mcgw_policy_list:
            # print(json.dumps(x, indent=2))
            my_url = f'{self.proxy_url}/policy/api/v1/infra/domains/cgw/gateway-policies/{x}'
            response = self.invokeCSPGET(my_url)
            if response is None or response.status_code != 200:
                return False
            json_response = response.json()
            mcgw_fw_policy_json[x] = json_response
        fname = self.export_path / self.mcgw_fw_export_filename
        with open(fname, 'w') as outfile:
            json.dump(mcgw_fw_policy_json, outfile, indent=4)
        return True


    def export_mpl(self):
        """Exports Connected VPC Managed Prefix List"""
        my_url = f'{self.proxy_url}/cloud-service/api/v1/infra/linked-vpcs'
        response = self.invokeCSPGET(my_url)
        if response is None or response.status_code != 200:
            self.error_handling(response)
            return False
        json_response = response.json()
        mpl_response = json_response['results']
        fname = self.export_path / self.mpl_export_filename
        with open(fname, 'w') as outfile:
            json.dump(mpl_response, outfile, indent=4)
        return True


    def export_ral(self):
        """Exports the SDDCs Route Aggregation List(s)"""
        my_url = f'{self.proxy_url}/cloud-service/api/v1/infra/external/route/aggregations'
        response = self.invokeCSPGET(my_url)
        if response is None or response.status_code != 200:
            return False
        json_response = response.json()
        ral_results = json_response['results']
        fname = self.export_path / self.ral_export_filename
        with open(fname, 'w') as outfile:
            json.dump(ral_results, outfile, indent=4)
        return True

    def export_route_config(self):
        """Exports the SDDC route configuration"""
        my_url = f'{self.proxy_url}/cloud-service/api/v1/infra/external/route/configs'
        response = self.invokeCSPGET(my_url)
        if response is None or response.status_code != 200:
            return False
        json_response = response.json()
        route_config = json_response['results']
        fname = self.export_path / self.route_config_export_filename
        with open(fname, 'w') as outfile:
            json.dump(route_config, outfile, indent=4)
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

        self.vmc_auth.check_access_token_expiration()
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
                myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
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
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
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
                        if len(self.cgw_groups_import_error_dict) > 0:
                            self.check_compute_group_errors(response.text)
                else:
                    print("TEST MODE - DFW rule " + commEnt["display_name"] + " would have been imported.")
        return True

    def check_compute_group_errors(self, response_text: str):
        #  We start with a response_text input of: "Following dependent objects, used in path=[/infra/domains/cgw/security-policies/Security-demo/rules/within_backend], does not exist path=[/infra/domains/cgw/groups/Security-backend,/infra/domains/cgw/groups/Security-backend]."

        split1=response_text.split("does not exist path=")
        if len(split1) > 1:
            buf = split1[1]
            # Our first split leaves us with this saved in buf [/infra/domains/cgw/groups/Security-backend,/infra/domains/cgw/groups/Security-backend].
            start_char = buf.find("[")
            end_char = buf.find("]")
            if start_char >= 0 and end_char > start_char:
                # Extract the string between the []
                not_exist_groups= buf[start_char+1:end_char]

                # Split on a comma to get a list object containing the group objects
                not_exist_groups_list = not_exist_groups.split(",")

                # See if any of the group objects are found in the group import error object
                for group in not_exist_groups_list:
                    if group in self.cgw_groups_import_error_dict:
                        print(f'INFO - Firewall rule import failed because group object {self.cgw_groups_import_error_dict[group]["display_name"]} was not imported. The group object import failure error was: {self.cgw_groups_import_error_dict[group]["error_message"]}')
            else:
                print("checkGroupErrors() - could not find start and end brackets")

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

        debug_mode = False
        debug_page_size = 20

        myURL = (self.proxy_url + "/policy/api/v1/infra/services")
        if debug_mode:
            myURL += f'?page_size={debug_page_size}'
            print(f'DEBUG, page size set to {debug_page_size}, calling {myURL}')
        response = self.invokeVMCGET(myURL)
        if response is None or response.status_code != 200:
            return False
        json_response = response.json()
        sddc_services = json_response['results']
        result_count = json_response['result_count']
        if debug_mode:
            print(f'Result count: {result_count}')

        # After grabbing an intial set of results, check for presence of a cursor
        while "cursor" in json_response:
            #print(json_response)
            result_count -= debug_page_size
            myURL = self.proxy_url + "/policy/api/v1/infra/services?cursor=" + json_response['cursor']
            if debug_mode:
                print(f'{result_count} records to go.')
                myURL += f'&page_size={debug_page_size}'
                print(f'DEBUG, page size set to {debug_page_size}, calling {myURL}')
            response = self.invokeVMCGET(myURL)
            if response is None or response.status_code != 200:
                return False
            json_response = response.json()
            sddc_services.extend(json_response['results'])

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


    def export_tier1_vpn(self):
        """Exports the Tier-1 VPN Services"""
        t1_url = f'{self.proxy_url}/policy/api/v1/infra/tier-1s'
        t1_response = self.invokeVMCGET(t1_url)
        if t1_response.status_code != 200:
            self.error_handling(t1_response)
            return False
        t1_json = t1_response.json()
        t1_lst = []
        for t in t1_json['results']:
            if t['_create_user'] != 'admin':
                t1_lst.append(t['id'])
        if self.vpn_export is False:
            self.exportVPNIKEProfiles()
            self.exportVPNTunnelProfiles()
            self.exportVPNDPDProfiles()
            self.exportVPNBGPNeighbors()
            self.exportVPNLocalBGP()
        t1_vpn_service_dict = {}
        t1_vpn_le_dict = {}
        t1_vpn_dict = {}
        for t in t1_lst:
            t1_vpn_service_url = f'{self.proxy_url}/policy/api/v1/infra/tier-1s/{t}/ipsec-vpn-services'
            t1_vpn_service_response = self.invokeVMCGET(t1_vpn_service_url)
            if t1_vpn_service_response.status_code == 200:
                t1_vpn_service_json = t1_vpn_service_response.json()
                t1_vpn_service = t1_vpn_service_json['results']
                if t1_vpn_service:
                    t1_vpn_service_dict[t] = t1_vpn_service
                    t1_vpn_service_id = t1_vpn_service[0]['id']

                    t1_vpn_le_url = f'{self.proxy_url}/policy/api/v1/infra/tier-1s/{t}/ipsec-vpn-services/{t1_vpn_service_id}/local-endpoints'
                    t1_vpn_le_response = self.invokeVMCGET(t1_vpn_le_url)
                    if t1_vpn_le_response.status_code == 200:
                        t1_vpn_le_json = t1_vpn_le_response.json()
                        t1_vpn_le = t1_vpn_le_json['results']
                        if t1_vpn_le:
                            t1_vpn_le_dict[t1_vpn_service_id] = t1_vpn_le
                        else:
                            pass
                    else:
                        self.error_handling(t1_vpn_le_response)
                        return False

                    t1_vpn_url = f'{self.proxy_url}/policy/api/v1/infra/tier-1s/{t}/ipsec-vpn-services/{t1_vpn_service_id}/sessions'
                    t1_vpn_response = self.invokeCSPGET(t1_vpn_url)
                    if t1_vpn_response.status_code == 200:
                        t1_vpn_json = t1_vpn_response.json()
                        t1_vpn_json = t1_vpn_json['results']
                        if t1_vpn_json:
                            for v in t1_vpn_json:
                                if self.sddc_info_hide_sensitive_data is True:
                                    t1_vpn_dict[t1_vpn_service_id] = v
                                else:
                                    t1_vpn_id = v['id']
                                    t1_vpn_sen_url = f'{self.proxy_url}/policy/api/v1/infra/tier-1s/{t}/ipsec-vpn-services/{t1_vpn_service_id}/sessions/{t1_vpn_id}?action=show_sensitive_data'
                                    t1_vpn_sen_response = self.invokeCSPGET(t1_vpn_sen_url)
                                    if t1_vpn_sen_response.status_code == 200:
                                        t1_vpn_sen_json = t1_vpn_sen_response.json()
                                        t1_vpn_dict[t1_vpn_service_id] = t1_vpn_sen_json
                                    else:
                                        self.error_handling(t1_vpn_sen_response)
                                        return False
                        else:
                            pass
                    else:
                        self.error_handling(t1_vpn_response)
                        return False
                else:
                    pass
            else:
                self.error_handling(t1_vpn_service_response)
                return False

        if t1_vpn_service_dict:
            fname = self.export_path / self.tier1_vpn_service_filename
            with open(fname, 'w') as outfile:
                json.dump(t1_vpn_service_dict, outfile, indent=4)

        if t1_vpn_le_dict:
            lname = self.export_path / self.tier1_vpn_le_filename
            with open(lname, 'w') as lefile:
                json.dump(t1_vpn_le_dict, lefile, indent=4)

        if t1_vpn_dict:
            vname = f'{self.export_path}/{self.tier1_vpn_export_filename}'
            with open(vname, 'w') as outfile:
                json.dump(t1_vpn_dict, outfile, indent=4)

        return True


    def getVPNl3sensitivedata(self,l3vpnid):
        """ Retrieve sensitive data such as IPSEC preshared keys from an L3VPN configuration"""
        myHeader = {'csp-auth-token': self.vmc_auth.access_token}
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
        self.vmc_auth.check_access_token_expiration()
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
                myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
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
    
    def import_flex_segments(self):
        """Imports flexible segments from a JSON file"""
        self.vmc_auth.check_access_token_expiration()
        fname = self.import_path / self.flex_segment_import_filename
        try:
            with open (fname) as filehandle:
                flex_segments = json.load(filehandle)
        except:
            print(f'Import failed - unable to open {filehandle}')
            return
        import_results = {}
        irKey = 0
        for f in flex_segments:
            skip_network = False
            for e in self.flex_segment_import_exclude_list:
                m = re.match(e,f['display_name'])
                if m:
                    print(f"{f['display_name']}, skipped - matches excluseion regex")
                    skip_network = True
                    break
                if skip_network is True:
                    continue
                result = ""
                result_note = ""
                json_data = {}
                json_data['id'] = f['id']
                json_data['display_name'] = f['display_name']
                json_data['type'] = f['type']
                json_data['resource_type'] = f['resource_type']
                json_data['advanced_config'] = f['advanced_config']
                if f['type'] == 'ROUTED':
                    json_data['connectivity_path'] = f['connectivity_path']
                    json_data['subnets'] = f['subnets']
                uri_path = f['path']
                if self.import_mode == 'live':
                    my_header = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token}
                    my_url = f'{self.proxy_url}/policy/api/v1{uri_path}'
                    if self.sync_mode is True:
                        response = requests.patch(my_url, headers = my_header, json = json_data)
                    else:
                        response = requests.put(my_url, headers = my_header, json = json_data)
                    if response.status_code == 200:
                        result = "SUCCESS"
                        print(f'Segment {f["display_name"]} has been imported')
                    else:
                        result = "FAIL"
                        result_note += f'API call status {response.status_code}, text:{response.text}'
                else:
                    result = "TEST"
                    result_note += f'TEST Mode, no changes made. {f["display_name"]} would have been imported'
                current_result = {'id':f['id'], 'display_name':f['display_name'], 'result':result, 'result_note':result_note}
                import_results[irKey] = current_result
                irKey += 1
        table = PrettyTable(['Display Name', 'Result', 'Result Note', 'Segment ID'])
        for i in import_results:
            table.add_row([import_results[i]['display_name'], import_results[i]['result'], import_results[i]['result_note'], import_results[i]['id']])
        return table

    def import_flex_seg_disc_binding_map(self):
        """Imports Segment profile binding maps for all imported flexible segments"""
        self.vmc_auth.check_access_token_expiration()
        fname = self.import_path / self.flex_segment_disc_prof_export_filename
        try:
            with open (fname) as filehandle:
                binding_maps = json.load(filehandle)
        except:
            print(f"Import failed - unable to open {filehandle}")
            return
        for b in binding_maps.values():
            if b:
                json_data = {}
                json_data['mac_discovery_profile_path'] = b[0]['mac_discovery_profile_path']
                json_data['ip_discovery_profile_path'] = b[0]['ip_discovery_profile_path']
                json_data['resource_type'] = b[0]['resource_type']
                json_data['id'] = b[0]['id']
                json_data['display_name'] = b[0]['display_name']
                uri_path = b[0]['path']

                if self.import_mode == 'live':
                    my_header = {"Content-Type": "application/json", "Accept": "application/json",
                                 'csp-auth-token': self.vmc_auth.access_token}
                    my_url = f'{self.proxy_url}/policy/api/v1{uri_path}'
                    response = requests.put(my_url, headers = my_header, json = json_data)
                    if response.status_code == 200:
                        print(f'Discovery binding map has been updated for segment {b[0]["parent_path"]}')
                    else:
                        self.error_handling(response)
                else:
                    print(f'TEST MODE - Discovery binding map for segment {b[0]["parent_path"]} would have been imported')
            else:
                pass

    def importCGWDHCPStaticBindings(self):
        self.vmc_auth.check_access_token_expiration()
        fname = self.import_path / self.network_dhcp_static_binding_filename
        try:
            with open(fname) as filehandle:
                bindings = json.load(filehandle)
        except:
            print('Import failed - unable to open', fname)
            return

        for binding in bindings[0]:
            payload = {}
            for x in binding:
                # Strip out underscore keys - these are system generated and cannot be imported
                if x[0:1]  != '_':
                    payload[x] = binding[x]

            if self.import_mode == 'live':
                myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
                myURL = self.proxy_url + "/policy/api/v1" +  binding['path']
                if self.sync_mode is True:
                    response = requests.patch(myURL, headers=myHeader, json=payload)
                else:
                    response = requests.put(myURL, headers=myHeader, json=payload)
                if response.status_code == 200:
                    result = "SUCCESS"
                    print(f'Added {payload["display_name"]}')
                else:
                    result = "FAIL"
                    print( f'API Call Status {response.status_code}, text:{response.text}')
            else:
                print(f'TEST MODE: Would have added binding {payload["display_name"]}')


    def importSDDCServices(self):
        """Import all services from a JSON file"""
        self.vmc_auth.check_access_token_expiration()
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
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
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

    def import_mcgw(self):
        """Import Tier-1 gateways from a JSON file"""
        self.vmc_auth.check_access_token_expiration()
        fname = self.import_path / self.mcgw_import_filename
        try:
            with open(fname) as filehandle:
                mcgws = json.load(filehandle)
        except:
            print(f'Import failed - unable to open {fname}')
            return
        for mcgw in mcgws.values():
            json_data = {}
            if self.import_mode == "live":
                json_data['id'] = mcgw['id']
                json_data['display_name'] = mcgw['display_name']
                json_data['type'] = mcgw['type']
                if 'dhcp_config_paths' in mcgw:
                    json_data['dhcp_config_paths'] = mcgw['dhcp_config_paths']
            my_header = {"Content-Type": "application/json", "Accept": "application/json", "csp-auth-token": self.vmc_auth.access_token}
            my_url = self.proxy_url + '/policy/api/v1/infra/tier-1s/' + mcgw['id']
            if self.sync_mode is True:
                response = requests.patch(my_url, headers=my_header, json=json_data)
            else:
                response = requests.put(my_url, headers=my_header, json=json_data)
            if response.status_code == 200:
                result = "SUCCESS"
                print('Added {}'.format(json_data['display_name']))
            else:
                result = "FAIL"
                print(f'API Call Status {response.status_code}, text:{response.text}')

    def import_mcgw_static_routes(self):
        """Import Tier-1 Gateway static routes from a JSON file"""
        self.vmc_auth.check_access_token_expiration()
        fname = self.import_path / self.mcgw_static_route_import_filename
        try:
            with open(fname) as filehandle:
                routes = json.load(filehandle)
        except:
            print(f'Import failed - unable to open {fname}')
            return
        if self.import_mode == 'live':
            for route in routes.values():
                for r in route['results']:
                    json_data = {}
                    json_data['display_name'] = r['display_name']
                    json_data['id'] = r['id']
                    json_data['network'] = r['network']
                    json_data['next_hops'] = r['next_hops']
                    json_data['resource_type'] = r['resource_type']
                    path = r['path']
                    my_header = {"Content-Type": "application/json", "Accept": "application/json",
                                 "csp-auth-token": self.vmc_auth.access_token}
                    my_url = f'{self.proxy_url}/policy/api/v1{path}'
                    if self.sync_mode is True:
                        response = requests.patch(my_url, headers=my_header, json=json_data)
                    else:
                        response = requests.put(my_url, headers=my_header, json=json_data)
                    if response.status_code == 200:
                        result = "SUCCESS"
                        print('Added {}'.format(json_data['display_name']))
                    else:
                        result = "FAIL"
                        print(f'API Call Status {response.status_code}, text:{response.text}')
        else:
            print(f"TEST MODE - Tier 1 Gateway static routes would have been imported.")

    def import_mcgw_fw(self):
        """Import Tier-1 Gateway firewall policies and rules from a JSON file"""
        self.vmc_auth.check_access_token_expiration()
        fname = self.import_path / self.mcgw_fw_import_filename
        try:
            with open(fname) as filehandle:
                rules = json.load(filehandle)
        except:
            print(f'Import failed - unable to open {fname}')
            return
        if self.import_mode == 'live':
            for policy in rules.values():
                # print(json.dumps(policy, indent=2))
                # import and create the top level firewall policy
                json_policy_data = {}
                json_policy_data['resource_type'] = policy['resource_type']
                json_policy_data['id'] = policy['id']
                json_policy_data['display_name'] = policy['display_name']
                json_policy_data['category'] = policy['category']
                path = policy['path']
                my_header = {"Content-Type": "application/json", "Accept": "application/json", "csp-auth-token": self.vmc_auth.access_token}
                my_url = f'{self.proxy_url}/policy/api/v1{path}'
                if self.sync_mode is True:
                    response = requests.patch(my_url, headers=my_header, json=json_policy_data)
                else:
                    response = requests.put(my_url, headers=my_header, json=json_policy_data)
                if response.status_code == 200:
                    result = "SUCCESS"
                    print(f'Added {json_policy_data["id"]} firewall policy')
                else:
                    result = "FAIL"
                    print(f'API Call Status {response.status_code}, text:{response.text}')
                json_rule_data = {}
                rules = policy['rules']
                for r in rules:
                    # import and create firewall rules assigned to the top level policy
                    json_rule_data['action'] = r['action']
                    json_rule_data['id'] = r['id']
                    json_rule_data['display_name'] = r['display_name']
                    json_rule_data['source_groups'] = r['source_groups']
                    json_rule_data['destination_groups'] = r['destination_groups']
                    json_rule_data['services'] = r['services']
                    json_rule_data['profiles'] = r['profiles']
                    json_rule_data['scope'] = r['scope']
                    json_rule_data['sequence_number'] = r['sequence_number']
                    json_rule_data['direction'] = r['direction']
                    json_rule_data['ip_protocol'] = r['ip_protocol']
                    json_rule_data['tag'] = r['tag']
                    path = r['path']
                    my_header = {"Content-Type": "application/json", "Accept": "application/json",
                                 "csp-auth-token": self.vmc_auth.access_token}
                    my_url = f'{self.proxy_url}/policy/api/v1{path}'
                    if self.sync_mode is True:
                        response = requests.patch(my_url, headers=my_header, json=json_rule_data)
                    else:
                        response = requests.put(my_url, headers=my_header, json=json_rule_data)
                    if response.status_code == 200:
                        result = "SUCCESS"
                        print(f'Added {json_rule_data["display_name"]} firewall rule')
                    else:
                        result = "FAIL"
                        print(f'API Call Status {response.status_code}, text:{response.text}')
        else:
            print(f"TEST MODE - Tier 1 Gateway firewall policy and rules would have been imported.")


    def import_mpl(self):
        """Import/Configuration Connected VPC Managed Prefix List"""
        self.vmc_auth.check_access_token_expiration()
        fname = self.import_path / self.mpl_import_filename
        try:
            with open(fname) as filehandle:
                mpl = json.load(filehandle)
        except:
            print(f'Import failed - unable to open {fname}')
            return
        if self.import_mode == 'live':
          for m in mpl:
            if m['linked_vpc_managed_prefix_list_info']['managed_prefix_list_mode'] == 'ENABLED':
                vpc_id = m['linked_vpc_id']
                my_header = {"Content-Type": "application/json", "Accept": "application/json", "csp-auth-token": self.vmc_auth.access_token}
                my_url = f'{self.proxy_url}/cloud-service/api/v1/linked-vpcs/{vpc_id}?action=enable_managed_prefix_list_mode'
                response = requests.post(my_url, headers=my_header)
                if response.status_code == 200:
                    result = "SUCCESS"
                    print('Enabled Managed Prefix List Mode. Proceed to the AWS Management Console and Resource Access Manager to accept the share')
                else:
                    self.error_handling(response)
                    result = "FAIL"
        else:
            print("TEST MODE - Connected VPC Managed Prefix List mode would have been enabled")



    def import_ral(self):
        """Import SDDC Route Aggregation lists from JSON"""
        self.vmc_auth.check_access_token_expiration()
        fname = self.import_path / self.ral_import_filename
        try:
            with open(fname) as filehandle:
               ral = json.load(filehandle)
        except:
            print(f'Import failed - unable to open {fname}')
            return
        if self.import_mode == 'live':
            for r in ral:
                json_data = {}
                json_data['display_name'] = r['display_name']
                json_data['prefixes'] = r['prefixes']
                json_data['resource_type'] = r['resource_type']
                json_data['id'] = r['id']
                path = r['path']
                # print(json.dumps(json_data, indent=2))
                my_header = {"Content-Type": "application/json", "Accept": "application/json", "csp-auth-token": self.vmc_auth.access_token}
                my_url = f'{self.proxy_url}/cloud-service/api/v1{path}'
                response = requests.put(my_url, headers=my_header, json=json_data)
                if response.status_code == 200:
                    result = "SUCCESS"
                    print(f'Added {json_data["display_name"]} route aggregation list')
                else:
                    result = "FAIL"
                    print(f'API Call Status {response.status_code}, text:{response.text}')
        else:
            print(f'TEST Mode - Route Aggregation lists would have been imported')

    def import_route_config(self):
        """Imports SDDC route configuration from JSON"""
        self.vmc_auth.check_access_token_expiration()
        fname = self.import_path / self.route_config_import_filename
        try:
            with open(fname) as filehandle:
                config = json.load(filehandle)
        except:
            print(f'Import failed - unable to open {fname}')
            return
        if self.import_mode == 'live':
            for r in config:
                json_data = {}
                json_data['display_name'] = r['display_name']
                json_data['resource_type'] = r['resource_type']
                json_data['id'] = r['id']
                json_data['aggregation_route_config'] = r['aggregation_route_config']
                json_data['connectivity_endpoint_path'] = r['connectivity_endpoint_path']
                my_header = {"Content-Type": "application/json", "Accept": "application/json",
                             "csp-auth-token": self.vmc_auth.access_token}
                my_url = f'{self.proxy_url}/cloud-service/api/v1/infra/external/route/configs/{r["id"]}'
                response = requests.put(my_url, headers=my_header, json=json_data)
                if response.status_code == 200:
                    result = "SUCCESS"
                    print(f'Added {json_data["display_name"]} route configuration')
                else:
                    result = "FAIL"
                    print(f'API Call Status {response.status_code}, text:{response.text}')
        else:
            print(f'TEST Mode - Route configuration would have been imported')

    def convertServiceRolePayload(self, sourcePayload: str) -> bool:
        """Converts a ServiceRole payload from its default format to the format required to add it to a User. Saves results to convertedServiceRolePayload """
        self.convertedServiceRolePayload = {}
        servicedefs = []
        for servicedef in sourcePayload:
            modified_def = {}
            role = {}
            modified_def['serviceDefinitionId'] = servicedef['serviceDefinitionId']
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
        self.vmc_auth.check_access_token_expiration()
        try:
            response = requests.get(url,headers= {"Authorization":"Bearer " + self.vmc_auth.access_token})
            if response.status_code != 200:
                self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
            return response
        except Exception as e:
                self.lastJSONResponse = e
                return None

    def invokeVMCGET(self,url: str) -> requests.Response:
        """Invokes a VMC On AWS GET request"""
        self.vmc_auth.check_access_token_expiration()
        myHeader = {'csp-auth-token': self.vmc_auth.access_token}
        attempts = 1
        status_code = 0
        try:
            while attempts <=3 and status_code != 200:
                if attempts > 1:
                    print('Retrying...')
                response = requests.get(url,headers=myHeader)
                status_code = response.status_code
                if status_code == 200:
                    break
                self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
                if status_code == 504:
                    attempts +=1
                    print('Received gateway time out error 504, pausing...')
                    time.sleep(5)
            return response
        except Exception as e:
                self.lastJSONResponse = e
                return None

    def invokeVMCPUT(self, url: str,json_data: str) -> requests.Response:
        """Invokes a VMC on AWS PUT request"""
        self.vmc_auth.check_access_token_expiration()
        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
        try:
            response = requests.put(url,headers=myHeader,data=json_data)
            if response.status_code != 200:
                self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
            return response
        except Exception as e:
            self.lastJSONResponse = e
            return None

    def invokeVMCPATCH(self, url: str,json_data: str) -> requests.Response:
        """Invokes a VMC on AWS PATCH request"""
        self.vmc_auth.check_access_token_expiration()
        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
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

    def findRandomTestbedVM(self) -> str:
        self.vmc_auth.check_access_token_expiration()
        """Looks for any of the first 100 VMs available in NSX-T - used to generate realistic group members for a testbed"""
        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
        myURL = self.proxy_url + '/policy/api/v1/search/aggregate?page_size=100'
        json_data = {"primary":{"resource_type":"VirtualMachine","filters":[{"field_names":"!tags.tag","value":"nsx_policy_internal"},{"field_names":"!display_name","value":"(\"NSX-Edge-0\" OR \"NSX-Edge-1\" OR \"NSX-Manager-0\" OR \"NSX-Manager-1\" OR \"NSX-Manager-2\" OR \"vcenter\")"}]},"related":[{"resource_type":"TransportNode OR HostNode","join_condition":"id:source.target_id","alias":"TransportNode"},{"resource_type":"VirtualNetworkInterface","join_condition":"owner_vm_id:external_id","alias":"VirtualNetworkInterface"},{"resource_type":"HostNode","join_condition":"id:host_id","alias":"HostNode","size":0},{"resource_type":"DiscoveredNode","join_condition":"external_id:$2.discovered_node_id","alias":"DiscoveredNode","size":0},{"resource_type":"ComputeManager","join_condition":"id:$3.origin_id","alias":"ComputeManager"}],"data_source":"ALL"}
        response = requests.post(myURL, headers=myHeader, data=json.dumps(json_data))
        if response.status_code != 200:
            self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
            return None
        json_response = response.json()
        vm_list = json_response['results']
        if len(vm_list) == 0:
            return None
        i = random.randint(0,len(vm_list)-1)
        return(vm_list[i]['primary']['display_name'])
        #print(json_response)

    def createSDDCCGWGroup(self, group_name: str, vm_name_to_add: str = None):
        """Creates a new CGW Group"""
        self.vmc_auth.check_access_token_expiration()
        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
        myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/groups/" + group_name

        if vm_name_to_add is None:
            vm_name_to_add = "sample_vm_" + group_name

        json_data = {
            "expression": [
                {
                    "ip_addresses": [
                        "192.168.100.1"
                    ],
                    "resource_type": "IPAddressExpression"
                },
                {
                    "conjunction_operator": "OR",
                    "resource_type": "ConjunctionOperator"
                },
                {
                    "member_type": "VirtualMachine",
                    "key": "Name",
                    "operator": "EQUALS",
                    "value": vm_name_to_add,
                    "resource_type": "Condition"
                }
            ],
            "display_name":group_name, "id":group_name 
        }

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
        self.vmc_auth.check_access_token_expiration()
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
        """Deletes a CGW Group"""
        self.vmc_auth.check_access_token_expiration()
        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
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

            self.vmc_auth.check_access_token_expiration()
            debug_mode = False
            debug_page_size = 20

            myURL = (self.proxy_url + "/policy/api/v1/infra/domains/cgw/groups")

            if debug_mode:
                myURL += f'?page_size={debug_page_size}'
                print(f'DEBUG, page size set to {debug_page_size}, calling {myURL}')
            response = self.invokeVMCGET(myURL)
            if response is None or response.status_code != 200:
                return False
            json_response = response.json()
            cgw_groups = json_response['results']
            result_count = json_response['result_count']
            if debug_mode:
                print(f'Result count: {result_count}')

            # After grabbing an intial set of results, check for presence of a cursor
            while "cursor" in json_response:
                result_count -= debug_page_size
                myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/groups?cursor=" + json_response['cursor']
                if debug_mode:
                    print(f'{result_count} records to go.')
                    myURL += f'&page_size={debug_page_size}'
                    print(f'DEBUG, page size set to {debug_page_size}, calling {myURL}')
                response = self.invokeVMCGET(myURL)
                if response is None or response.status_code != 200:
                    return False
                json_response = response.json()
                cgw_groups.extend(json_response['results'])

            fname = self.export_path / self.cgw_groups_filename
            with open(fname, 'w') as outfile:
                json.dump(cgw_groups, outfile,indent=4)

            return True

    def enable_advanced_firewall_dest(self) -> bool:
        """Enable the NSX advanced firewall in the destination SDDC"""
        self.vmc_auth.check_access_token_expiration()
        myURL = (self.strProdURL  + f'/vmc/skynet/api/orgs/{self.dest_org_id}/sddcs/{self.dest_sddc_id}/nsx-advanced-addon?enable=true')
        myHeader = {"Authorization":"Bearer " + self.vmc_auth.access_token}
        if self.import_mode == "live":
            response = requests.post(myURL,headers=myHeader)
            if response is None or (response.status_code != 200 and response.status_code != 201 and response.status_code != 202):
                self.lastJSONResponse = f'API Call Status {response.status_code}, text:{response.text}'
                print(f'API Call Status {response.status_code}, text:{response.text}')
                return False
            else:
                print(f'Enabled NSX Advanced Firewall in dest SDDC {self.dest_sddc_id}')
        else:
            print(f'TEST MODE - Would have enabled NSX Advanced Firewall in SDDC {self.dest_sddc_id}')

        return True

    def import_advanced_firewall(self):
        self.vmc_auth.check_access_token_expiration()
        if self.dest_sddc_enable_nsx_advanced_addon is False:
            if self.nsx_adv_fw_allow_enable is True:
                print("nsx_adv_fw_allow_enable set to True, attempting to enable the NSX Advanced Firewall in the destination SDDC...")
                retval = self.enable_advanced_firewall_dest()
                if retval is False:
                    print("ERROR - Failed to enable NSX Advanced Firewall - unable to import")
                    return

                print("NSX advanced firewall has been enabled.")
            else:
                print("ERROR - Unable to import advanced firewall config - the advanced firewall add-on is disabled in the destination SDDC. You can try to automatically enable the feature with the `nsx_adv_fw_allow_enable` flag in config.ini")
                return

        print("Feature not implemented")

    def importSDDCCGWRule(self):
        """Import all CGW Rules from a JSON file"""

        self.vmc_auth.check_access_token_expiration()
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
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
                    myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/gateway-policies/default/rules/" + rule["id"]
                    json_data = json.dumps(payload)
                    if self.sync_mode is True:
                        createfwruleresp = requests.patch(myURL,headers=myHeader,data=json_data)
                    else:
                        createfwruleresp = requests.put(myURL,headers=myHeader,data=json_data)

                    if  createfwruleresp.status_code == 200:
                        print("Firewall Rule " + payload["display_name"] + " has been imported.")
                    else:
                        self.lastJSONResponse = f'API Call Status {createfwruleresp.status_code}, text:{createfwruleresp.text}'
                        print(f'API Call Status {createfwruleresp.status_code}, text:{createfwruleresp.text}')
                        if len(self.cgw_groups_import_error_dict) > 0:
                            self.check_compute_group_errors(createfwruleresp.text)  
                else:
                    print("TEST MODE - Firewall Rule " + payload["display_name"] + " would have been imported." )
                payload = {}
        return True


    def importSDDCCGWGroup(self):
        """Import all CGW groups from a JSON file"""
        self.vmc_auth.check_access_token_expiration()
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
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
                    myURL = self.proxy_url + "/policy/api/v1/infra/domains/cgw/groups/" + group["id"]
                    if "expression" in group:
                        group_expression = group["expression"]
                        for item in group_expression:
                            if item["resource_type"] == "ExternalIDExpression":
                                skip_vm_expression = True
                                msg = f'CGW Group {group["display_name"]} cannot be imported as it relies on VM external ID.'
                                print(msg)
                                path = "/infra/domains/cgw/groups/" + group["id"]
                                self.cgw_groups_import_error_dict[path] = { "display_name": payload["display_name"] , "error_message": msg }
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

        self.vmc_auth.check_access_token_expiration()
        # First, retrieve the linked VPC ID
        myHeader = {'csp-auth-token': self.vmc_auth.access_token}
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
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
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
        self.vmc_auth.check_access_token_expiration()
        fname = self.import_path / self.vpn_local_bgp_filename
        with open(fname) as filehandle:
            local_bgp = json.load(filehandle)
            payload = {}
            payload["local_as_num"] = local_bgp ["local_as_num"]
            if self.import_mode == 'live':
                myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
                myURL = self.proxy_url + "/policy/api/v1/infra/tier-0s/vmc/locale-services/default/bgp"
                json_data = json.dumps(payload)
                # Always using PATCH here because this BGP object always exists in any SDDC
                bgppresp = requests.patch(myURL,headers=myHeader,data=json_data)
                if bgppresp.status_code == 200:
                    print("Local BGP config  has been imported.")
                else:
                    self.error_handling(bgppresp)
            else:
                print("TEST MODE - Local BGP config  would have been imported.")


    def importVPNBGPNeighbors(self):
        self.vmc_auth.check_access_token_expiration()
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
                            myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
                            myURL = self.proxy_url + "/policy/api/v1/infra/tier-0s/vmc/locale-services/default/bgp/neighbors/" + bgpentry["id"]
                            json_data = json.dumps(payload)
                            if self.sync_mode is True:
                                bgppresp = requests.patch(myURL,headers=myHeader,data=json_data)
                            else:
                                bgppresp = requests.put(myURL,headers=myHeader,data=json_data)
                            if bgppresp.status_code == 200:
                                print("BGP neighbor " + payload["display_name"] + " has been imported.")
                            else:
                                self.error_handling(bgppresp)
                        else:
                            print("TEST MODE - BGP Neighbor " +  payload["display_name"] + " created by " + bgpentry["_create_user"] + " would have been imported.")


    def importVPNTunnelProfiles(self):
        self.vmc_auth.check_access_token_expiration()
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
                        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
                        myURL = self.proxy_url + "/policy/api/v1/infra/ipsec-vpn-tunnel-profiles/" + tunp["id"]
                        json_data = json.dumps(payload)
                        if self.sync_mode is True:
                            tunpresp = requests.patch(myURL,headers=myHeader,data=json_data)
                        else:
                            tunpresp = requests.put(myURL,headers=myHeader,data=json_data)
                        if tunpresp.status_code == 200:
                            print("Tunnel Profile " + payload["display_name"] + " has been imported.")
                        else:
                            self.error_handling(tunpresp)
                    else:
                        print("TEST MODE - Tunnel Profile " +  payload["display_name"] + " created by " + tunp["_create_user"] + " would have been imported.")

    def importVPNDPDProfiles(self):
        self.vmc_auth.check_access_token_expiration()
        fname = self.import_path / self.vpn_dpd_filename
        with open(fname) as filehandle:
            dpdps = json.load(filehandle)
            payload = {}
            for dpdp in dpdps:
                if dpdp['_system_owned'] is False:
                    payload['id'] = dpdp['id']
                    payload['display_name'] = dpdp['display_name']
                    payload['dpd_probe_mode'] = dpdp['dpd_probe_mode']
                    payload['dpd_probe_interval'] = dpdp['dpd_probe_interval']
                    payload['retry_count'] = dpdp['retry_count']
                    payload['enabled'] = dpdp['enabled']
                    payload['_create_user'] = dpdp['_create_user']
                    profile_url = dpdp['path']
                    if self.import_mode == 'live':
                        my_header = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
                        my_url = f"{self.proxy_url}/policy/api/v1{profile_url}"
                        json_data = json.dumps(payload)
                        if self.sync_mode is True:
                            response = requests.patch(my_url, headers=my_header, data=json_data)
                        else:
                            response = requests.put(my_url, headers=my_header, data=json_data)
                        if response.status_code == 200:
                            print(f"DPD Profile {payload['display_name']} has been imported")
                        else:
                            self.error_handling(response)
                    else:
                        print(f"TEST MODE - DPD Profile {payload['display_name']} created by {payload['_create_user']} would have been imported")


    def importVPNl2config(self):
        self.vmc_auth.check_access_token_expiration()
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
                        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
                        myURL = self.proxy_url + f'/policy/api/v1/infra/tier-0s/vmc/locale-services/default/l2vpn-services/default/sessions/{payload["id"]}'
                        if self.sync_mode is True:
                            l2vpnresp = requests.patch(myURL,headers=myHeader,data=json_data)
                        else:
                            l2vpnresp = requests.put(myURL,headers=myHeader,data=json_data)
                        if l2vpnresp.status_code == 200:
                            print("L2VPN " + payload["id"] + " has been imported.")
                        else:
                            self.error_handling(l2vpnresp)
                    else:
                        print("TEST MODE - L2VPN " + l2vpn["id"] + " created by " + l2vpn["_create_user"] + " would have been imported.")
        return True


    def importVPNl3config(self):
        self.vmc_auth.check_access_token_expiration()
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
                        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
                        myURL = self.proxy_url + f'/policy/api/v1/infra/tier-0s/vmc/locale-services/default/ipsec-vpn-services/default/sessions/{payload["id"]}'
                        if self.sync_mode is True:
                            l3vpnresp = requests.patch(myURL,headers=myHeader,data=json_data)
                        else:
                            l3vpnresp = requests.put(myURL,headers=myHeader,data=json_data)
                        if l3vpnresp.status_code == 200:
                            print("L3VPN " + payload["id"] + " has been imported.")
                        else:
                            self.error_handling(l3vpnresp)
                    else:
                        print("TEST MODE - L3VPN " + l3vpn["id"] + " created by " + l3vpn["_create_user"] + " would have been imported.")

    def importVPNIKEProfiles(self):
        """Import all"""
        self.vmc_auth.check_access_token_expiration()
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
                        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
                        myURL = self.proxy_url + "/policy/api/v1/infra/ipsec-vpn-ike-profiles/" + ikep["id"]
                        if self.sync_mode is True:
                            createikepresp = requests.patch(myURL,headers=myHeader,data=json_data)
                        else:
                            createikepresp = requests.put(myURL,headers=myHeader,data=json_data)
                        if createikepresp.status_code == 200:
                            print("IKE Profile " + payload["display_name"] + " has been imported.")
                        else:
                            self.error_handling(createikepresp)
                    else:
                        print("TEST MODE - IKE Profile " + ikep["display_name"] + " created by " + ikep["_create_user"] + " would have been imported.")

    def importSDDCMGWRule(self):
        """Import all MGW Rules from a JSON file"""
        self.vmc_auth.check_access_token_expiration()
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
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
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
        self.vmc_auth.check_access_token_expiration()
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
                    myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token }
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
        self.vmc_auth.check_access_token_expiration()
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
        self.vmc_auth.check_access_token_expiration()
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
                    myHeader = {'csp-auth-token': self.vmc_auth.access_token}
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
                    myHeader = {'csp-auth-token': self.vmc_auth.access_token}
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
        self.vmc_auth.check_access_token_expiration()
        myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': self.vmc_auth.access_token}
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
                    myHeader = {'csp-auth-token': self.vmc_auth.access_token}
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

    def enable_sddc_ipv6(self):
        """Enable IPv6 on destination SDDC if enalbed on source SDDC"""
        self.vmc_auth.check_access_token_expiration()
        fname = self.import_path / self.sddc_info_filename
        with open(fname) as filehandle:
            source_sddc_info = json.load(filehandle)
        if self.import_mode == 'live':
            dest_sddc_json = self.loadSDDCData(self.dest_org_id, self.dest_sddc_id)
            if dest_sddc_json['resource_config']['ipv6_enabled'] is True:
                print(f"IPv6 already enabled on {self.dest_sddc_name}...skipping")
                return True
            else:
                if source_sddc_info['resource_config']['ipv6_enabled'] is True:
                    my_header = {"Content-Type": "application/json", "Accept": "application/json",
                                'csp-auth-token': self.vmc_auth.access_token}
                    my_url = f'{self.strProdURL}/api/network/{self.dest_org_id}/aws/operations'
                    json_body = {
                        "type": "ENABLE_IPV6",
                        "resource_type": "deployment",
                        "resource_id": self.dest_sddc_id,
                        "config": {
                            "type": "AwsEnableIpv6Config"
                        }
                    }
                    response = requests.post(my_url, json=json_body, headers=my_header)
                    if response.status_code == 201:
                        print(f"Enabling IPv6 on SDDC, please wait...")
                        time.sleep(180)
                        return True
                    else:
                        self.error_handling(response)
                        return False
                else:
                    print(f'IPv6 not enalbed on source SDDC and will not be enabled on destination SDDC')
                    return False
        else:
            print(f'IPv6 would have been enabled on the destination SDDC')
            return


    def importVPN(self):
        self.vmc_auth.check_access_token_expiration()
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

        retval = self.importVPNDPDProfiles()
        if retval is False:
            successval = False
            print('DPD Profile import failure: ', self.lastJSONResponse)
        else:
            print('DPD Profiles imported.')

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

    # def getAccessToken(self,myRefreshToken):
    #     """ Gets the Access Token using the Refresh Token """
    #     self.activeRefreshToken = myRefreshToken
    #     params = {'api_token': myRefreshToken}
    #     headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    #     response = requests.post(f'{self.strCSPProdURL}/csp/gateway/am/api/auth/api-tokens/authorize', params=params, headers=headers)
    #     jsonResponse = response.json()
    #     #print(jsonResponse)
    #     try:
    #         self.access_token = jsonResponse['access_token']
    #         expires_in = jsonResponse['expires_in']
    #         expirestime = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
    #         self.access_token_expiration = expirestime
    #         print(f'Token expires at {expirestime}')
    #     except:
    #         self.access_token = None
    #         self.access_token_expiration = None
    #     return self.access_token

    # def check_access_token_expiration(self) -> None:
    #     """Retrieve a new access token if it is near expiration"""
    #     time_to_expire = self.access_token_expiration - datetime.datetime.now()
    #     if time_to_expire.total_seconds() <= 100:
    #         print('Access token expired, attempting to refresh...')
    #         self.getAccessToken(self.activeRefreshToken)

    def getNSXTproxy(self, org_id, sddc_id):
        """ Gets the Reverse Proxy URL """
        self.vmc_auth.check_access_token_expiration()
        myHeader = {'csp-auth-token': self.vmc_auth.access_token}
        myURL = f'{self.strProdURL}/vmc/api/orgs/{org_id}/sddcs/{sddc_id}'
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
        self.vmc_auth.check_access_token_expiration()
        myHeader = {'csp-auth-token': self.vmc_auth.access_token}
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
            if jsonResponse['resource_config']['nsxt_addons']:
                if jsonResponse['resource_config']['nsxt_addons']['enable_nsx_advanced_addon']:
                    self.dest_sddc_enable_nsx_advanced_addon = jsonResponse['resource_config']['nsxt_addons']['enable_nsx_advanced_addon']
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
            if jsonResponse['resource_config']['nsxt_addons']:
                if jsonResponse['resource_config']['nsxt_addons']['enable_nsx_advanced_addon']:
                    self.source_sddc_enable_nsx_advanced_addon = jsonResponse['resource_config']['nsxt_addons']['enable_nsx_advanced_addon']
            self.source_sddc_info = jsonResponse
        else:
            return False

    def loadSourceSDDCNSXData(self):
        jsonResponse = self.loadSDDCNSX(self.source_org_id, self.source_sddc_id)
        if jsonResponse != "":
            for login_url in jsonResponse['login_urls']:
                #print(login_url)
                if login_url['access_type'] == 'PRIVATE' and login_url['auth_type'] == 'CSP':
                    self.source_sddc_nsx_csp_url = login_url['preferred_url']
                    break
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
        self.vmc_auth.check_access_token_expiration()
        myHeader = {'csp-auth-token': self.vmc_auth.access_token}
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

    def loadSDDCNSX(self, orgID, sddcID):
        """Loads SDDC URLs and credentials"""
        self.vmc_auth.check_access_token_expiration()
        myURL = self.strProdURL + f'/api/network/{orgID}/core/deployments/{sddcID}/nsx'
        response = self.invokeCSPGET(myURL)
        if response is None or response.status_code != 200:
            print(f'Error: {response.status_code}, {response.text}')
            return False
        return response.json()

    def searchOrgUser(self,orgid,userSearchTerm):
        self.vmc_auth.check_access_token_expiration()
        myURL = (self.strCSPProdURL + "/csp/gateway/am/api/orgs/" + orgid + "/users/search?userSearchTerm=" + userSearchTerm)
        response = self.invokeCSPGET(myURL)
        if response is None or response.status_code != 200:
            print(f'Error: {response.status_code}, {response.text}')
            return False

        self.user_search_results_json = response.json()
        return True