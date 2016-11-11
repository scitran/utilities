#!/usr/bin/env python

import os
import json
import datetime

# Build dict of types, which maps extensions to known data types
data_types = {
    "bval":         [ ".bval", ".bvals" ],
    "bvec":         [ ".bvec", ".bvecs" ],
    "dicom":        [ ".dcm", ".dcm.zip", ".dicom.zip" ],
    "parrec":       [ ".parrec.zip", ".par-rec.zip" ],
    "gephysio":     [ ".gephysio.zip" ],
    "MATLAB data":  [ ".mat" ],
    "nifti":        [ ".nii.gz", ".nii" ],
    "pfile":        [ ".7.gz", ".7" ],
    "PsychoPy data":  [ ".psydat" ],
    "qa":           [ ".qa.png", ".qa.json" ],

    "archive":      [ ".zip", ".tbz2", ".tar.gz", ".tbz", ".tar.bz2", ".tgz", ".tar", ".txz", ".tar.xz" ],
    "document":     [ ".docx", ".doc" ],
    "image":        [ ".jpg", ".tif", ".jpeg", ".gif", ".bmp", ".png", ".tiff" ],
    "markup":       [ ".html", ".htm" ],
    "log":          [ ".log" ],
    "pdf":          [ ".pdf" ],
    "presentation": [ ".ppt", ".pptx" ],
    "source code":  [ ".c", ".py", ".cpp", ".js", ".m", ".json", ".java", ".php", ".css" ],
    "spreadsheet":  [ ".xls", ".xlsx" ],
    "tabular data": [ ".csv.gz", ".csv" ],
    "text":         [ ".txt" ],
    "video":        [ ".mpeg", ".mpg", ".mov", ".mp4", ".m4v", ".mts" ]
}


def meta_create(outbase):

    # Default to gear output directory
    if not os.path.isdir(outbase):
        outbase = '/flywheel/v0/output'

    # Build a dict of output file names and data types
    output_files = os.listdir(outbase)
    files = []
    if len(output_files) > 0:
        for f in output_files:
            fdict = {}
            fdict['name'] = f

            # Check file extension against every data_type to determine type
            ftype = ''
            for d in data_types:
                extensions = list(data_types[d])
                # For any given type there could be multiple matching extensions
                if any([f.endswith(ext) for ext in extensions]):
                    ftype = d
            if not ftype:
                ftype = 'None'

            fdict['type'] = ftype
            files.append(fdict)

        # Assemble final metadata
        metadata = {}
        metadata['acquisition'] = {}
        metadata['acquisition']['files'] = files

        # Write metadata file
        with open(os.path.join(outbase, '.metadata.json'), 'w') as metafile:
            json.dump(metadata, metafile)

    return os.path.join(outbase,'.metadata.json')

if __name__ == '__main__':
    """

    Given a directory ('outbase') determine all file names and types by mapping extenstions to data_types dict.

    Generate and write '.metadata.json' in 'outbase'. Metadata will consist of filenames and data types for all files in 'outbase'.

    Example Usage:
        python metadata_from_gear_outuput.py /output/directory/ scitran/dtiinit

    """
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('outbase', help='Base directory to be scanned for output files')
    ap.add_argument('gearname', help='Name of running gear', default='gear')
    args = ap.parse_args()

    metafile = meta_create(args.outbase)

    if os.path.isfile(metafile):
        print args.gearname + '  generated %s' % metafile
    else:
        print args.gearname + '  Failed to create metadata.json'
