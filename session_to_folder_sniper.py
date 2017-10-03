#! /usr/bin/env python
# -*- coding: utf-8 -*-


"""
NIMSFS session to folder sniper conversion utility.

This code will convert a NIMS v1.0 session to a folder
tree that the SciTran folder_sniper can ingest.

Users can optionally pass in group, project, and subject arguments. If these
arguments are not passed in they are gleaned from the folder structure within
the NIMS archive or read from the DICOM header.


"""

import os
import sys
import time
import glob
import gzip
import dicom
import shutil
import zipfile
import tarfile
import logging
import argparse
import subprocess
from distutils.dir_util import copy_tree


logging.basicConfig(
            format='%(asctime)s %(levelname)8.8s %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
                )
log = logging.getLogger()


def extract_subject_id(root_path, args):
    '''
    If no subjectID is provided as input, we will attempt to extract the ID from a dicom.
    If there are no dicom files then we use the name of the session folder to create a subject ID.
    If there is a dicom file, we read it and use the field that was passed in - if no field was
    passed in then we use values from the following fields, in order: PatientID, PatientName,
    StudyID ('ex' + StudyID).
    '''
    log.info('No subjectID provided - Attempting to extract subject ID from dicom...')
    subject_id = None
    study_id = None

    (file_paths, dir_paths, _, _, _) = get_paths(root_path)
    dicom_dirs = [d for d in dir_paths if d.endswith('dicom')]

    # Read the dicom file and return an id from (PatientID - PatientName - StudyDate+StudyTime)
    if dicom_dirs:
        dicom_files = [d for d in file_paths if d.startswith(dicom_dirs[0])]
        dcm = dicom.read_file(dicom_files[0])
        study_id = dcm.StudyID

        # Use the field that was passed in
        if args.subject_id_field and dcm.get(args.subject_id_field):
            subject_id = dcm.get(args.subject_id_field)

        # Use the PatientID field
        else:
            if dcm.PatientID and dcm.PatientID != args.group: # Some users put the group in this field
                subject_id = dcm.PatientID
                subject_id = subject_id.split('@')[0]
                if '/' in subject_id:# If the group/is still in the name then no subjectID was entered
                    subject_id = None

        # Use StudyID
        if not subject_id and dcm.StudyID:
            subject_id = 'ex' + dcm.StudyID

    # No dicoms - use the session folder name
    if not subject_id or subject_id.isspace(): # This is empty b/c there are no dicoms, or the id field set failed
        log.info('... subjectID could not be extraced from DICOM header - setting subjectID  from session label')
        subject_id = 'sub_' + os.path.basename(root_path).replace(' ', '_').replace(':','')

    # Sanitize subject_id
    subject_id = subject_id.replace(os.sep, '_')

    log.info('... subjectID set to %s' % subject_id)
    return subject_id, study_id


def screen_save_montage(dirs):
    screen_saves = [f for f in dirs if f.endswith('Screen_Save')]
    if screen_saves:
        log.info('... %s screen saves to process' % str(len(screen_saves)))
        for d in screen_saves:
            orig_pngs = glob.glob(d + '/*.png')
            montage_name = orig_pngs[0][:-5] + 'ScreenSave.png'
            pngs = [shellquote(p) for p in orig_pngs]
            # Build the montage (requires imagemagick)
            os.system('montage -geometry +4+4 ' + " ".join(pngs) + ' ' + shellquote(montage_name))
            # Move the contents of this folder to the correct acquitision directory
            ss_num = os.path.basename(d).split('_')[1][-2:] # This is the acquisition number we need
            if ss_num[0] == '0': # Drop the leading zero if it's the first char
                ss_num = ss_num[1:]
            for target in dirs:
                target_dir=False
                if os.path.basename(target).split('_')[1] == ss_num:
                    target_dir = target
                    break
            if target_dir:
                shutil.move(montage_name, target_dir)
                shutil.rmtree(d) # Remove the screen save folder
            else:
                log.info("No matching acquisition found... keeping only the montage.")
                [os.remove(x) for x in orig_pngs]
        log.info('... done')
    else:
        log.info('... 0 screen saves found')


def extract_dicoms(files):
    dicom_arcs = [f for f in files if f.endswith('_dicoms.tgz') or f.endswith('_dicom.tgz')]
    if dicom_arcs:
        log.info('... %s dicom archives to extract' % str(len(dicom_arcs)))
        for f in dicom_arcs:
            utd = untar(f, os.path.dirname(f))
            del_files = ['._*', 'DIGEST.txt', 'METADATA.json', 'metadata.json', 'digest.txt']
            for df in del_files:
                [os.remove(d) for d in glob.glob(utd + '/' + df)]
            log.debug('renaming %s' % utd)
            # TODO: This can be an issue if there is more than one dicom archive per acquisition
            os.rename(utd, os.path.join(os.path.dirname(utd), 'dicom'))
            os.remove(f)
            log.debug('Removing %s' % f)
        log.info('... done')
    else:
        log.info('... 0 dicom archives found')


def extract_pfiles(files):
    import zipfile
    pfile_arcs = [f for f in files if f.endswith('_pfile.tgz')]
    if pfile_arcs:
        log.info('... %s pfile archives to extract' % str(len(pfile_arcs)))
        for f in pfile_arcs:
            utd = untar(f, os.path.dirname(f))
            [_files, _dirs, _, _, _] = get_paths(utd)
            # TODO: Remove the files that should not be in the archive
            del_files = ['._*', 'DIGEST.txt', 'METADATA.json', 'metadata.json', 'digest.txt']
            for df in del_files:
                [os.remove(d) for d in glob.glob(utd + '/' + df)]
            # Gzip the P-file prior to adding to the archive
            for p in _files:
                if p.endswith('.7') and not p.endswith('_refscan.7'):
                    gzfile = create_gzip(p, os.path.join(utd, p + '.gz'))
                    os.remove(p)

            # Zip the utd directory
            zipdir(utd, utd + '.7.zip', os.path.basename(utd))

            # Clean up the directory and files
            shutil.rmtree(utd)
            os.remove(f)
        log.info('... done')
    else:
        log.info('... 0 pfile archives found')


def extract_and_zip_physio(files):
    physio_arcs = [f for f in files if f.endswith('_physio.tgz')]
    if physio_arcs:
        log.info('... %s physio archives to extract' % str(len(physio_arcs)))
        for f in physio_arcs:
            utd = untar(f, os.path.dirname(f))
            create_archive(utd, utd)
            os.rename(utd + '.zip', utd + '.gephysio.zip')
            shutil.rmtree(utd)
            os.remove(f)
        log.info('... done')
    else:
        log.info('... 0 physio archives found')


def extract_physio(files):
    physio_arcs = [f for f in files if f.endswith('.csv.gz')]
    if physio_arcs:
        log.info('... %s physio regressor file(s) to extract' % str(len(physio_arcs)))
        for f in physio_arcs:
            with gzip.open(f, 'rb') as in_file:
                s = in_file.read()
                with open(f[:-3], 'w') as a:
                    a.write(s)
            os.remove(f)
    else:
        log.info('... 0 physio regressors found')

def prune_tree(files, args):
    if args.prune:
        print args.prune
        log.debug('Pruning files that end with %s ' % args.prune)
        for p in args.prune:
            for f in files:
                if f.endswith(p) and os.path.isfile(p):
                    os.remove(f)
                    log.debug('Pruning file %s ' % f)


###### UTILITIES ######

def shellquote(s):
   return "'" + s.replace("'", "'\\''") + "'"


def get_paths(root_path):
    file_paths = []
    dir_paths = []
    groups = []
    projects = []
    sessions = []
    for (root, dirs, files) in os.walk(root_path):
        for name in files:
            file_paths.append(os.path.join(root, name))
        for name in dirs:
            dir_paths.append(os.path.join(root, name))
    if len(dir_paths) > 3:
        group_level = len(dir_paths[1].split(os.sep))
        project_level = group_level + 1
        session_level = project_level + 1
        [groups.append(d) for d in dir_paths if len(d.split(os.sep)) == group_level]
        [projects.append(d) for d in dir_paths if len(d.split(os.sep)) == project_level]
        [sessions.append(d) for d in dir_paths if len(d.split(os.sep)) == session_level]
    return (file_paths, dir_paths, groups, projects, sessions)


def untar(fname, path):
    tar = tarfile.open(fname)
    tar.extractall(path)
    untar_dir = '.'
    while untar_dir.startswith('.'):
        for name in range(0, len(tar.getnames())):
            untar_dir = os.path.dirname(tar.getnames()[name])
    untar_dir = os.path.join(path, untar_dir)
    tar.close()
    return untar_dir


def create_archive(content_dir, arcname):
    zipfilepath = content_dir + '.zip'
    with zipfile.ZipFile(zipfilepath, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        zf.write(content_dir, arcname)
        for fn in os.listdir(content_dir):
            zf.write(os.path.join(content_dir, fn), os.path.join(os.path.basename(arcname), fn))
    return zipfilepath


def zipdir(dirpath, zipname=None, arcbase=None):
    if not arcbase:
        arcbase = os.path.basename(dirpath)
    if not zipname:
        zipname = dirpath + '.zip'
    zipf = zipfile.ZipFile(zipname, 'w', zipfile.ZIP_DEFLATED, allowZip64=True)
    for root, dirs, files in os.walk(dirpath):
        for _file in files:
            zipf.write(os.path.join(root, _file), os.path.join(arcbase, _file))
    zipf.close()
    return zipname


def create_gzip(in_file, gz_file):
    if not gz_file:
        gz_file = in_file + '.gz'
    with open(in_file, 'rb') as f_in, gzip.open(gz_file, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    return gz_file


######################################################################################
def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-d', '--nimsfs_session_dir', help='NIMSfs raw directory', type=str)
    arg_parser.add_argument('-g', '--group', help='Group', type=str)
    arg_parser.add_argument('-p', '--project', help='project', type=str)
    arg_parser.add_argument('-o', '--output_path', help='path for untar data', type=str)
    arg_parser.add_argument('-s', '--subject', help='Subject Code', type=str, default='')
    arg_parser.add_argument('-i', '--subject_id_field', help='Look here for the subject id', type=str, default='')
    arg_parser.add_argument('-l', '--loglevel', default='info', help='log level [default=info]')
    arg_parser.add_argument('--prune', action='append', help='Files that end with this string will be pruned from final tree.')

    args = arg_parser.parse_args()

    log.setLevel(getattr(logging, args.loglevel.upper()))
    log.debug(args)

    # Output directory where the repackaged data will be written
    output_path = os.path.join(os.path.realpath(args.output_path))


    ## 1. Make the output directory where the session will be copied
    output_deep_path=os.path.join(output_path,'nims', args.group, args.project, os.path.basename(args.nimsfs_session_dir))
    os.makedirs(output_deep_path)


    ## 2. Replicate session tree for conversion
    log.info('Converting %s to %s' % (args.nimsfs_session_dir, output_path))
    # TODO right now this will copy the data to the output_deep_path, but that is not at all what we want to do.
    copy_tree(args.nimsfs_session_dir, output_deep_path)


    ## 3. Generate file paths and directory paths
    log.info('Extracting path and file info in %s' % output_path)
    (file_paths, dir_paths, group_paths, project_paths, session_paths) = get_paths(output_path)
    db_root_path = dir_paths[0] # sdm or nims path (removed later)

    ## 4. Handle missing arguments
    if not args.group:
        get_group = True
    else:
        get_group = False
    if not args.project:
        get_project = True
    else:
        get_project = False
    if not args.subject:
        get_subject_id = True
    else:
        get_subject_id = False

    # Go through groups/projects/sessions
    for group in group_paths:
        if get_group == True:
            args.group = os.path.basename(group)
        log.debug(group)
        log.debug(args)
        projects = []
        [projects.append(p) for p in project_paths if p.startswith(group)]

        for project in projects:
            if get_project == True:
                args.project = os.path.basename(project)
            log.debug(project)
            log.debug(args)
            sessions = []
            [sessions.append(s) for s in session_paths if s.startswith(project)]

            for session in sessions:
                (file_paths, dir_paths, _, _, _) = get_paths(session)
                log.debug(session)
                log.debug(project)
                log.debug(args)

                ## 5. Remove the 'qa.json' files (UI can't read them)
                #TODO Should we do this???
                # Prune tree to remove unwanted files
                prune_tree(file_paths, args)
                for f in file_paths:
                    if f.endswith('qa.json') or f.endswith('.pyrdb'):
                        os.remove(f)

                ## 6. Rename: qa file to [...].qa.png and montage to .montage.zip
                for f in file_paths:
                    if f.endswith('_qa.png'):
                        new_name = f.replace('_qa.png', '.qa.png')
                        os.rename(f, new_name)
                    if f.endswith('_montage.zip'):
                        new_name = f.replace('_montage.zip', '.montage.zip')
                        os.rename(f, new_name)

                ## 7. Extract physio regressors (_physio_regressors.csv.gz)
                log.info('Extracting physio regressors...')
                extract_physio(file_paths)

                ## 8. Move _physio.tgz files to gephsio and zip (removing digest .txt)
                log.info('Extracting and repackaging physio data...')
                extract_and_zip_physio(file_paths)

                ## 9. Extract pfiles and remove the digest and metadata files and gzip the file
                log.info('Extracting and repackaging pfiles...')
                extract_pfiles(file_paths)

                ## 10. Extract all the dicom archives and rename to 'dicom'
                log.info('Extracting dicom archives...')
                extract_dicoms(file_paths)

                ## 11. Create a montage of the screen saves and move them to the correct acquisition
                log.info('Processing screen saves...')
                screen_save_montage(dir_paths)

                ## 12. Get the subjectID (if not passed in)
                extracted_subject_id, extracted_study_id = extract_subject_id(session, args)
                if get_subject_id == True:
                    args.subject = extracted_subject_id

                ## 13. Make the folder hierarchy and move the session to it's right place
                log.info('Organizing final file structure...')
                target_path = os.path.join(output_path, args.group, args.project, args.subject)
                log.debug('Target Path: %s' % target_path)
                log.debug('Session Path: %s' % session)
                if not os.path.isdir(target_path):
                    os.makedirs(target_path)
                shutil.move(session, target_path) # Move the session to the target
                if extracted_study_id:
                    log.info('Renaming final folder structure: %s' % os.path.join(target_path, extracted_study_id))
                    os.rename(os.path.join(target_path, os.path.basename(session)), os.path.join(target_path, extracted_study_id))


    ## 15. Remove the db root folder
    shutil.rmtree(db_root_path)


    log.info("Done.")
    print output_path


if __name__ == '__main__':
    main()
