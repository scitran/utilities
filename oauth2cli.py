"""
to run it:
sudo pip install oauth2client
python oauth2cli.py --auth_host_port 9000 --client-secret <client-secret> --client-id <client-id>

it creates a json file called "credentials_sdm"
the access_token in the credentials is also printed to stdout
"""

from oauth2client.client import OAuth2WebServerFlow, OAuth2Credentials
from oauth2client.file import Storage
import argparse
from oauth2client import tools
import contextlib
import sys
import cStringIO
import httplib2

FILE_NAME = 'credentials_sdm'

@contextlib.contextmanager
def nostdout():
    save_stdout = sys.stdout
    sys.stdout = cStringIO.StringIO()
    yield
    sys.stdout = save_stdout

def main(args):
    flow = OAuth2WebServerFlow(client_id=args.client_id,
                           client_secret=args.client_secret,
                           scope='https://www.googleapis.com/auth/userinfo.email')
    storage = Storage(FILE_NAME)
    credentials = tools.run_flow(flow, storage, args)
    return credentials

def refresh(args):
    with open(FILE_NAME, 'rU') as f:
        credentials = OAuth2Credentials.from_json(f.read())
    credentials.refresh(httplib2.Http())
    storage = Storage(FILE_NAME)
    storage.put(credentials)
    credentials.set_store(storage)
    return credentials

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='sub-command help')
    subparser_create = subparsers.add_parser('create', help='create help', parents=[tools.argparser])
    subparser_create.add_argument('--client-id', type=str, required=True)
    subparser_create.add_argument('--client-secret', type=str, required=True)
    subparser_create.set_defaults(func=main)
    subparser_refresh = subparsers.add_parser('refresh', help='refresh help')
    subparser_refresh.set_defaults(func=refresh)
    args = parser.parse_args()
    with nostdout():
        c = args.func(args)
    print c.access_token
