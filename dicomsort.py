#!/usr/bin/env python

import os
import json
import time
import dicom
import hashlib
import tarfile
import argparse


def create_archive(path, content, arcname, **kwargs):
    def add_to_archive(archive, content, arcname):
        archive.add(content, arcname, recursive=False)
        if os.path.isdir(content):
            for fn in sorted(os.listdir(content), key=lambda fn: not fn.endswith('.json')):
                add_to_archive(archive, os.path.join(content, fn), os.path.join(arcname, fn))
    with tarfile.open(path, 'w:gz', **kwargs) as archive:
        add_to_archive(archive, content, arcname)


def write_json_file(path, json_document):
    with open(path, 'w') as json_file:
        json.dump(json_document, json_file)


def checksum(path):
    hash_ = hashlib.sha1()
    with open(path, 'rb') as fd:
        for chunk in iter(lambda: fd.read(1048577 * hash_.block_size), ''):
            hash_.update(chunk)
    return hash_.digest()


def sort(args):
    if not os.path.isdir(args.sort_path):
        os.makedirs(args.sort_path)
    if not os.access(args.sort_path, os.W_OK):
        print 'error: sort_path is not a writable directory'

    files = []
    print 'inspecting %s' % args.path
    for dirpath, dirnames, filenames in os.walk(args.path):
        for filepath in [dirpath + '/' + fn for fn in filenames if not fn.startswith('.')]:
            if not os.path.islink(filepath):
                files.append(filepath)
    file_cnt = len(files)
    cnt_width = len(str(file_cnt))

    print 'found %d files to sort (ignoring symlinks and dotfiles)' % file_cnt
    time.sleep(2)

    for i, filepath in enumerate(files):
        print '%*d/%d' % (cnt_width, i+1, file_cnt),
        try:
            dcm = dicom.read_file(filepath, stop_before_pixels=True)
        except:
            print 'not a DICOM file: %s' % filepath
        else:
            if dcm.get('Manufacturer').upper() != 'SIEMENS':
                acq_name = '%s_%s_%s_dicoms' % (dcm.StudyID, dcm.SeriesNumber, int(dcm.get('AcquisitionNumber', 1)))
            else:
                acq_name = '%s_%s_dicoms' % (dcm.StudyID, dcm.SeriesNumber)
            acq_path = os.path.join(args.sort_path, dcm.StudyInstanceUID, acq_name)
            if not os.path.isdir(acq_path):
                os.makedirs(acq_path)
            new_filepath = os.path.join(acq_path, os.path.basename(filepath))
            if not os.path.isfile(new_filepath):
                print 'sorting %s' % filepath
                os.rename(filepath, new_filepath)
            elif checksum(filepath) == checksum(new_filepath):
                print 'deleting duplicate %s' % filepath
                os.remove(filepath)
            else:
                print 'retaining non-identical duplicate %s of %s' % (filepath, new_filepath)


def tar(args):
    if not os.path.isdir(args.tar_path):
        os.makedirs(args.tar_path)
    if not os.access(args.tar_path, os.W_OK):
        print 'error: tar_path is not a writable directory'

    dirs = []
    print 'inspecting %s' % args.sort_path
    for dirpath, dirnames, filenames in os.walk(args.sort_path):
	if not dirnames and not os.path.basename(dirpath).startswith('.') and not os.path.islink(dirpath):
	    dirs.append(dirpath)
    dir_cnt = len(dirs)
    cnt_width = len(str(dir_cnt))

    print 'found %d directories to compress (ignoring symlinks and dotfiles)' % dir_cnt
    time.sleep(2)

    metadata = {'filetype': 'dicom'}
    for i, dirpath in enumerate(dirs):
	dirname = os.path.basename(dirpath)
	dir_relpath = os.path.relpath(dirpath, args.sort_path)
        print '%*d/%d compressing %s' % (cnt_width, i+1, dir_cnt, dir_relpath)
        write_json_file(dirpath + '/metadata.json', metadata)
        create_archive(os.path.join(args.tar_path, dir_relpath.replace('/', '_') + '.tgz'), dirpath, dirname, compresslevel=6)


def tarsort(args):
    sort(args)
    print
    tar(args)


parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(help='operation to perform')

sort_parser = subparsers.add_parser(
        name='sort',
        help='sort all dicom files in a dicrectory tree',
        )
sort_parser.add_argument('path', help='input path of unsorted data')
sort_parser.add_argument('sort_path', help='output path for sorted data')
sort_parser.set_defaults(func=sort)

tar_parser = subparsers.add_parser(
        name='tar',
        help='tar a sorted directory tree of dicoms',
        )
tar_parser.add_argument('sort_path', help='input path of sorted data')
tar_parser.add_argument('tar_path', help='output path for tar\'ed data')
tar_parser.set_defaults(func=tar)

tarsort_parser = subparsers.add_parser(
        name='tarsort',
        help='sort all dicom files in a dicrectory tree and tar the result',
        )
tarsort_parser.add_argument('path', help='input path of unsorted data')
tarsort_parser.add_argument('sort_path', help='input path of sorted data')
tarsort_parser.add_argument('tar_path', help='output path for tar\'ed data')
tarsort_parser.set_defaults(func=tarsort)

args = parser.parse_args()
args.func(args)
