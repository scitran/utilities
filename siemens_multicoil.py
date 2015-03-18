#!/usr/bin/env python
# @author:  Kevin S Hahn
"""
Siemens_multicoil.py creates a siemens multicoil nifti from two input dicom.tgz.

Takes sorted dicom.tgz as inputs.  Use `dicomsort.py tarsort ./mess/of/dicoms ./sort_dest ./tar_dest`.
Writes merged nifti file to the current working directory.


Examples
--------

sort the dicoms

.. code-block::bash

    dicomsort.py tarsort ./mess/of/dicoms ./sort/path ./tar/path


combine niftis

.. code-block::bash

    siemens_multicoil.py ./tar/path/individual_coils_dicoms.tgz ./tar/path/combined_coils_dicoms.tgz


"""


import os
import logging
import nibabel
import dcmstack
import warnings
import traceback        # log tracebacks
import numpy as np

log = logging.getLogger(os.path.basename(__file__)[:-3])
logging.basicConfig(level=logging.INFO)
warnings.simplefilter("ignore", FutureWarning)

import scitran.data as scidata         # use .parse and .write interfaces
import tempdir as tempfile


class ProcessorError(Exception):
    def __init__(self, message, log_level=None):
        super(ProcessorError, self).__init__(message)
        if log_level is not None:
            message = '%s\n%s' % (message, traceback.format_exc())
            log.log(log_level, message)


class NiftiConcat(object):

    """Convert two tgz to niftis and then merge the two niftis into one."""

    def __init__(self, input_list, outbase, voxel_order='LPS'):
        super(NiftiConcat, self).__init__()
        self.inputs = input_list
        self.outbase = outbase
        for f in input_list:
            if not os.path.exists(f):
                raise ProcessorError('file %s does not exist. bailing' % f, log_level=logging.ERROR)
        self.voxel_order = voxel_order
        self.outbase = outbase
        log.info('preparing to reconstruct %s' % str(self.inputs))

    def process(self):
        log.info('reconstructing and concatenating')
        outfiles = []
        first_tr = None
        with tempfile.TemporaryDirectory(dir=None) as temp_dirpath:
            for f in self.inputs:
                fpath = os.path.abspath(f)
                dcm_ds = scidata.parse(fpath, filetype='dicom', load_data=True, ignore_json=True)
                if not first_tr:
                    first_tr = dcm_ds.tr
                # save info to name this nifti
                label = '%s_%s' % (dcm_ds.exam_no, dcm_ds.series_no)
                intermediate = os.path.join(temp_dirpath, '_%s' % label)
                # save info to name the final output
                if not self.outbase:
                    self.outbase = os.path.join(label + '_multicoil.nii.gz')
                result = scidata.write(dcm_ds, dcm_ds.data, intermediate, filetype='nifti', voxel_order=self.voxel_order)
                log.debug('reconstructed nifti: %s' % result)
                # maintain a list of intermediate files
                outfiles += result

            first_nii_header = None
            first_qto_xyz = None    # to be able to check if any is saved at all.
            seq = []
            # create a sequence from the intermediate files
            # resulting sequence items should have consistent dimensions
            log.debug('combinging niftis: %s' % str(outfiles))
            for f in outfiles:
                nii = dcmstack.dcmmeta.NiftiWrapper(nibabel.load(f), make_empty=True)
                # store the header from the first outfile
                if first_nii_header is None:
                    log.debug('storing first input nifti header')
                    first_nii_header = nii.nii_img.get_header()
                if first_qto_xyz is None:     # is array set?
                    log.debug('storing first input affine')
                    first_qto_xyz = nii.nii_img.get_affine()
                # build up the sequence of nifti wrappers
                if len(nii.nii_img.get_shape()) == 4:
                    seq += [nii_wrp for nii_wrp in nii.split()]
                else:
                    seq += [nii]

            # combine the sequence of nifti wrappers, raises error if shapes not consistent
            nii_merge = dcmstack.dcmmeta.NiftiWrapper.from_sequence(seq)
            nii_merge.nii_img.update_header()               # update the underlying nifti header
            nii_header = nii_merge.nii_img.get_header()     # reference to underlying nifti header

            # adjust the new header
            nii_header['descrip'] = first_nii_header['descrip']

            data = nii_merge.nii_img.get_data()
            if np.iscomplexobj(data):
                clip_vals = np.percentile(np.abs(data), (10.0, 99.5))
            else:
                clip_vals = np.percentile(data, (10.0, 99.5))
            nii_header.structarr['cal_min'] = clip_vals[0]
            nii_header.structarr['cal_max'] = clip_vals[1]
            nii_header['pixdim'][4] = first_tr

            if os.path.exists(self.outbase):
                raise ProcessorError('output file %s already exists. not overwriting. bailing.', log_level=logging.ERROR)
            else:
                nii_merge.to_filename(self.outbase)
                if os.path.exists(self.outbase):
                    log.info('generated %s' % self.outbase)
                else:
                    raise ProcessorError('output file %s does not exist?' % self.outbase, log_level=logging.ERROR)
                    return [self.outbase]


if __name__ == '__main__':

    import argparse

    argparser = argparse.ArgumentParser()
    argparser.add_argument('inputs', nargs='+', help='paths of input(s)')
    argparser.add_argument('-o', '--outbase', help='base for output names')
    argparser.add_argument('-v', '--voxel_order', help='reorder the voxels, default LPS', default='LPS')
    argparser.add_argument('-d', '--debug', help='enable debug logging', action='store_true', default=False)
    args = argparser.parse_args()

    if args.debug:
        log.setLevel(logging.DEBUG)

    outbase = None
    if args.outbase:
        outbase = args.outbase

    inputs = []
    for i in args.inputs:
        inputs.append(os.path.abspath(i))

    n = NiftiConcat(inputs, outbase, args.voxel_order)
    n.process()
