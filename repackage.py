#!/usr/bin/env python
"""
SDM tar archive creation utility.

example usage:
    create_archive.py 8311_17_1_dicoms -f dicoms newarchive

"""
from __future__ import print_function

import os
import glob
import json
import tarfile
import calendar
import datetime


def datetime_encoder(o):
    if isinstance(o, datetime.datetime):
        if o.utcoffset() is not None:
            o = o - o.utcoffset()
        return {"$date": int(calendar.timegm(o.timetuple()) * 1000 + o.microsecond / 1000)}
    raise TypeError(repr(o) + " is not JSON serializable")


def datetime_decoder(dct):
    if "$date" in dct:
        return datetime.datetime.utcfromtimestamp(float(dct["$date"]) / 1000.0)
    return dct


def create_archive(path, content, arcname, metadata={}, **kwargs):
    # write metadata file
    metadata_filepath = os.path.join(content, 'METADATA.json')
    if os.path.exists(metadata_filepath):
        existing_metadata = json.load(open(metadata_filepath), object_hook=datetime_decoder)
        metadata.update(existing_metadata)
    with open(metadata_filepath, 'w') as json_file:
        json.dump(metadata, json_file, default=datetime_encoder)
        json_file.write('\n')
    # write digest file
    digest_filepath = os.path.join(content, 'DIGEST.txt')
    open(digest_filepath, 'w').close()  # touch file, so that it's included in the digest
    filenames = sorted(os.listdir(content), key=lambda fn: (fn.endswith('.json') and 1) or (fn.endswith('.txt') and 2) or fn)
    with open(digest_filepath, 'w') as digest_file:
        digest_file.write('\n'.join(filenames) + '\n')
    # create archive
    with tarfile.open(path, 'w:gz', **kwargs) as archive:
        archive.add(content, arcname, recursive=False)  # add the top-level directory
        for fn in filenames:
            archive.add(os.path.join(content, fn), os.path.join(arcname, fn))


def repackage(dcmtgz, outdir=None, args=None):
    if outdir and not os.path.exists(outdir):
        os.makedirs(outdir)
    outname = os.path.basename(dcmtgz)
    if outdir:
        outname = os.path.join(outdir, outname)
    if os.path.exists(outname):
        print ('%s exists! We will replace it.' % outname)
    with TemporaryDirectory() as tempdir_path:
        with tarfile.open(dcmtgz) as archive:
            def is_within_directory(directory, target):
                
                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)
            
                prefix = os.path.commonprefix([abs_directory, abs_target])
                
                return prefix == abs_directory
            
            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
            
                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")
            
                tar.extractall(path, members, numeric_owner=numeric_owner) 
                
            
            safe_extract(archive, path=tempdir_path)
        dcm_dir = glob.glob(os.path.join(tempdir_path, '*'))[0]
        metadata = {'filetype': 'dicom'}
        if args.group:
            if not args.project:
                args.project='unknown'
            overwrite = {'overwrite': { 'group_name': args.group, 'project_name': args.project }}
        metadata.update(overwrite)
        basename = os.path.basename(dcm_dir)
        print ('repackaging %s to %s' % (dcmtgz, outname))
        create_archive(outname, dcm_dir, basename, metadata, compresslevel=6)

"""This is a backport of TemporaryDirectory from Python 3.3."""


import warnings as _warnings
import sys as _sys
import os as _os

from tempfile import mkdtemp

template = "tmp"

# entire contents of tempfile copied here for portability
class TemporaryDirectory(object):
    """Create and return a temporary directory.  This has the same
    behavior as mkdtemp but can be used as a context manager.  For
    example:

        with TemporaryDirectory() as tmpdir:
            ...

    Upon exiting the context, the directory and everything contained
    in it are removed.
    """

    def __init__(self, suffix="", prefix=template, dir=None):
        self._closed = False
        self.name = None # Handle mkdtemp raising an exception
        self.name = mkdtemp(suffix, prefix, dir)

    def __repr__(self):
        return "<{} {!r}>".format(self.__class__.__name__, self.name)

    def __enter__(self):
        return self.name

    def cleanup(self, _warn=False):
        if self.name and not self._closed:
            try:
                self._rmtree(self.name)
            except (TypeError, AttributeError) as ex:
                # Issue #10188: Emit a warning on stderr
                # if the directory could not be cleaned
                # up due to missing globals
                if "None" not in str(ex):
                    raise
                print("ERROR: {!r} while cleaning up {!r}".format(ex, self,),
                      file=_sys.stderr)
                return
            self._closed = True
            if _warn:
                self._warn("Implicitly cleaning up {!r}".format(self),
                           ResourceWarning)

    def __exit__(self, exc, value, tb):
        self.cleanup()

    def __del__(self):
        # Issue a ResourceWarning if implicit cleanup needed
        self.cleanup(_warn=True)

    # XXX (ncoghlan): The following code attempts to make
    # this class tolerant of the module nulling out process
    # that happens during CPython interpreter shutdown
    # Alas, it doesn't actually manage it. See issue #10188
    _listdir = staticmethod(_os.listdir)
    _path_join = staticmethod(_os.path.join)
    _isdir = staticmethod(_os.path.isdir)
    _islink = staticmethod(_os.path.islink)
    _remove = staticmethod(_os.remove)
    _rmdir = staticmethod(_os.rmdir)
    _os_error = OSError
    _warn = _warnings.warn

    def _rmtree(self, path):
        # Essentially a stripped down version of shutil.rmtree.  We can't
        # use globals because they may be None'ed out at shutdown.
        for name in self._listdir(path):
            fullname = self._path_join(path, name)
            try:
                isdir = self._isdir(fullname) and not self._islink(fullname)
            except self._os_error:
                isdir = False
            if isdir:
                self._rmtree(fullname)
            else:
                try:
                    self._remove(fullname)
                except self._os_error:
                    pass
        try:
            self._rmdir(path)
        except self._os_error:
            pass


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('target', help='input tgz or dir to walk)')
    ap.add_argument('-o', '--output_dir', help='output into this directory, will create if doesn not exist')
    ap.add_argument('-g', '--group', type=str,  help='name of group to sort data into')
    ap.add_argument('-p', '--project', type=str, help='name of project to sort data into')
    args = ap.parse_args()

    outdir = None
    if args.output_dir:
        outdir = os.path.abspath(args.output_dir)
        print ('outputting to %s' % outdir)

    if os.path.isdir(args.target):
        for f in glob.glob(os.path.join(args.target, '*.tgz')):
            repackage(f, args.output_dir, args)
    elif os.path.isfile(args.target):
        repackage(args.target, args.output_dir, args)
