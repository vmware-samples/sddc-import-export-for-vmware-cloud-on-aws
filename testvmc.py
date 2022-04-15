from vmc import VMCSDDC
import json, sys

refresh_token = ''
oauth_id = ''
oauth_secret = ''
org_id = ''
sddc_id = ''

vmcsddc = VMCSDDC(org_id,sddc_id,refresh_token=refresh_token)
#vmcsddc = VMCSDDC(org_id,sddc_id, oauth_id=oauth_id, oauth_secret=oauth_secret)
vmcsddc.debug_mode = True
success = vmcsddc.load_interface_counters()
if success:
    for x in vmcsddc.edge_interface_stats:
        print (f'Interface: {x}, timestamp={vmcsddc.edge_interface_stats[x].last_update_timestamp} ')
        print(f'\trx_total_bytes={vmcsddc.edge_interface_stats[x].rx_total_bytes}')
        print(f'\trx_total_packets={vmcsddc.edge_interface_stats[x].rx_total_packets}')
        print(f'\trx_dropped_packets={vmcsddc.edge_interface_stats[x].rx_dropped_packets}')
        print(f'\ttx_total_bytes={vmcsddc.edge_interface_stats[x].tx_total_bytes}')
        print(f'\ttx_total_packets={vmcsddc.edge_interface_stats[x].tx_total_packets}')
        print(f'\ttx_dropped_packets={vmcsddc.edge_interface_stats[x].tx_dropped_packets}')
else:
    print("Could not load counters.")
