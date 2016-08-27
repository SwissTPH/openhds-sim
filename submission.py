#!/usr/bin/env python

"""Test form submission"""

__email__ = "nicolas.maire@unibas.ch"
__status__ = "Alpha"

from lxml import etree
import urllib2
import uuid
import logging

DEVICE_ID = "8d:77:12:5b:c1:3c"


def submit_data(data, url):
    """Submit an instance to ODKAggregate"""
    r = urllib2.Request(url, data=data, headers={'Content-Type': 'application/xml'})
    try:
        u = urllib2.urlopen(r)
        response = u.read()
        return response
    except urllib2.HTTPError as e:
        print(e.read())
        print(e.code)
        print(e.info())
        print(data)


def submit_from_instance_file(filename, aggregate_url):
    """Read an instance from a file and submit to ODKAggregate"""
    f = open(filename, 'r')
    data = f.read()
    f.close()
    submit_data(data, aggregate_url)


def submit_from_dict(form_dict, aggregate_url):
    """Create an instance from a dict and submit to ODKAggregate"""
    root = etree.Element(form_dict["id"], id=form_dict["id"])
    #TODO: deviceid should be added here, but what spelling , Id or id?
    dev_id = etree.SubElement(root, "deviceid")
    dev_id.text = DEVICE_ID
    meta = etree.SubElement(root, "meta")
    inst_id = etree.SubElement(meta, "instanceID")
    inst_id.text = str(uuid.uuid1())
    p_b_m = etree.SubElement(root, "processedByMirth")
    p_b_m.text = '0'
    etree.SubElement(root, "start")
    for field in form_dict["fields"]:
        if type(field[1]) == list:
            el_par = etree.SubElement(root, field[0])
            for sub_field in field[1]:
                el = etree.SubElement(el_par, sub_field[0])
                el.text = sub_field[1]
        else:
            el = etree.SubElement(root, field[0])
            el.text = field[1]
    logging.debug(form_dict)
    submit_data(etree.tostring(root), aggregate_url)


def submit_baseline_individual(start, end, location_id, visit_id, fieldworker_id, individual_id, mother_id, father_id,
                               first_name, middle_name, last_name, gender, date_of_birth, partial_date,
                               date_of_visit, aggregate_url):
    """Register an individual during baseline"""
    # dateOfMigration is date of  visit by definition
    form_dict = {"id": "baseline",
                 "fields": [["start", start], ["end", end],
                            ["openhds", [["migrationType", "BASELINE"], ["locationId", location_id],
                                         ["visitId", visit_id], ["fieldWorkerId", fieldworker_id]]],
                            ["individualInfo", [["individualId", individual_id], ["motherId", mother_id],
                                                ["fatherId", father_id], ["firstName", first_name],
                                                ["middleName", middle_name], ["lastName", last_name],
                                                ["gender", gender], ["dateOfBirth", date_of_birth],
                                                ["partialDate", partial_date]]],
                            ["dateOfMigration", date_of_visit], ["warning", ""], ["visitDate", date_of_visit],
                            ["majo4mo", "yes"], ["spelasni", "yes"]]}
    return submit_from_dict(form_dict, aggregate_url)


def submit_in_migration(start, end, migration_type, location_id, visit_id, fieldworker_id, individual_id, mother_id,
                        father_id, first_name, middle_name, last_name, gender, date_of_birth, partial_date,
                        date_of_migration, aggregate_url):
    """Register an inmigration"""
    form_dict = {"id": "in_migration",
                 "fields": [["start", start], ["end", end],
                            ["openhds", [["visitId", visit_id], ["fieldWorkerId", fieldworker_id],
                                        ["migrationType", migration_type], ["locationId", location_id]]],
                            ["individualInfo", [["individualId", individual_id], ["motherId", mother_id],
                                                ["fatherId", father_id], ["firstName", first_name],
                                                ["middleName", middle_name], ["lastName", last_name],
                                                ["gender", gender], ["dateOfBirth", date_of_birth],
                                                ["partialDate", partial_date]]],
                            ["dateOfMigration", date_of_migration], ["warning", ""], ["origin", "other"],
                            ["reason", "NA"], ["maritalChange", "NA"], ["reasonOther", "NA"], ["movedfrom", "NA"],
                            ["shortorlongstay", "NA"]]}
    return submit_from_dict(form_dict, aggregate_url)


def submit_death_registration(start, individual_id, first_name, last_name, field_worker_id, visit_id, date_of_death,
                              place_of_death, place_of_death_other, end, aggregate_url):
    form_dict = {"id": "death_registration",
                 "fields": [["start", start], ["end", end],
                            ["openhds", [["fieldWorkerId", field_worker_id], ["visitId", visit_id],
                                         ["individualId", individual_id], ["firstName", first_name],
                                         ["lastName", last_name]]],
                            ["dateOfDeath", date_of_death], ["diagnoseddeath", ''], ["whom", ''],
                            ["causeofdeathdiagnosed", ''], ["causofdeathnotdiagnosed", ''],
                            ["placeOfDeath", place_of_death], ["placeOfDeathOther", place_of_death_other],
                            ["causeOfDeath", '']
                            ]}
    return submit_from_dict(form_dict, aggregate_url)


def submit_death_of_hoh_registration(start, individual_id, household_id, new_hoh_id, field_worker_id, gender, death_within_dss,
                                     death_village, have_death_certificate, visit_id, cause_of_death, date_of_death,
                                     place_of_death, place_of_death_other, end, aggregate_url):
    #TODO: update form fields to lastest
    form_dict = {"id": "DEATHTOHOH",
                 "fields": [["start", start], ["end", end],
                            ["openhds", [["visitId", visit_id], ["fieldWorkerId", field_worker_id],
                                         ["householdId", household_id], ["individualId", individual_id],
                                         ["firstName", "first"], ["lastName", "last"], ["new_hoh_id", new_hoh_id]]],
                            ["gender", gender], ["deathWithinDSS", death_within_dss], ["deathVillage", death_village],
                            ["haveDeathCertificate", have_death_certificate],
                            ["causeOfDeath", cause_of_death], ["dateOfDeath", date_of_death],
                            ["placeOfDeath", place_of_death], ["placeOfDeathOther", place_of_death_other],
                            ]}
    return submit_from_dict(form_dict, aggregate_url)


def submit_location_registration(start, hierarchy_id, fieldworker_id, location_id, location_name, ten_cell_leader,
                                 location_type, geopoint, end, aggregate_url):
    form_dict = {"id": "location_registration",
                 "fields": [["start", start], ["end", end],
                            ["openhds", [["fieldWorkerId", fieldworker_id], ["hierarchyId", hierarchy_id],
                            ["locationId", location_id]]],
                            ["locationName", location_name], ["tenCellLeader", ten_cell_leader],
                            ["locationType", location_type], ["geopoint", geopoint]]}
    return submit_from_dict(form_dict, aggregate_url)


def submit_membership(start, individual_id, household_id, fieldworker_id, relationship_to_group_head, start_date, end,
                      aggregate_url):
    form_dict = {"id": "membership",
                 "fields": [["start", start], ["end", end],
                            ["openhds", [["householdId", household_id], ["fieldWorkerId", fieldworker_id],
                                         ["individualId", individual_id]]],
                            ["relationshipToGroupHead", relationship_to_group_head],
                            ["startDate", start_date]]}
    return submit_from_dict(form_dict, aggregate_url)


def submit_out_migration_registration(start, individual_id, fieldworker_id, visit_id, first_name, last_name,
                                      date_of_migration, name_of_destination, reason_for_out_migration, marital_change,
                                      end, aggregate_url):
    form_dict = {"id": "out_migration_registration",
                 "fields": [["start", start], ["end", end],
                            ["openhds", [["individualId", individual_id], ["fieldWorkerId", fieldworker_id],
                            ["visitId", visit_id], ["firstName", first_name], ["lastName", last_name]]],
                            ["dateOfMigration", date_of_migration], ["nameOfDestination", name_of_destination],
                            ["reasonForOutMigration", reason_for_out_migration], ["maritalChange", marital_change]]}
    return submit_from_dict(form_dict, aggregate_url)


def submit_pregnancy_observation(start, estimated_age_of_preg, preg_notes, age_of_preg_from_notes,
                                 last_period_from_notes, has_anc_clinic_visit, pregnancy_number, have_mosquito_net,
                                 slept_under_mosquito_net, treated_net, months_or_years, month_since_last_net_treatment,
                                 source_of_net, relationship_of_respondent_to_expectant, individual_id, fieldworker_id,
                                 visit_id, exptected_delivery_date, recorded_date, end, aggregate_url):
    form_dict = {"id": "pregnancy_observation",
                 "fields": [["start", start], ["end", end],
                            ["openhds", [["fieldWorkerId", fieldworker_id], ["visitId", visit_id],
                                         ["individualId", individual_id], ["recordedDate", recorded_date]]],
                            ["estimatedAgeOfPreg", estimated_age_of_preg], ["pregNotes", preg_notes],
                            ["ageOfPregFromPregNotes", age_of_preg_from_notes],
                            ["lastPeriodFromPregNotes", last_period_from_notes],
                            ["hasANCClinicVisit", has_anc_clinic_visit],
                            ["pregnancyNumber", pregnancy_number], ["haveMosquitoNet", have_mosquito_net],
                            ["sleptUnderMosquitoNet", slept_under_mosquito_net], ["treatedNet", treated_net],
                            ["monthsOrYears", months_or_years],
                            ["monthsSinceLastNetTreatment", month_since_last_net_treatment],
                            ["sourceOfNet", source_of_net],
                            ["relationshipOfRespondentToExpectantMother", relationship_of_respondent_to_expectant],
                            ["expectedDeliveryDate", exptected_delivery_date]]}
    return submit_from_dict(form_dict, aggregate_url)


def submit_pregnancy_outcome(start, mother_id, father_id, visit_id, fieldworker_id, nboutcomes, partial_date,
                             birthingplace, birthing_assistant, hours_or_days_in_hospital, hours_in_hospital,
                             caesarian_or_natural, total_number_children_still_living, attended_anc,
                             number_of_attendances, recorded_date, end, aggregate_url):
    form_dict = {"id": "pregnancy_outcome",
                 "fields": [["start", start], ["end", end],
                            ["openhds", [["visitId", visit_id], ["fieldWorkerId", fieldworker_id],
                                         ["motherId", mother_id], ["fatherId", father_id]]],
                            ["nboutcomes", nboutcomes], ["partialDate", partial_date], ["birthingPlace", birthingplace],
                            ["birthingAssistant", birthing_assistant],
                            ["hoursOrDaysInHospital", hours_or_days_in_hospital],
                            ["hoursInHospital", hours_in_hospital], ["caesarianOrNatural", caesarian_or_natural],
                            ["totalNumberChildrenStillLiving", total_number_children_still_living],
                            ["attendedANC", attended_anc], ["numberOfANCAttendances", number_of_attendances],
                            ["recordedDate", recorded_date]]}
    return submit_from_dict(form_dict, aggregate_url)


def submit_relationship(start, individual_a, individual_b, fieldworker_id, relationship_type, start_date, end,
                        aggregate_url):
    form_dict = {"id": "relationship",
                 "fields": [["start", start], ["end", end],
                            ["openhds", [["fieldWorkerId", fieldworker_id], ["individualA", individual_a],
                                         ["individualB", individual_b]]],
                            ["relationshipType", relationship_type], ["startDate", start_date]]}
    return submit_from_dict(form_dict, aggregate_url)


def submit_social_group_registration(start, household_id, individual_id, field_worker_id, group_name, social_group_type,
                                     end, aggregate_url):
    form_dict = {"id": "social_group_registration",
                 "fields": [["start", start], ["end", end],
                            ["openhds", [["fieldWorkerId", field_worker_id], ["householdId", household_id],
                                         ["individualId", individual_id]]],
                                         ["groupName", group_name], ["socialGroupType", social_group_type]]}
    return submit_from_dict(form_dict, aggregate_url)


def submit_visit_registration(start, visit_id, field_worker_id, location_id, round_number, visit_date, interviewee_id,
                              correct_interviewee, farmhouse, coordinates, end, aggregate_url):
    form_dict = {"id": "visit_registration",
                 "fields": [["start", start], ["end", end],
                            ["openhds", [["visitId", visit_id], ["fieldWorkerId", field_worker_id],
                            ["locationId", location_id], ["roundNumber", round_number]]],
                            ["visitDate", visit_date], ["intervieweeId", interviewee_id],
                            ["correctInterviewee", correct_interviewee], ["realVisit", "1"],
                            ["farmhouse", farmhouse], ["coordinates", coordinates]]}
    return submit_from_dict(form_dict, aggregate_url)
