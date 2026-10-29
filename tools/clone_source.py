"""Read one approved private commit using a repository-scoped read-only deploy key."""
import argparse
import json
import os
import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('commit');args=parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}',args.commit):raise ValueError('Full commit SHA required')
    key=os.environ.pop('ADS_PRO_SOURCE_DEPLOY_KEY')
    with tempfile.TemporaryDirectory(prefix='ads-source-key-') as tmp:
        folder=Path(tmp);private=folder/'key';private.write_text(key+'\n');private.chmod(0o600)
        with urllib.request.urlopen('https://api.github.com/meta',timeout=20) as response:meta=json.load(response)
        hosts=folder/'known_hosts';hosts.write_text(''.join('github.com '+item+'\n' for item in meta['ssh_keys']))
        env=dict(os.environ,GIT_SSH_COMMAND=f'ssh -i {private} -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile={hosts}')
        destination=Path('source');destination.mkdir()
        for command in (['git','init'],['git','remote','add','origin','git@github.com:pixii69-ui/ads-pro-source.git'],['git','fetch','--depth=1','origin',args.commit],['git','checkout','--detach','FETCH_HEAD']):
            subprocess.run(command,cwd=destination,env=env,check=True,capture_output=True)
        actual=subprocess.run(['git','rev-parse','HEAD'],cwd=destination,capture_output=True,text=True,check=True).stdout.strip()
        assert actual==args.commit
    print('Checked out approved source commit:',actual)


if __name__=='__main__':main()
