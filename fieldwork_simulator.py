#!/usr/bin/env python

"""HDSS fieldwork simulation, using openHDS"""

__email__ = "nicolas.maire@unibas.ch"
__status__ = "Alpha"

import json
import datetime
import os
import MySQLdb.cursors
import random
import numpy as np
import time
from matplotlib.path import Path
import argparse
import submission
import util
import pickle
import pprint
import logging

conf_dir = 'conf'
config = None
site = None
aggregate_url = ''
open_hds_connection = None
odk_connection = None
m_first_names = []
f_first_names = []
last_names = []

area_polygon = None
area_extent = None
locations_per_social_group = None
individuals_per_social_group = None
pop_size_baseline = 0
min_age_head_of_social_group = 0
min_age_marriage = 0
proportion_females = 0.5
birth_rate = 0
death_rate = 0
inmigration_rate = 0
outmigration_rate = 0
internal_migration_rate = 0

t = 0

hdss = {'field_workers': [], 'social_groups': []}


def init(site_config):
    """Initialization"""
    global config, m_first_names, f_first_names, last_names, aggregate_url, open_hds_connection, odk_connection
    global area_polygon, area_extent, locations_per_social_group, individuals_per_social_group
    global pop_size_baseline, site, min_age_head_of_social_group, proportion_females, birth_rate, death_rate
    global inmigration_rate, outmigration_rate, internal_migration_rate
    global min_age_marriage, hdss
    with open(os.path.join(conf_dir, 'config.json')) as config_file:
        config = json.load(config_file)
    with open(os.path.join(conf_dir, site_config + '.json')) as site_file:
        site = json.load(site_file)
    open_hds_connection = MySQLdb.connect(host=config['open_hds_server']['db_host'],
                                          user=config['open_hds_server']['db_user'],
                                          passwd=config['open_hds_server']['db_password'],
                                          db=config['open_hds_server']['db_name'],
                                          cursorclass=MySQLdb.cursors.DictCursor)
    open_hds_connection.autocommit(True)
    odk_connection = MySQLdb.connect(host=config['odk_server']['db_host'],
                                     user=config['odk_server']['db_user'],
                                     passwd=config['odk_server']['db_password'],
                                     db=config['odk_server']['db_name'],
                                     cursorclass=MySQLdb.cursors.DictCursor)
    odk_connection.autocommit(True)
    aggregate_url = config['odk_server']['aggregate_url']
    with open(os.path.join(conf_dir, 'firstnames.csv')) as f:
        first_names = list(f.read().splitlines(False))
    for first_name in first_names:
        fn = first_name.split(';')
        if fn[0] == 'M':
            m_first_names.append(fn[1])
        else:
            f_first_names.append(fn[1])
    with open(os.path.join(conf_dir, 'lastnames.csv')) as f:
        last_names = list(f.read().splitlines(False))
    area_outline_vertices = []
    for point in site['general']['area_polygon']:
        area_outline_vertices.append(point)
    area_polygon = Path(area_outline_vertices)
    area_extent = area_polygon.get_extents().get_points()
    pop_size_baseline = site['general']['pop_size_baseline']
    locations_per_social_group = site['socialgroup']['locations_per_social_group']
    individuals_per_social_group = site['socialgroup']['individuals_per_social_group']
    min_age_head_of_social_group = site['socialgroup']['min_age_head']
    min_age_marriage = site['relationship']['min_age_marriage']
    proportion_females = 1 / (1 + site['general']['sex_ratio'])
    birth_rate = site['general']['birth_rate']
    death_rate = site['general']['death_rate']
    inmigration_rate = site['general']['inmigration_rate']
    outmigration_rate = site['general']['outmigration_rate']
    internal_migration_rate = site['general']['internal_migration_rate']
    #either load population from pickle, or re-init db and create hdss dictionary
    if not 'pickle_in' in site['general']:
        clean_db()
        create_fws(site['fieldworker'])
        create_location_hierarchy(site['locationhierarchy'])
    else:
        with open(os.path.join(conf_dir, site['general']['pickle_in'])) as f:
            hdss = pickle.load(f)


def clean_db():
    """Remove any data from openhds that is not in 'openhds-required-data'"""
    cursor = open_hds_connection.cursor()
    cursor.execute("SET FOREIGN_KEY_CHECKS=0")
    cursor.execute("DELETE FROM locationhierarchy where uuid != 'hierarchy_root'")
    cursor.execute("DELETE FROM fieldworker where uuid != 'UnknownFieldWorker'")
    cursor.execute("DELETE FROM individual where uuid != 'Unknown Individual'")
    for table in config['open_hds_server']['tables_to_truncate']:
        cursor.execute("TRUNCATE " + table)
    cursor.execute("SET FOREIGN_KEY_CHECKS=1")
    cursor.close()
    open_hds_connection.commit()
    cursor = odk_connection.cursor()
    for form in config['odk_server']['forms']:
        cursor.execute("TRUNCATE " + form)
    cursor.execute("CREATE TABLE IF NOT EXISTS `SCENARIO` "
                   "(`FLG_SCENARIO` int(11) NOT NULL DEFAULT '0') "
                   "ENGINE=InnoDB DEFAULT CHARSET=latin1;")
    cursor.close()
    odk_connection.commit()


def sample_coordinates(constraint=None):
    """Sample coordinates from area_polygon, possible constrained further by a constraint rectangle"""
    #The northern, southern, western, and eastern bounds of the area.
    nb = area_extent[1][0]
    wb = area_extent[0][1]
    sb = area_extent[0][0]
    eb = area_extent[1][1]
    if constraint is not None:
        #TODO: further restrict area (e.g. fw-specific)
        pass
    while True:
        lat = random.uniform(sb, nb)
        lon = random.uniform(wb, eb)
        if area_polygon.contains_point([lat, lon]):
            return str(lat) + ' ' + str(lon) + ' 0 0'


def create_first_name(sex):
    if sex == 'M':
        return random.choice(m_first_names)
    else:
        return random.choice(f_first_names)


def create_last_name():
    return random.choice(last_names)


def sample_age(min_age=None):
    if min_age is None:
        min_age = 0
    MAX_AGE = 100
    while True:
        age = random.expovariate(death_rate)
        if min_age <= age <= MAX_AGE:
            return age


def get_age_in_years(dob, date_of_visit):
    try:
        birthday = dob.replace(year=date_of_visit.year)
    except ValueError:
        birthday = dob.replace(year=date_of_visit.year, day=dob.day-1)
    if birthday > date_of_visit:
        return date_of_visit.year - dob.year - 1
    else:
        return date_of_visit.year - dob.year


def sample_gender():
    if random.random() < proportion_females:
        return 'F'
    else:
        return 'M'


def makes_mistake(event):
    """Does FW make event-specific mistake?"""
    if random.random() < site['fieldworker']['accuracy'][event]['rate']:
        if site['fieldworker']['accuracy'][event]['max'] > 0:
            site['fieldworker']['accuracy'][event]['max'] -= 1
            return True
    return False


def create_date(event_age, survey_date=None):
    """Return the date of an event that happen event_age (in years) before survey_date"""
    if survey_date is None:
        survey_date = datetime.date.now()
    try:
        return survey_date - datetime.timedelta(days=int(event_age * 365))
    except:
        # Must be 2/29!
        assert survey_date.month == 2 and survey_date.day == 29
        return survey_date.replace(month=2, day=28, year=survey_date.year - event_age)


def create_date_from_interval(start, end):
    start_date = datetime.datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.datetime.strptime(end, "%Y-%m-%d").date()
    return start_date + datetime.timedelta(days=random.randint(0, (end_date - start_date).days))


def create_start_end_time(date_of_visit):
    start_datetime = datetime.datetime.combine(date_of_visit, datetime.datetime.min.time())
    #TODO:  move hard coded values for times in seconds to config
    #start visit between 8am and 4pm
    start_datetime = start_datetime + datetime.timedelta(seconds=random.randint(0, 21600)+21599)
    #end visit within 60 minutes
    end_datetime = start_datetime + datetime.timedelta(seconds=random.randint(1, 3600))
    return start_datetime.strftime('%Y-%m-%dT%H:%M:%S.000+03'), end_datetime.strftime('%Y-%m-%dT%H:%M:%S.000+03')


def create_fws(fieldworker):
    """Create fieldworkers in openhds"""
    cursor = open_hds_connection.cursor()
    #first add a default fieldworker named Data Data, username data, for use in a the standard tablet emulator
    cursor.execute("INSERT INTO fieldworker (uuid, extid, firstname, lastname, deleted, passwordHash) VALUES "
                   "('{uu_id}','data', 'Data', 'Data', false,"
                   "'$2a$08$83Vl7c/z85s9vdmWLcQYOuflMxgVwdNnMQmDA77L5FvX7ao65vt0W')".format(uu_id=util.create_uuid()))
    cursor.execute("INSERT INTO fieldworker (uuid, extid, firstname, lastname, deleted, passwordHash) VALUES "
                   "('{uu_id}','data2', 'Data2', 'Data2', false,"
                   "'$2a$08$83Vl7c/z85s9vdmWLcQYOuflMxgVwdNnMQmDA77L5FvX7ao65vt0W')".format(uu_id=util.create_uuid()))
    number = fieldworker['number']
    for i in range(1, number + 1):
        first_name = create_first_name(sample_gender())
        last_name = create_last_name()
        #TODO: i is not what should be used according to the naming convention
        ext_id = 'FW' + first_name[0] + last_name[0] + str(i)
        cursor.execute("INSERT INTO fieldworker (uuid, extid, firstname, lastname, deleted, passwordHash) VALUES "
                       "('{uu_id}','{ext_id}', '{first_name}', '{last_name}', false, '$2a$08$83Vl7c/z85s9vdmWLcQYOuflMxgVwdNnMQmDA77L5FvX7ao65vt0W')"
                       .format(uu_id=util.create_uuid(), ext_id=ext_id, first_name=first_name, last_name=last_name))
        hdss['field_workers'].append({'ext_id': ext_id, 'center': sample_coordinates()})
    cursor.close()
    open_hds_connection.commit()

def create_location_hierarchy(location_hierarchy):
    """Create the location hierarchy"""
    cursor = open_hds_connection.cursor()
    for level in location_hierarchy['levels']:
        cursor.execute("INSERT INTO locationhierarchy VALUES ('{uuid}','{extId}','{name}','{level_uuid}',"
                       "'{parent_uuid}')".format(**level))
    cursor.close()
    open_hds_connection.commit()


def create_social_group(social_group_size, round_number, start_date, end_date, id_offset):
    date_of_visit = create_date_from_interval(start_date, end_date)
    field_worker = random.choice(hdss['field_workers'])
    cursor = open_hds_connection.cursor()
    #sample location on lowest level of location hierarchy
    area = util.query_db_one(cursor, "SELECT extId FROM locationhierarchy "
                                     "WHERE level_uuid = 'hierarchyLevelId5' ORDER BY RAND() LIMIT 1")['extId']
    #for now assume one location per social group
    location_index = len(hdss['social_groups']) + 1 + id_offset
    location_id = area + str(location_index).zfill(6)
    coordinates = sample_coordinates()
    visit_id = location_id + round_number.zfill(3)
    sg_id = location_id + '00'
    #first create the social group head
    id_of_head = location_id + '1'.zfill(3)
    last_name = create_last_name()
    gender_of_head = sample_gender()
    first_name = create_first_name(gender_of_head)
    middle_name = create_first_name(gender_of_head)
    start_time, end_time = create_start_end_time(date_of_visit)
    submission.submit_location_registration(start_time, area, field_worker['ext_id'], location_id, last_name,
                                            'Ten cell leader', 'RUR', coordinates,
                                            end_time, aggregate_url)
    start_time, end_time = create_start_end_time(date_of_visit)
    #migration date only for in_migrations. assume inmgration during this update round for now.
    date_of_migration = create_date_from_interval(start_date, str(date_of_visit))
    if round_number == '0':
        submission.submit_baseline_individual(start_time, end_time, location_id, visit_id, field_worker['ext_id'],
                                              id_of_head, 'UNK', 'UNK', first_name, middle_name, last_name,
                                              gender_of_head, str(create_date(sample_age(min_age_head_of_social_group),
                                                                              date_of_visit)),
                                              '1', str(date_of_visit), aggregate_url)
    else:
        submission.submit_in_migration(start_time, end_time, 'EXTERNAL_INMIGRATION', location_id, visit_id,
                                       field_worker['ext_id'],
                                       id_of_head, 'UNK', 'UNK', first_name, middle_name, last_name, gender_of_head,
                                       str(create_date(sample_age(min_age_head_of_social_group), date_of_migration)),
                                       '1', str(date_of_migration), aggregate_url)

    #create a social group
    start_time, end_time = create_start_end_time(date_of_visit)
    submission.submit_social_group_registration(start_time, sg_id, id_of_head, field_worker['ext_id'], last_name, "FAM",
                                                end_time, aggregate_url)
    social_group = {'sg_id': sg_id, 'individuals': [], 'locations': []}
    social_group['locations'].append({'location_id': location_id, 'coordinates': coordinates})
    social_group['individuals'].append({'ind_id': id_of_head, 'gender': gender_of_head, 'last_seen': date_of_visit,
                                        'status': 'present'})
    #and make the head a member
    start_time, end_time = create_start_end_time(date_of_visit)
    if round_number == '0':
        submission.submit_membership(start_time, id_of_head, sg_id, field_worker['ext_id'], '1', str(date_of_visit),
                                     end_time, aggregate_url)
    else:
        submission.submit_membership(start_time, id_of_head, sg_id, field_worker['ext_id'], '1', str(date_of_migration),
                                     end_time, aggregate_url)
    for i in range(2, social_group_size):
        ind_id = location_id + str(i).zfill(3)
        gender = sample_gender()
        first_name = create_first_name(gender)
        middle_name = create_first_name(gender)
        age = sample_age()
        start_time, end_time = create_start_end_time(date_of_visit)
        if round_number == '0':
            submission.submit_baseline_individual(start_time, end_time, location_id, visit_id, field_worker['ext_id'],
                                                  ind_id, 'UNK', 'UNK', first_name, middle_name, last_name, gender,
                                                  str(create_date(age, date_of_visit)),
                                                  '1', str(date_of_visit), aggregate_url)
            if makes_mistake('baseline'):
                submission.submit_baseline_individual(start_time, end_time, location_id, visit_id,
                                                      field_worker['ext_id'], ind_id, 'UNK', 'UNK', first_name,
                                                      middle_name, last_name, gender,
                                                      str(create_date(age, date_of_visit)),'1', str(date_of_visit),
                                                      aggregate_url)

        else:
            submission.submit_in_migration(start_time, end_time, 'EXTERNAL_INMIGRATION', location_id, visit_id,
                                           field_worker['ext_id'],
                                           ind_id, 'UNK', 'UNK', first_name, middle_name, last_name, gender,
                                           str(create_date(age, date_of_migration)),
                                           '1', str(date_of_migration), aggregate_url)

        #create memberships here, 2-9 for relationship
        start_time, end_time = create_start_end_time(date_of_visit)
        submission.submit_membership(start_time, ind_id, sg_id, field_worker['ext_id'], str(random.randint(2, 9)),
                                     str(date_of_visit), end_time, aggregate_url)
        social_group['individuals'].append({'ind_id': ind_id, 'gender': gender, 'last_seen': date_of_visit,
                                            'status': 'present'})
    #then another loop for relationship, use code 2 for marriages.
    #submission.submit_relationship()
    #TODO: for now, just take individual 2 and marry it to the household head (if opposite sexes and old enough)
        if i == 2 and gender != gender_of_head and age > min_age_marriage:
            start_time, end_time = create_start_end_time(date_of_visit)
            submission.submit_relationship(start_time, id_of_head, ind_id, field_worker['ext_id'], '2',
                                           str(date_of_visit), end_time, aggregate_url)
    return social_group


def simulate_baseline(round):
    """Simulate a census. Use the population size at start. Sample random locations.
    Use inmigration for all individuals.
    Don't fill a visit form."""
    global individuals_per_social_group
    popsize = 0
    while popsize < pop_size_baseline:
        social_group_size = np.random.poisson(individuals_per_social_group)
        social_group = create_social_group(social_group_size, str(round['roundNumber']), round['startDate'],
                                           round['endDate'], 0)
        hdss['social_groups'].append(social_group)
        popsize += social_group_size


def visit_social_group(social_group, round_number, start_date, end_date):
    date_of_visit = create_date_from_interval(start_date, end_date)
    field_worker = random.choice(hdss['field_workers'])
    #TODO: only one location per social group for now
    location_id = social_group['locations'][0]['location_id']
    visit_id = location_id + round_number.zfill(3)
    start_time, end_time = create_start_end_time(date_of_visit)
    submission.submit_visit_registration(start_time, visit_id, field_worker['ext_id'], location_id, round_number,
                                         str(date_of_visit), social_group['individuals'][0]['ind_id'], '1', '0',
                                         social_group['locations'][0]['coordinates'],
                                         end_time, aggregate_url)
    newly_inmigrated = []
    for individual in social_group['individuals']:
        #TODO: for now define death rate as per visit rate
        if individual['status'] == 'present' and random.random() < death_rate:
            start_time, end_time = create_start_end_time(date_of_visit)
            submission.submit_death_registration(start_time, individual['ind_id'], field_worker['ext_id'],
                                                 individual['gender'], '1', 'VILLAGE', '1', visit_id, 'CAUSE_OF_DEATH',
                                                 str(date_of_visit), 'OTHER', 'OTHERPLACE', end_time, aggregate_url)
            individual['status'] = 'dead'
            #TODO: dummy condition
            if "isheadofhousehold" == "True":
                submission.submit_death_of_hoh_registration(start_time, individual['ind_id'], "TODO_NEW_HOH",
                                                            field_worker['ext_id'], individual['gender'], '1',
                                                            'VILLAGE', '1', visit_id, 'CAUSE_OF_DEATH',
                                                            str(date_of_visit), 'OTHER', 'OTHERPLACE', end_time,
                                                            aggregate_url)
        #TODO: for now define outmigration rate as per visit rate
        if individual['status'] == 'present' and random.random() < outmigration_rate:
            start_time, end_time = create_start_end_time(date_of_visit)
            submission.submit_out_migration_registration(start_time, individual['ind_id'], field_worker['ext_id'],
                                                         visit_id, str(date_of_visit), 'DESTINATION', 'MARITAL_CHANGE',
                                                         'REC', end_time, aggregate_url)
            individual['status'] = 'outside_hdss'
        #half of the external inmigration events happen into social groups
        #TODO: for now assume all inmigrants are previously unknown
        if random.random() < inmigration_rate/2:
            next_id = int(social_group['individuals'][-1]['ind_id'][-3:]) + 1 + len(newly_inmigrated)
            ind_id = location_id + str(next_id).zfill(3)
            gender = sample_gender()
            first_name = create_first_name(gender)
            middle_name = create_first_name(gender)
            last_name = create_last_name()
            age = sample_age()
            date_of_migration = create_date_from_interval(start_date, str(date_of_visit))
            start_time, end_time = create_start_end_time(date_of_visit)
            submission.submit_in_migration(start_time, end_time, 'EXTERNAL_INMIGRATION', location_id, visit_id,
                                           field_worker['ext_id'], ind_id, 'UNK', 'UNK', first_name, middle_name,
                                           last_name, gender, str(create_date(age, date_of_visit)),
                                           '1', str(date_of_migration), aggregate_url)
            start_time, end_time = create_start_end_time(date_of_visit)
            submission.submit_membership(start_time, ind_id, social_group['sg_id'], field_worker['ext_id'],
                                         str(random.randint(2, 9)), str(date_of_migration), end_time, aggregate_url)
            newly_inmigrated.append({'ind_id': ind_id, 'gender': gender, 'last_seen': date_of_visit,
                                     'status': 'present'})
    social_group['individuals'].extend(newly_inmigrated)


def simulate_update(round):
    """Simulate an update round"""
    newly_inmigrated = []
    for social_group in hdss['social_groups']:
        if not 'no_update' in social_group:
            visit_social_group(social_group, str(round['roundNumber']), round['startDate'], round['endDate'])
            if random.random() < inmigration_rate/2:
                social_group_size = np.random.poisson(individuals_per_social_group)
                #social_group = create_social_group(social_group_size, str(round['roundNumber']), round['startDate'],
                #                                   round['endDate'], len(newly_inmigrated))
                #newly_inmigrated.append(social_group)
                #logging.debug(newly_inmigrated)
    #hdss['social_groups'].extend(newly_inmigrated)


def submit_fixed_events(household):
    household_id = household['householdId']
    forms = household['forms']
    for form in forms:
        submission.submit_from_dict(form, aggregate_url)
        social_group = next((item for item in hdss['social_groups'] if item['sg_id'] == household_id), None)
        #social_group = (item for item in hdss['social_groups'] if item['sg_id'] == household_id).next()
        if not social_group:
            social_group = {'sg_id': household_id, 'individuals': [], 'locations': [], 'no_update': True}
            hdss['social_groups'].append(social_group)
        if form['id'] == 'location_registration':
            location_id = form['fields'][3][1]
            location = {'location_id': location_id, 'coordinates': form['fields'][7][1]}
            print(social_group)
            social_group['locations'].append(location)
        if form['id'] == 'membership':
            individual_id = form['fields'][1][1]
            start_date = form['fields'][5][1]
            #TODO: properly deal with individuals
            social_group['individuals'].append({'ind_id': individual_id, 'gender': 'F', 'last_seen': start_date,
                                                'status': 'present'})
        if form['id'] == 'out_migration_registration' or form['id'] == 'death_registration':
            individual_id = form['fields'][1][1]
            individual = next((item for item in social_group['individuals'] if item['ind_id'] == individual_id), None)
            if form['id'] == 'out_migration_registration':
                individual['status'] = 'outside_hdss'
            if form['id'] == 'death_registration':
                individual['status'] = 'dead'


def simulate_round(round):
    """Simulate a baseline or update round. Discrete time simulation with daily time steps,
    assumes number of events >> number of days per round"""
    cursor = open_hds_connection.cursor()
    cursor.execute("INSERT INTO round VALUES ('{uuid}','{endDate}','{remarks}','{roundNumber}',"
                   "'{startDate}')".format(uuid=util.create_uuid(), **round))
    cursor = odk_connection.cursor()
    if round['remarks'] == 'Baseline':
        #enable mirth baseline channels
        cursor.execute("UPDATE SCENARIO SET FLG_SCENARIO=0")
        print("set 0")
    else:
        #enable mirth update channels
        cursor.execute("UPDATE SCENARIO SET FLG_SCENARIO=1")
        print("set 1")
    if 'fixedEvents' in round:
        for household in round['fixedEvents']:
            submit_fixed_events(household)
    if round['remarks'] == 'Baseline':
        simulate_baseline(round)
    else:
        simulate_update(round)


def simulate_inter_round(round):
    #wait for mirth to finish transferring data to openhds
    waiting_for_mirth = True
    while waiting_for_mirth:
        cursor = odk_connection.cursor()
        number_unprocessed = 0
        processed_flag = config['odk_server']['processed_by_mirth_flag']
        for odk_form in config['odk_server']['forms']:
            unprocessed = util.query_db_one(cursor, "SELECT COUNT(*) AS count FROM {odk_form} WHERE {processed} = 0"
                                            .format(odk_form=odk_form, processed=processed_flag))['count']
            if unprocessed > 0:
                print(odk_form + " unprocessed: " + str(unprocessed))
                number_unprocessed += unprocessed
        if number_unprocessed == 0:
            waiting_for_mirth = False
        else:
            print("Still waiting for Mirth...")
            time.sleep(3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--site', help='Json file with site description, located in conf dir', required=True)
    parser.add_argument('-d', '--debug', help='Debug logging', action='store_true', default=False)
    parser.set_defaults(truncate=False)
    args = parser.parse_args()
    init(args.site)
    if args.debug:
        logging.basicConfig(filename='sim.log', level=logging.DEBUG)
    else:
        logging.basicConfig(filename='sim.log', level=logging.WARN)
    for round in site['round']:
        pprint.pprint(round, width=1)
        simulate_round(round)
        simulate_inter_round(round)
    open_hds_connection.close()
    odk_connection.close()
    if 'pickle_out' in site['general']:
        with open(os.path.join(conf_dir, site['general']['pickle_out']), 'w') as site_file:
            pickle.dump(hdss, site_file)
    pprint.pprint(hdss, width=1)
    print("Done")
