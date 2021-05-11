# SDDC Import/Export for VMware Cloud on AWS


################################################################################
### Copyright 2020-2021 VMware, Inc.
### SPDX-License-Identifier: BSD-2-Clause
################################################################################

import json
import sddc_import_export

# export, import, or export-import
operation               = 'export'

# os or s3
export_type             = 's3'

# Usually the 'json' folder, but '/tmp' is the only writable folder in Lambda
export_folder           = '/tmp'

#Fill in the source org ID
source_org_id           = ''

#Fill in the source SDDC ID
source_sddc_id          = ''

#Fill in the dest org ID
dest_org_id             = ''

#Fill in the dest SDDC ID
dest_sddc_id            = ''

#Fill in the source SDDC refresh token
source_refresh_token    = ''

#Fill in the dest SDDC refresh token
dest_refresh_token      = ''

#Fill in the S3 bucket name
aws_s3_export_bucket    = ''


def lambda_handler(event, context):
    # TODO implement
    print(event)
    print(context)
    sddc_import_export.main(['-o',f'{operation}','-et',f'{export_type}','-ef',f'{export_folder}','-so',f'{source_org_id}','-ss',f'{source_sddc_id}','-do',f'{dest_org_id}','-ds',f'{dest_sddc_id}','-st',f'{source_refresh_token}','-dt',f'{dest_refresh_token}','-s3b',f'{aws_s3_export_bucket}'])
    return {
        'statusCode': 200,
        'body': json.dumps('Execution complete.')
    }

#lambda_handler("x","y")
