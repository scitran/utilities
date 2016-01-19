"""
to run it:
sudo pip install oauth2client
python oauth2cli.py --auth_host_port 9000 --client-secret <client-secret> --client-id <client-id>

it creates a json file called "credentials_sdm"
the access_token in the credentials is also printed to stdout
"""

from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
import argparse
from oauth2client import tools
import contextlib
import sys
import cStringIO

parser = argparse.ArgumentParser(parents=[tools.argparser])
parser.add_argument('--client-id', type=str, required=True)
parser.add_argument('--client-secret', type=str, required=True)
flags = parser.parse_args()

@contextlib.contextmanager
def nostdout():
    save_stdout = sys.stdout
    sys.stdout = cStringIO.StringIO()
    yield
    sys.stdout = save_stdout

def main(flags):
    flow = OAuth2WebServerFlow(client_id=flags.client_id,
                           client_secret=flags.client_secret,
                           scope='https://www.googleapis.com/auth/userinfo.email')


    storage = Storage('credentials_sdm')

    credentials = tools.run_flow(flow, storage, flags)
    return credentials

if __name__ == '__main__':
    with nostdout():
        c = main(flags)
    print c.get_access_token().access_token
