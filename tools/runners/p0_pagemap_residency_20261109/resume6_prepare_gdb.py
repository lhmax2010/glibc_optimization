#!/usr/bin/env python3
"""Fresh downloads from the one approved repository; host unpack only."""
import bz2
import datetime
import gzip
import hashlib
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
sys.dont_write_bytecode=True
from resume6_driver import D,RoundDriver,Stop,write,utc

NAMES=['gdb-16.3-1.2.armv7l.rpm','libgmp-4.2.1-1.13.armv7l.rpm','gdbm-1.8.3-1.16.armv7l.rpm',
       'libpython3_141_0-3.14.2-1.11.armv7l.rpm','python3-base-3.14.2-1.11.armv7l.rpm','python3-3.14.2-1.12.armv7l.rpm']
APPROVED='http://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Base-Toolchain/tizen-base-toolchain_20261030.120529/'
OUT=D/'resume6_rpms'
REQUESTS=[]

def sha(path,algorithm='sha256'):
    h=hashlib.new(algorithm)
    with path.open('rb') as f:
        for block in iter(lambda:f.read(65536),b''):h.update(block)
    return h.hexdigest()

def approved(url):
    if not url.replace('https://','http://',1).startswith(APPROVED):raise Stop('STOP_UNAPPROVED_SOURCE '+url)

def fetch(url,path):
    approved(url)
    if path.exists():raise Stop('STOP_NOT_A_FRESH_DOWNLOAD '+str(path))
    rec={'url':url,'start_utc':utc(),'file':str(path.relative_to(D))}
    REQUESTS.append(rec);write('rpm_http_requests.json',REQUESTS)
    print('DOWNLOAD',url,flush=True)
    try:
        with urllib.request.urlopen(url,timeout=90) as r,path.open('xb') as f:
            approved(r.geturl());rec.update(final_url=r.geturl(),http_status=r.status)
            while True:
                block=r.read(65536)
                if not block:break
                f.write(block)
        rec.update(end_utc=utc(),bytes=path.stat().st_size,sha256=sha(path))
    except Exception as e:
        rec.update(end_utc=utc(),error=str(e));raise
    finally:write('rpm_http_requests.json',REQUESTS)
    print('DOWNLOADED',path.name,rec['bytes'],rec['sha256'],flush=True)

def main():
    loc=json.loads((D/'resume6_repo_location.json').read_text())
    repomd=OUT/'repomd.xml';fetch(urllib.parse.urljoin(loc['repodata'],'repomd.xml'),repomd)
    ns={'r':'http://linux.duke.edu/metadata/repo'}
    tree=ET.parse(repomd);primary=tree.find("r:data[@type='primary']",ns)
    if primary is None:raise Stop('STOP_NO_PRIMARY_METADATA')
    href=primary.find('r:location',ns).attrib['href'];check=primary.find('r:checksum',ns)
    primary_file=OUT/Path(href).name
    fetch(urllib.parse.urljoin(loc['repo_root'],href),primary_file)
    alg=check.attrib['type'].replace('sha','sha',1)
    if alg=='sha':alg='sha1'
    if sha(primary_file,alg)!=check.text.strip():raise Stop('STOP_PRIMARY_CHECKSUM_MISMATCH')
    metadata={'repomd_sha256':sha(repomd),'revision':tree.findtext('r:revision',namespaces=ns),
              'primary_url':urllib.parse.urljoin(loc['repo_root'],href),'primary_checksum_type':alg,
              'primary_expected_checksum':check.text.strip(),'primary_checksum_pass':True}
    write('repodata_proof.json',metadata)
    suffix=primary_file.name
    if suffix.endswith('.gz'):stream=gzip.open(primary_file,'rb')
    elif suffix.endswith('.bz2'):stream=bz2.open(primary_file,'rb')
    elif suffix.endswith('.xz'):stream=lzma.open(primary_file,'rb')
    elif suffix.endswith('.xml'):stream=primary_file.open('rb')
    elif suffix.endswith('.zst'):
        import zstandard
        stream=zstandard.ZstdDecompressor().stream_reader(primary_file.open('rb'))
    else:raise Stop('STOP_UNKNOWN_PRIMARY_COMPRESSION')
    found={};n={'c':'http://linux.duke.edu/metadata/common'}
    with stream:
        for event,element in ET.iterparse(stream,events=('end',)):
            if element.tag!='{'+n['c']+'}package':continue
            location=element.find('c:location',n).attrib['href'];name=Path(location).name
            if name in NAMES:
                checksum=element.find('c:checksum',n)
                if checksum.attrib['type']!='sha256':raise Stop('STOP_RPM_METADATA_NOT_SHA256 '+name)
                entry=dict(file=name,url=urllib.parse.urljoin(loc['repo_root'],location),sha256=checksum.text.strip(),
                           bytes=int(element.find('c:size',n).attrib['package']),name=element.findtext('c:name',namespaces=n),
                           arch=element.findtext('c:arch',namespaces=n),version=element.find('c:version',n).attrib)
                if name in found:raise Stop('STOP_DUPLICATE_PACKAGE_METADATA '+name)
                found[name]=entry
            element.clear()
    write('rpm_metadata_selected.json',found)
    if set(found)!=set(NAMES):raise Stop('STOP_MISSING_REQUESTED_PACKAGES '+repr(set(NAMES)-set(found)))
    verified=[]
    for name in NAMES:
        entry=found[name];url=urllib.parse.urljoin(loc['packages'],name)
        if url!=entry['url']:raise Stop('STOP_PACKAGE_LOCATION_MISMATCH '+name)
        path=OUT/name;fetch(url,path)
        actual=sha(path);ok=actual==entry['sha256'] and path.stat().st_size==entry['bytes']
        verified.append(dict(entry,actual_sha256=actual,actual_bytes=path.stat().st_size,checksum_pass=ok))
        write('rpm_verification.json',verified)
        if not ok:raise Stop('HARD_STOP_RPM_SHA256_OR_SIZE_MISMATCH '+name)
    build=D/'resume6_gdb_build';build.mkdir();root=build/'gdbroot';root.mkdir()
    for i,name in enumerate(NAMES):
        print('UNPACK',name,flush=True)
        with (D/f'resume6_unpack_{i}.log').open('wb') as log:
            rpm=subprocess.Popen(['/usr/bin/rpm2cpio',str(OUT/name)],stdout=subprocess.PIPE,stderr=log)
            cp=subprocess.run(['/usr/bin/cpio','-idm'],stdin=rpm.stdout,stdout=log,stderr=log,cwd=root)
            rpm.stdout.close();rr=rpm.wait()
        if cp.returncode or rr:raise Stop('STOP_HOST_RPM_UNPACK '+name)
    archive=D/'resume6_gdbroot.tar'
    with (D/'resume6_gdbroot_tar.log').open('wb') as log:
        result=subprocess.run(['/usr/bin/tar','cf',str(archive),'-C',str(build),'gdbroot'],stdout=log,stderr=log)
    if result.returncode:raise Stop('STOP_HOST_GDBROOT_TAR')
    proof=dict(file=archive.name,bytes=archive.stat().st_size,sha256=sha(archive),packages=NAMES,utc=utc())
    write('gdbroot_archive.json',proof)
    print('GDBROOT_ARCHIVE',json.dumps(proof),flush=True)

if __name__=='__main__':
    os.umask(0o077)
    try:main()
    except Exception as e:
        b=RoundDriver();b.s.update(status='STOPPED',reason=str(e),stopped_utc=utc());b.save()
        print('STOP',str(e),flush=True);b.cleanup();sys.exit(2)
