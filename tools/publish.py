"""Publication only inside manually dispatched, reviewer-protected GitHub job."""
import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path

REPO='pixii69-ui/ads-pro-updates'


def plan(folder,commit,version,confirmation,current):
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('Full source commit required')
    if confirmation!='PUBLIKUJ '+version:raise ValueError('Explicit publication phrase required')
    data=json.loads((folder/'candidate.json').read_text())
    if data['source_commit']!=commit or data['version']!=version:raise ValueError('Candidate differs from approval')
    if not re.fullmatch(r'[1-9][0-9]*\.0\.0',version) or type(data['version_code']) is not int or data['version_code']!=int(version.split('.')[0]):raise ValueError('Version/code mismatch')
    if type(current['version_code']) is not int or data['version_code']<=current['version_code']:raise ValueError('No downgrade/republication')
    files=list(folder.glob('*.zip'))
    if len(files)!=1:raise ValueError('Exactly one ZIP required')
    package=files[0]
    digest=hashlib.sha256(package.read_bytes()).hexdigest()
    if digest!=data['sha256']:raise ValueError('Candidate SHA-256 differs')
    url=f'https://github.com/{REPO}/releases/download/v{version}/{package.name}'
    if data['download_url']!=url:raise ValueError('Candidate URL differs from V9 contract')
    manifest={key:data[key] for key in ('version','version_code','download_url','sha256','release_notes')}
    return package,manifest


def gh(*args,input=None):
    return subprocess.run(['gh',*args],input=input,text=True,capture_output=True,check=True).stdout


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);parser.add_argument('--commit',required=True);parser.add_argument('--version',required=True);parser.add_argument('--confirmation',required=True);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if not args.execute:raise SystemExit('No publication: --execute must be used by approved Actions job')
    if os.environ.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_ACTOR')!='pixii69-ui' or os.environ.get('GITHUB_REF')!='refs/heads/main':
        raise SystemExit('Publication outside approved manual owner workflow is blocked')
    contents=json.loads(gh('api',f'repos/{REPO}/contents/version.json'))
    current=json.loads(base64.b64decode(contents['content']))
    package,manifest=plan(args.folder,args.commit,args.version,args.confirmation,current)
    tag='v'+args.version
    # Never overwrite a tag, release, ZIP or manifest of an existing version.
    existing=subprocess.run(['gh','api',f'repos/{REPO}/releases/tags/{tag}'],capture_output=True,text=True)
    if existing.returncode==0:raise SystemExit('Existing release retained; choose a new version')
    if '404' not in existing.stderr:raise RuntimeError('Cannot verify release absence')
    gh('release','create',tag,str(package),str(args.folder/'SHA256SUMS.txt'),'--repo',REPO,'--draft','--target','main','--title','ADS PRO '+args.version,'--notes','Approved source commit: '+args.commit)
    gh('release','edit',tag,'--repo',REPO,'--draft=false')
    # Manifest is updated last, only after public asset bytes are verified.
    digest=hashlib.sha256()
    with urllib.request.urlopen(manifest['download_url'],timeout=60) as response:
        for block in iter(lambda:response.read(65536),b''):digest.update(block)
    if digest.hexdigest()!=manifest['sha256']:raise RuntimeError('Public asset mismatch; old manifest retained')
    payload={'message':'Publish approved ADS PRO '+args.version,'sha':contents['sha'],'content':base64.b64encode((json.dumps(manifest,indent=2)+'\n').encode()).decode(),'branch':'main'}
    gh('api',f'repos/{REPO}/contents/version.json','--method','PUT','--input','-',input=json.dumps(payload))
    print('Published approved release; manifest updated last:',args.version,args.commit)


if __name__=='__main__':main()
