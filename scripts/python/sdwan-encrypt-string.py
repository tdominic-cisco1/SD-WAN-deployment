#!/usr/bin/python

## This script takes as input a clear text string and generates:
## - The SD-WAN Manager-encrypted string (specific to each SD-WAN Manager)
## - The SHA512 hash of the string
## - The Cisco Type 7 hash of the string
## - The Cisco Type 9 hash of the string

import os
import sys
import argparse
import logging
import http.client
import requests
from passlib.hash import sha512_crypt
from CiscoPWDhasher import type7, type9
requests.packages.urllib3.disable_warnings()

log = logging.getLogger("sdwan-encrypt")

def main(argv=None):
    try:
        url = os.environ['SDWAN_URL']
        sdwan_username = os.environ['SDWAN_USERNAME']
        sdwan_password = os.environ['SDWAN_PASSWORD']
    except:
        raise Exception("Missing environment variables with SDWAN credentials: SDWAN_URL, SDWAN_USERNAME, SDWAN_PASSWORD")

    parser = argparse.ArgumentParser()
    parser.add_argument("string", type=str, help='Clear text value to encrypt')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose HTTP debug logging')
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
        # Hook http.client into logging to capture raw HTTP traffic
        http.client.HTTPConnection.debuglevel = 1
        logging.getLogger("urllib3").setLevel(logging.DEBUG)
        logging.getLogger("requests").setLevel(logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    log.info("*** Connecting to the SD-WAN Manager API... ***")

    with requests.Session() as s:
        s.verify = False
        # Authenticate
        s.post(
            f"{url}/j_security_check",
            data={"j_username": sdwan_username, "j_password": sdwan_password},
        )
        # Fetch XSRF token
        token = s.get(f"{url}/dataservice/client/token").text
        s.headers.update({"X-XSRF-TOKEN": token})
        # Encrypt string
        cluster_enc = s.post(
            f"{url}/dataservice/template/security/encryptText/encrypt",
            json={"inputString": args.string},
        ).json()["encryptedText"]

    log.info("Input clear-text string: " + args.string)
    log.info("SD-WAN Manager-encrypted string: " + cluster_enc)
    log.info("SHA512 hash: " + sha512_crypt.hash(args.string, rounds=5000))
    log.info("Cisco Type 7 hash: " + type7(args.string).lower())
    log.info("Cisco Type 9 hash: " + type9(args.string))

if __name__ == "__main__":
   main(sys.argv[1:])
