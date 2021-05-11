#!/usr/bin/env python3
# The shebang above is to tell the shell which interpreter to use. This make the file executable without "python3" in front of it (otherwise I had to use python3 pyvmc.py)
# I also had to change the permissions of the file to make it run. "chmod +x pyVMC.py" did the trick.
# I also added "export PATH="MY/PYVMC/DIRECTORY":$PATH" (otherwise I had to use ./pyvmc.y)

# SDDC Import/Export for VMware Cloud on AWS


################################################################################
### Copyright 2020-2021 VMware, Inc.
### SPDX-License-Identifier: BSD-2-Clause
################################################################################

# For git BASH on Windows, you can use something like this 
# #!/C/Users/usr1/AppData/Local/Programs/Python/Python38/python.exe

"""

Welcome to SDDC Import/Export ! 

VMware Cloud on AWS API Documentation is available at: https://code.vmware.com/apis/920/vmware-cloud-on-aws
CSP API documentation is available at https://console.cloud.vmware.com/csp/gateway/api-docs
vCenter API documentation is available at https://code.vmware.com/apis/366/vsphere-automation


You can install python 3.8 from https://www.python.org/downloads/windows/ (Windows) or https://www.python.org/downloads/mac-osx/ (MacOs).

You can install the dependent python packages locally with:
pip3 install requests or pip3 install requests -t . --upgrade
pip3 install configparser or pip3 install configparser -t . --upgrade
pip3 install PTable or pip3 install PTable -t . --upgrade
pip3 install boto3

Or you can install all the requirement above with:
pip3 install -r requirements.txt

With git BASH on Windows, you might need to use 'python -m pip install' instead of pip3 install

"""
import boto3
import sys
MIN_PYTHON = (3,6)
assert sys.version_info >= MIN_PYTHON, f"Python {'.'.join([str(n) for n in MIN_PYTHON])} or newer is required."

import argparse
import requests                          # need this for Get/Post/Delete
import configparser                     # parsing config file
import time
import glob
from pathlib import Path
from prettytable import PrettyTable
import json
import os
import vcenter
from VMCImportExport import VMCImportExport
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def yes_or_no(question):
    """ Forces user to respond, 'y' or 'n', returns True or False """
    while "the answer is invalid":
        reply = str(input(question+' (y/n): ')).lower().strip()
        if reply[0] == 'y':
            return True
        if reply[0] == 'n':
            return False

# --------------------------------------------
# ---------------- Main ----------------------
# --------------------------------------------
def main(args):
    CONFIG_FILE_PATH="./config_ini/config.ini"
    VMC_CONFIG_FILE_PATH="./config_ini/vmc.ini"
    AWS_CONFIG_FILE_PATH="./config_ini/aws.ini"

    ap = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                    epilog="Welcome to sddc_import_export!\n"
                                    "Examples:\n\n"
                                    "Export an SDDC:\n"
                                    "python sddc_import_export.py -o export\n\n"
                                    "Import an SDDC:\n"
                                    "python sddc_import_export.py -o import\n\n"
                                    "Import an SDDC from a zipfile:\n"
                                    "python sddc_import_export.py -o import -i json/2020-12-15_10-33-43_json-export.zip\n\n")                                
    ap.add_argument("-o","--operation", required=True, choices=['import-nsx','export-nsx','import','export','export-import','check-vmc-ini','export-vcenter','import-vcenter'], help="SDDC-to-SDDC operations: import, export, or export and then immediately import. check-vmc-ini displays the currently configured Org and SDDC for import and export operations. export-nsx to export an on-prem NSX config, then import-nsx to import it to VMC. export-vcenter and import-vcenter to export and import vCenter configs.")
    ap.add_argument("-et","--export-type", required=False, choices=['os','s3'],help="os for a regular export, s3 for export to S3 bucket")
    ap.add_argument("-ef","--export-folder",required=False,help="Export folder location")
    import_group = ap.add_mutually_exclusive_group()
    import_group.add_argument("-i","--import-file-path", required=False,help="A full path to a previously exported zip")
    import_group.add_argument("-iff","--import-first-file", required=False,help="Imports the first zipfile found in the specified path")
    ap.add_argument("-st", "--source-refresh-token", required=False, help="An API refresh token for the source SDDC")
    ap.add_argument("-dt", "--dest-refresh-token", required=False, help="An API refresh token for the destination SDDC")
    ap.add_argument("-so","--source-org-id", required=False,help="The source organization ID")
    ap.add_argument("-do","--dest-org-id", required=False,help="The destination organization ID")
    ap.add_argument("-ss","--source-sddc-id", required=False,help="The source SDDC ID")
    ap.add_argument("-ds","--dest-sddc-id", required=False,help="The destination SDDC ID")
    ap.add_argument("-s3aid","--aws-s3-export-access-id", required=False,help="AWS Access ID for export to S3")
    ap.add_argument("-s3ase","--aws-s3-export-access-secret", required=False,help="AWS Secret for export to S3")
    ap.add_argument("-s3b","--aws-s3-export-bucket", required=False,help="AWS bucket name for export to S3")

    args = ap.parse_args(args)

    if args.operation:
        intent_name = args.operation
    else:
        intent_name = ""

    if args.import_file_path:
        import_file_path = args.import_file_path
    else:
        import_file_path = ""

    if args.import_first_file:
        import_first_file = args.import_first_file
    else:
        import_first_file = ""

    ioObj = VMCImportExport(CONFIG_FILE_PATH,VMC_CONFIG_FILE_PATH, AWS_CONFIG_FILE_PATH)

    # Check the optional command-line arguments to override the values in vmc.ini
    if args.source_refresh_token:
        ioObj.source_refresh_token = args.source_refresh_token
        print('Loaded source refresh token from command line')

    if args.export_type:
        ioObj.export_type = args.export_type
        print('Loaded export mode from command line')

    if args.export_folder:
        ioObj.export_folder = args.export_folder
        ioObj.export_path = Path(ioObj.export_folder)
        print('Loaded export folder from command line')

    if args.dest_refresh_token:
        ioObj.dest_refresh_token = args.dest_refresh_token
        print('Loaded dest refresh token from command line')

    if args.source_org_id:
        ioObj.source_org_id = args.source_org_id
        print('Loaded source org ID from command line')

    if args.dest_org_id:
        ioObj.dest_org_id = args.dest_org_id
        print('Loaded dest org ID from command line')

    if args.source_sddc_id:
        ioObj.source_sddc_id = args.source_sddc_id
        print('Loaded source SDDC ID from command line')

    if args.dest_sddc_id:
        ioObj.dest_sddc_id = args.dest_sddc_id
        print('Loaded dest SDDC ID from command line')

    if args.aws_s3_export_access_id:
        ioObj.aws_s3_export_access_id = args.aws_s3_export_access_id
        print('Loaded AWS S3 export Access ID from command line')

    if args.aws_s3_export_access_secret:
        ioObj.aws_s3_export_access_secret = args.aws_s3_export_access_secret
        print('Loaded AWS S3 export Secret from command line')

    if args.aws_s3_export_bucket:
        ioObj.aws_s3_export_bucket = args.aws_s3_export_bucket
        print('Loaded AWS S3 export bucket from command line')

    # Variable added so we can have an intent run multiple operations
    no_intent_found = True


        

    ################################ Warning ######################################
    ## Changing the order of ifchecks on intent name can have unexpected          #
    ## side effects. If you want to do both an export and import in a single      #
    ## run of the script, it only makes sense to run the export first.            #
    ## Moving the import section above the export section would break this intent #
    ###############################################################################

    if intent_name == "export-vcenter":
        no_intent_found = False
        if ioObj.export_vcenter_folders:
            srcvc = vcenter.vCenter(ioObj.srcvCenterURL,ioObj.srcvCenterUsername,ioObj.srcvCenterPassword,ioObj.srcvCenterSSLVerify)
            srcdc = srcvc.get_datacenter(ioObj.srcvCenterDatacenter)
            print('Exporting folder paths from source vCenter...')
            srcdc.export_folder_paths(ioObj.export_path / ioObj.vcenter_folders_filename)
            print('Export complete.')
    

    if intent_name == "import-vcenter":
        no_intent_found = False
        if ioObj.import_vcenter_folders:
            destvc = vcenter.vCenter(ioObj.destvCenterURL,ioObj.destvCenterUsername,ioObj.destvCenterPassword,ioObj.destvCenterSSLVerify)
            destdc = destvc.get_datacenter(ioObj.destvCenterDatacenter)
            print('Importing folder paths into destination vCenter...')
            if ioObj.import_mode == 'live':
                test_mode = False
            else:
                test_mode = True
            destdc.import_folder_paths(ioObj.import_path / ioObj.vcenter_folders_filename,test_mode=test_mode)
            print('Import complete.')

    if intent_name == "export-nsx":
        no_intent_found = False
        print("Beginning on-prem export...")

        print("Beginning Services export...")
        retval = ioObj.exportOnPremServices()
        if retval is True:
            print("Services exported.")
        else:
            print("Services export error: {}".format(ioObj.lastJSONResponse))

        retval = ioObj.exportOnPremGroups()
        if retval is True:
                print("Groups exported.")
        else:
                print("Groups export error: {}".format(ioObj.lastJSONResponse))
        
        retval = ioObj.exportOnPremDFWRule()
        if retval is True:
                print("DFW rules exported.")
        else:
                print("DFW rules error: {}".format(ioObj.lastJSONResponse))
       
        print("Thanks for using the export function")
    
    if intent_name == "import-nsx":
        no_intent_found = False
        print('Import mode:',ioObj.import_mode)

        ioObj.getAccessToken(ioObj.dest_refresh_token)
        if (ioObj.access_token == ""):
            print("Unable to retrieve access token. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()

        ioObj.getNSXTproxy(ioObj.dest_org_id,ioObj.dest_sddc_id)
        if (ioObj.proxy_url == ""):
            print("Unable to retrieve proxy. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()

        retval = ioObj.loadDestOrgData()
        if retval == False:
            print("Unable to load Dest Org Data. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit() 

        retval = ioObj.loadDestSDDCData()
        if retval == False:
            print("Unable to load Dest SDDC Data. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()
        
        if ioObj.dest_sddc_state != 'READY':
            print("Unable to import, expected SDDC",ioObj.dest_sddc_name,"state READY, found state", ioObj.dest_sddc_state)
            sys.exit()
        
        print(f'Importing data into org {ioObj.dest_org_display_name} ({ioObj.dest_org_id}), SDDC {ioObj.dest_sddc_name} ({ioObj.dest_sddc_id}), SDDC version {ioObj.dest_sddc_version}')
        #print(getSDDCS(ioObj.strProdURL,ioObj.dest_org_id, ioObj.access_token))

        if ioObj.import_mode == "live":
            if ioObj.import_mode_live_warning is True:
                continue_live = yes_or_no("Script is running in live mode - changes will be made to your destination SDDC. Continue in live mode?")
                if continue_live is False:
                    ioObj.import_mode = "test"
                    print("Import mode set to test")
                else:
                    print("Live import will proceed")

        print("Beginning Services import...")
        ioObj.importOnPremServices()


        print("Beginning Group import...")
        retval = ioObj.importOnPremGroup()

        if ioObj.dfw_import is True:
            print("Beginning DFW import...")
            ioObj.importOnPremDFWRule()
            
        print("Import has been concluded. Thank you for using SDDC Import/Export for VMware Cloud on AWS.")
            

    if intent_name == "check-vmc-ini":
        no_intent_found = False

        ioObj.getAccessToken(ioObj.source_refresh_token)
        if (ioObj.access_token == ""):
            print("Unable to retrieve access token. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()

        ioObj.getNSXTproxy(ioObj.source_org_id,ioObj.source_sddc_id)
        if (ioObj.proxy_url == ""):
            print("Unable to retrieve proxy. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()

        retval = ioObj.loadSourceOrgData()
        if retval == False:
            print("Unable to load Source Org Data. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()    

        retval = ioObj.loadSourceSDDCData()
        if retval == False:
            print("Unable to load Source SDDC Data. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()

        print(f'Export configuration: Org {ioObj.source_org_display_name} ({ioObj.source_org_id}), SDDC {ioObj.source_sddc_name} ({ioObj.source_sddc_id}), SDDC version {ioObj.source_sddc_version}')

        ioObj.getAccessToken(ioObj.dest_refresh_token)
        if (ioObj.access_token == ""):
            print("Unable to retrieve access token. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()

        ioObj.getNSXTproxy(ioObj.dest_org_id,ioObj.dest_sddc_id)
        if (ioObj.proxy_url == ""):
            print("Unable to retrieve proxy. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()

        retval = ioObj.loadDestOrgData()
        if retval == False:
            print("Unable to load Dest Org Data. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit() 

        retval = ioObj.loadDestSDDCData()
        if retval == False:
            print("Unable to load Dest SDDC Data. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()

        print(f'Import configuration: Org {ioObj.dest_org_display_name} ({ioObj.dest_org_id}), SDDC {ioObj.dest_sddc_name} ({ioObj.dest_sddc_id}), SDDC version {ioObj.dest_sddc_version}')

    if intent_name == "export" or intent_name == "export-import":
        no_intent_found = False

        ioObj.getAccessToken(ioObj.source_refresh_token)
        if (ioObj.access_token == ""):
            print("Unable to retrieve access token. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()

        ioObj.getNSXTproxy(ioObj.source_org_id,ioObj.source_sddc_id)
        if (ioObj.proxy_url == ""):
            print("Unable to retrieve proxy. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()

        retval = ioObj.loadSourceOrgData()
        if retval == False:
            print("Unable to load Source Org Data. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()    

        retval = ioObj.loadSourceSDDCData()
        if retval == False:
            print("Unable to load Source SDDC Data. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()

        print(f'Exporting data from org {ioObj.source_org_display_name} ({ioObj.source_org_id}), SDDC {ioObj.source_sddc_name} ({ioObj.source_sddc_id}), SDDC version {ioObj.source_sddc_version}')
        #print(getSDDCS(ioObj.strProdURL,ioObj.source_org_id, ioObj.access_token))

        # Delete old JSON files
        if ioObj.export_type == 'os' and ioObj.export_purge_before_run is True:
            print('Deleting old JSON export files...')
            retval = ioObj.purgeJSONfiles()
            if retval is False:
                stop_script = yes_or_no("Errors purging old files. Continue running script?")
                if stop_script is True:
                    sys.exit()
        
        # Run all selected export functions

        retval = ioObj.exportSourceSDDCData()
        if retval is True:
            print("Source SDDC Info exported.")
        else:
            print("Could not export Source SDDC Info")

        if (ioObj.cgw_export is True) or (ioObj.mgw_export is True):
            print("Beginning Services export...")
            retval = ioObj.exportSDDCServices()
            if retval is True:
                print("SDDC services exported.")
            else:
                print("SDDC services export error: {}".format(ioObj.lastJSONResponse))

        if ioObj.mgw_export is True:
            print("Beginning MGW export...")
            retval = ioObj.exportSDDCMGWGroups()
            if retval is True:
                print("MGW groups exported.")
            else:
                print("MGW groups export error: {}".format(ioObj.lastJSONResponse))

            retval = ioObj.exportSDDCMGWRule()
            if retval is True:
                print("MGW rules exported.")
            else:
                print("MGW export error: {}".format(ioObj.lastJSONResponse))
        else:
            print("MGW export skipped.")

        if ioObj.cgw_export is True:
            print("Beginning CGW export...")
            retval = ioObj.exportSDDCCGWGroups()
            if retval is True:
                print("CGW groups exported.")
            else:
                print("CGW groups export error: {}".format(ioObj.lastJSONResponse))

            retval = ioObj.exportSDDCCGWRule()
            if retval is True:
                print("CGW rules exported.")
            else:
                print("CGW export error: {}".format(ioObj.lastJSONResponse))
        else:
            print("CGW export skipped.")

        if ioObj.network_export is True:
            print("Beginning network segments export...")
            retval = ioObj.exportSDDCCGWnetworks()
            if retval is True:
                print("CGW networks exported.")
            else:
                print("CGW export error: {}".format(ioObj.lastJSONResponse))
        else:
            print("CGW network segment export skipped.")

        if ioObj.dfw_export is True:
            print("Beginning DFW export...")
            retval = ioObj.exportSDDCDFWRule()
            if retval is True:
                print("DFW rules exported.")
            else:
                print("DFW rules error: {}".format(ioObj.lastJSONResponse))
        else:
            print("DFW rules export skipped.")

        if ioObj.public_export is True:
            print("Beginning Public IP export...")
            retval = ioObj.exportSDDCListPublicIP()
            if retval is True:
                print("Public IP exported.")
            else:
                print("Public IP export error: {}".format(ioObj.lastJSONResponse))
        else:
            print("Public IP export skipped.")

        if ioObj.nat_export is True:
            print("Beginning NAT export...")
            retval = ioObj.exportSDDCNat()
            if retval is True:
                print("NAT rules exported.")
            else:
                print("NAT rules export error: {}".format(ioObj.lastJSONResponse))
        else:
            print("NAT rules export skipped.")

        if ioObj.service_access_export is True:
            print("Beginning Service Access export...")
            retval = ioObj.exportServiceAccess()
            if retval is True:
                print("Service access exported.")
            else:
                print("Service access export error: {}.".format(ioObj.lastJSONResponse))
        else:
            print("Service access export skipped.")
            
        if ioObj.vpn_export is True:
            print("Beginning VPN export...")
            retval = ioObj.exportVPN()
            if retval is True:
                print("VPN exported.")
            else:
                print("VPN export error.")
        else:
            print("VPN export skipped.")

        if ioObj.export_history is True:
            retval = ioObj.zipJSONfiles()
            if retval is False:
                print('JSON files were not successfully zipped.')
            else:
                print('JSON files successfully zipped into', ioObj.export_zip_name)
                if ioObj.export_type == 's3':
                    print('Uploading to s3 bucket',ioObj.aws_s3_export_bucket)
                    if len(ioObj.aws_s3_export_access_id) == 0:
                        #Blank access ID - running in Lambda mode, do not pass the key and secret, the Lambda role will grant access to the bucket
                        s3 = boto3.client('s3')
                    else:
                        s3 = boto3.client('s3',aws_access_key_id=ioObj.aws_s3_export_access_id,aws_secret_access_key=ioObj.aws_s3_export_access_secret)
                    try:
                        fname = ioObj.export_folder + '/' + ioObj.export_zip_name
                        with open(fname, "rb") as f:
                            response = s3.upload_fileobj(f,ioObj.aws_s3_export_bucket,ioObj.export_zip_name)
                        print('S3 upload successful')
                    except Exception as e:
                        print('Failed to upload file.')
                        print(e)
                
                if ioObj.export_purge_after_zip == True:
                    print('export_purge_after_zip flag is true, deleting JSON files')
                    retval = ioObj.purgeJSONfiles()
                    if retval is False:
                        print('Unable to purge JSON files.')
            
            retval = ioObj.purgeJSONzipfiles()
            if retval is True:
                print('Zipfile maintenance completed with no errors.')

        print("Export has been concluded. Thank you for using SDDC Import/Export for VMware Cloud on AWS.")

    if intent_name == "import" or intent_name == "export-import":
        no_intent_found = False

        # User passed a folder name to use as the import source
        # Find the first zipfile in the folder and save it to import_file_path
        # This will make the program run just as if the calling function had passed in a full zipfile
        # path via import_file_path

        if ioObj.sync_mode is True:
            if ioObj.public_import is True or ioObj.nat_import is True:
                print("When sync mode is enabled, public IP import and NAT import should be disabled. Syncing public IPs and NAT configuration is not currently supported. If you are importing into an empty SDDC, it is safe to continue. If your destination SDDC has existing public IPs and NATs, you should cancel the import.")
                stop_script = yes_or_no("Do you want to cancel the import?")
                if stop_script is True:
                    print("You can disable public IP and NAT imports for this single run of the import process. You will still need to change config.ini for any future imports.")
                    stop_script = yes_or_no("Do you want to disable public IP and NAT imports? Answering yes will disable those features and continue with the import. Answering no will stop the script.")
                    if stop_script is True:
                        print("Disabling public IP and NAT imports...")
                        ioObj.public_import = False
                        ioObj.nat_import = False
                    else:
                        sys.exit()

        if import_first_file != "":
            files = glob.glob(import_first_file + '/*.zip')
            if len(files) > 0:
                import_file_path = files[0]
                print('Found',import_file_path,'in folder.')
            else:
                print('Found no zipfiles in',import_first_file)

        # User passed a zipfile path to use as the import source
        if import_file_path != "":
            ioObj.import_folder = os.path.dirname(import_file_path)
            ioObj.import_path = Path(ioObj.import_folder)
            ioObj.export_folder = os.path.dirname(import_file_path) 
            ioObj.export_path = Path(ioObj.export_folder)
            retval = ioObj.purgeJSONfiles()
            if retval is False:
                stop_script = yes_or_no("Errors purging old files. Stop running script?")
                if stop_script is True:
                    sys.exit()
            retval = ioObj.unzipJSONfiles(import_file_path)
            if retval is False:
                stop_script = yes_or_no("Could not unzip archive. Stop running script?")
                if stop_script is True:
                    sys.exit()
            else:
                print('Extracted JSON from zip archive',import_file_path,"- continuing with import.")
                print('Loaded import and export folder from command line:', ioObj.import_path )
        
        print('Import mode:',ioObj.import_mode)

        ioObj.getAccessToken(ioObj.dest_refresh_token)
        if (ioObj.access_token == ""):
            print("Unable to retrieve access token. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()

        ioObj.getNSXTproxy(ioObj.dest_org_id,ioObj.dest_sddc_id)
        if (ioObj.proxy_url == ""):
            print("Unable to retrieve proxy. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()

        retval = ioObj.loadDestOrgData()
        if retval == False:
            print("Unable to load Dest Org Data. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit() 

        retval = ioObj.loadDestSDDCData()
        if retval == False:
            print("Unable to load Dest SDDC Data. Server response:{}".format(ioObj.lastJSONResponse))
            sys.exit()
        
        if ioObj.dest_sddc_state != 'READY':
            print("Unable to import, expected SDDC",ioObj.dest_sddc_name,"state READY, found state", ioObj.dest_sddc_state)
            sys.exit()
        
        print(f'Importing data into org {ioObj.dest_org_display_name} ({ioObj.dest_org_id}), SDDC {ioObj.dest_sddc_name} ({ioObj.dest_sddc_id}), SDDC version {ioObj.dest_sddc_version}')
        #print(getSDDCS(ioObj.strProdURL,ioObj.dest_org_id, ioObj.access_token))

        if ioObj.import_mode == "live":
            if ioObj.import_mode_live_warning is True:
                continue_live = yes_or_no("Script is running in live mode - changes will be made to your destination SDDC. Continue in live mode?")
                if continue_live is False:
                    ioObj.import_mode = "test"
                    print("Import mode set to test")
                else:
                    print("Live import will proceed")

        if ioObj.network_import is True:
            print("Beginning CGW network import...")        
            import_table = ioObj.importCGWNetworks()
            print('Import results:\n')
            print(import_table)

        if (ioObj.cgw_import is True) or (ioObj.mgw_import is True):
            print("Beginning Services import...")
            ioObj.importSDDCServices()

        if ioObj.cgw_import is True:
            print("Beginning CGW import...")
            retval = ioObj.importSDDCCGWGroup()
            if retval is True:
                ioObj.importSDDCCGWRule()
            else:
                print('Could not import CGW groups, will not attempt CGW firewall rules import.')

        if ioObj.mgw_import is True:
            print("Beginning MGW import...")
            retval = ioObj.importSDDCMGWGroup()
            if retval is True:
                ioObj.importSDDCMGWRule()
            else:
                print('Coud not import MGW groups, will not attempt MGW firewall rules import.')

        if ioObj.dfw_import is True:
            print("Beginning DFW import...")
            ioObj.importSDDCDFWRule()
            
        if ioObj.public_import is True:
            print("Beginning Public IP import...")
            ioObj.importSDDCPublicIPs()

        if ioObj.nat_import is True:
            print("Beginning NAT import...")
            ioObj.importSDDCNats()

        if ioObj.service_access_import is True:
            print("Beginning Service Access import...")
            ioObj.importServiceAccess()

        if ioObj.vpn_import is True:
            print("Beginning VPN import...")
            ioObj.importVPN()

        print("Import has been concluded. Thank you for using SDDC Import/Export for VMware Cloud on AWS.")
            
    if no_intent_found == True:
        print("\nWelcome to sddc_import_export!")
        print("\nHere are the currently supported commands: ")
        print("\nTo export your source SDDC to JSON")
        print("export")
        print("\nTo import your source SDDC from JSON into your destination SDDC")
        print("import")
        print("\nTo first export your source SDDC to JSON, then import into your destination SDDC")
        print("export-import")
        print("\nTo import a saved zip archive into your destination SDDC")
        print("import json/filename_json-export.zip")

if __name__ == '__main__':
    main(sys.argv[1:])
