"""Sign release metadata only with the key pinned in the exact candidate ZIP."""
import base64
import hashlib
import json
import zipfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def canonical(data):
    return json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def sign_program_manifest(package,manifest,secret):
    if not secret:raise ValueError('Publisher signing key is not configured')
    private=Ed25519PrivateKey.from_private_bytes(base64.b64decode(secret,validate=True))
    public=private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    encoded=base64.b64encode(public).decode('ascii')
    with zipfile.ZipFile(package) as archive:
        pinned=json.loads(archive.read('ads_update/trusted_keys.json'))
    matches=[key_id for key_id,value in pinned.items() if value==encoded]
    if len(matches)!=1:raise ValueError('Signing key must match exactly one key pinned in candidate')
    if 'signature' in manifest:raise ValueError('Refusing to sign an already signed manifest')
    data=dict(manifest,schema=1,channel='program',key_id=matches[0])
    if hashlib.sha256(package.read_bytes()).hexdigest()!=data['sha256']:
        raise ValueError('Candidate changed before signing')
    data['signature']=base64.b64encode(private.sign(canonical(data))).decode('ascii')
    private.public_key().verify(base64.b64decode(data['signature']),canonical({k:v for k,v in data.items() if k!='signature'}))
    return data
