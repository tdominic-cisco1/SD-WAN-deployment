#!/usr/bin/python

## This script retrieves third-party CA certificates from vManage and displays:
## - Certificate Name
## - UUID
## - Subject Common Name

import os
import logging
import argparse
from catalystwan.session import create_manager_session
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger("sdwan-get-ca-certs")

def main():
    parser = argparse.ArgumentParser(description='Retrieve third-party CA certificates from SD-WAN Manager')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    # Basic configuration for logging
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)

    try:
        url = os.environ['SDWAN_URL']
        sdwan_username = os.environ['SDWAN_USERNAME']
        sdwan_password = os.environ['SDWAN_PASSWORD']
    except:
        raise Exception("Missing environment variables with SDWAN credentials: SDWAN_URL, SDWAN_USERNAME, SDWAN_PASSWORD")

    print("*** Connecting to the SD-WAN Manager API... ***")

    with create_manager_session(url=url, username=sdwan_username, password=sdwan_password) as session:
        response = session.get("/dataservice/v1/certificate/third-party-ca").json()

        if 'data' not in response or len(response['data']) == 0:
            print("No CA certificates found.")
            return

        print("*** Third-Party CA Certificates ***")

        for cert in response['data']:
            cert_name = cert.get('certificateName', 'N/A')
            cert_uuid = cert.get('uuid', 'N/A')
            subject_cn = cert.get('subjectCommonName', 'N/A')

            print(f"Certificate Name: {cert_name}")
            print(f"UUID: {cert_uuid}")
            print(f"Subject Common Name: {subject_cn}")
            print("-" * 50)

if __name__ == "__main__":
   main()
