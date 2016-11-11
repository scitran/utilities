from metadata_from_gear_output import meta_create
import os
import pytest
import json


files_in_dirs_fixture = os.path.join(
    os.path.dirname(__file__), 'fixtures/gear-output-files-in-dirs')
metadata_path = os.path.join(files_in_dirs_fixture, '.metadata.json')


@pytest.fixture(scope="function")
def creates_metadata():
    try:
        yield
    finally:
        if os.path.exists(metadata_path):
            os.unlink(metadata_path)


def test_meta_generate(creates_metadata):
    meta_create(files_in_dirs_fixture)
    with open(metadata_path, 'r') as f:
        assert json.load(f) == {'acquisition': {'files': [
            {'name': 'log', 'type': 'None'},
            {'name': 'notes.csv', 'type': 'tabular data'}
        ]}}
