#!/usr/bin/env python
import json
import names # Use 'pip install names'
import random
import pymongo

'''
Updates the DB for a dev instance, making the subject subdocuments rich and interesting.
'''

# Connect to the DB
db = pymongo.MongoClient('mongodb://docker.local.flywheel.io:9001/scitran').get_default_database()

# Update DB: Set group names to use the group '_id' (Should be done by the UI)
for g in db.groups.find({},['_id']):
    group_name = g['_id'].capitalize() + ' Group'
    db.groups.update_one({'_id': g['_id']},{'$set':{'name': group_name}})

# Configure tags for the groups
tags = ['Good Subject', 'Bad Subject', 'To Process', 'Processed', 'To Analyze', 'Analyzed',  'Control', 'Patient', 'NSF Grant', 'NIH Grant', 'NIMH Grant']
groups = list(db.groups.find())
for g in groups:
    db.groups.update_one({'_id':g['_id']}, {'$set':{'tags':tags}})

# Randomly assign tags from each group to each session
tags1 = tags[:2]
tags2 = tags[2:6]
tags3 = tags[6:8]
tags4 = tags[8:]
sessions = list(db.sessions.find())
for ses in sessions:
    tag_set = []
    tag_set.append(random.choice(tags1))
    tag_set.append(random.choice(tags2))
    tag_set.append(random.choice(tags3))
    tag_set.append(random.choice(tags4))
    db.sessions.update_one({'label': ses['label']}, {'$set':{'tags':tag_set}})

# Get a list of the subjects/sessions
subjects = list(db.sessions.find({}, ['subject']))

# Get unique subject codes (some have multiple sessions)
codes = set([s['subject']['code'] for s in subjects])
total_sessions = len(codes)

# Update the subject subdocument only once per unique subject code
idx = 0
for c in codes:
    # Set half to male, rest female, using gender specific names
    if idx <= total_sessions * 0.5:
        first_name = names.get_first_name(gender='male')
        sex = 'male'
    else:
        first_name = names.get_first_name(gender='female')
        sex = 'female'
    last_name = names.get_last_name()

    # Set the age (in seconds) from a normal distrubition
    age = int(random.normalvariate(35, 10) * 31536000)

    # Build some fun subject metadata for each subject
    metadata = {}
    metadata['IQ'] = int(random.normalvariate(100, 15))
    metadata['Education'] = int(random.normalvariate(14, 2))
    ses = ['High', 'Middle', 'Low']
    metadata['SES'] = ses[random.randrange(0, len(ses))]
    metadata['TOWRE'] = int(random.normalvariate(100, 15))
    metadata['GORT'] = int(random.normalvariate(100, 15))
    metadata['SAT'] = int(random.normalvariate(1490, 100))
    metadata['Verbal_Reasoning'] = {}
    metadata['Verbal_Reasoning']['Score_1'] = random.randrange(130, 170)
    metadata['Verbal_Reasoning']['Score_2'] = random.randrange(130, 170)
    metadata['Quantitative_Reasoning'] = {}
    metadata['Quantitative_Reasoning']['Score_1'] = random.randrange(130, 170)
    metadata['Quantitative_Reasoning']['Score_2'] = random.randrange(130, 170)
    metadata['Analytical_Writing'] = {}
    metadata['Analytical_Writing']['Score_1'] = random.randrange(2, 6)
    metadata['Analytical_Writing']['Score_2'] = random.randrange(2, 6)

    db.sessions.update_many({'subject.code': c},{'$set':{'subject.lastname': last_name}})
    db.sessions.update_many({'subject.code': c},{'$set':{'subject.firstname': first_name}})
    db.sessions.update_many({'subject.code': c},{'$set':{'subject.sex': sex}})
    db.sessions.update_many({'subject.code': c},{'$set':{'subject.age': age}})
    db.sessions.update_many({'subject.code': c},{'$set':{'subject.metadata': metadata}})

    # Increment the index
    idx +=1
