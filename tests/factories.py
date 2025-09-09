from __future__ import annotations

from typing import Any

import factory
from faker import Faker

from src.models import (
    History,
    PatientState,
    PregnancyStatus,
    Recurrence,
    RedFlags,
    RenalFunction,
    Sex,
    Symptoms,
)

fake = Faker()


class SymptomsFactory(factory.Factory):
    class Meta:
        model = Symptoms

    dysuria = True
    urgency = factory.Faker("boolean", chance_of_getting_true=70)
    frequency = factory.Faker("boolean", chance_of_getting_true=60)
    suprapubic_pain = factory.Faker("boolean", chance_of_getting_true=50)
    hematuria = factory.Faker("boolean", chance_of_getting_true=30)
    gross_hematuria = False
    confusion = False
    delirium = False


class RedFlagsFactory(factory.Factory):
    class Meta:
        model = RedFlags

    fever = False
    rigors = False
    flank_pain = False
    back_pain = False
    nausea_vomiting = False
    systemic = False


class HistoryFactory(factory.Factory):
    class Meta:
        model = History

    antibiotics_last_90d = False
    allergies = factory.List([])
    meds = factory.List([])
    ACEI_ARB_use = False
    catheter = False
    stones = False
    immunocompromised = False
    neurogenic_bladder = False


class RecurrenceFactory(factory.Factory):
    class Meta:
        model = Recurrence

    relapse_within_4w = False
    recurrent_6m = False
    recurrent_12m = False


class PatientStateFactory(factory.Factory):
    class Meta:
        model = PatientState

    age = factory.Faker("random_int", min=18, max=65)
    sex = factory.Faker("random_element", elements=[Sex.female, Sex.male])
    pregnancy_status = factory.LazyAttribute(
        lambda obj: PregnancyStatus.not_applicable
        if obj.sex == Sex.male
        else fake.random_element(
            elements=[PregnancyStatus.not_pregnant, PregnancyStatus.unknown],
        ),
    )
    renal_function_summary = factory.Faker(
        "random_element", elements=[RenalFunction.normal, RenalFunction.impaired],
    )
    egfr_ml_min = None
    symptoms = factory.SubFactory(SymptomsFactory)
    red_flags = factory.SubFactory(RedFlagsFactory)
    history = factory.SubFactory(HistoryFactory)
    recurrence = factory.SubFactory(RecurrenceFactory)
    locale_code = "CA-ON"
    asymptomatic_bacteriuria = False


class SimpleUTIPatientFactory(PatientStateFactory):
    age = 25
    sex = Sex.female
    pregnancy_status = PregnancyStatus.not_pregnant
    renal_function_summary = RenalFunction.normal
    symptoms = factory.SubFactory(
        SymptomsFactory,
        dysuria=True,
        urgency=True,
        frequency=False,
        suprapubic_pain=False,
        hematuria=False,
    )
    red_flags = factory.SubFactory(RedFlagsFactory)
    history = factory.SubFactory(HistoryFactory)
    recurrence = factory.SubFactory(RecurrenceFactory)


class ComplicatedUTIPatientFactory(PatientStateFactory):
    age = 35
    sex = Sex.female
    pregnancy_status = PregnancyStatus.not_pregnant
    renal_function_summary = RenalFunction.normal
    symptoms = factory.SubFactory(
        SymptomsFactory, dysuria=True, urgency=True, frequency=True,
    )
    red_flags = factory.SubFactory(RedFlagsFactory, fever=True, rigors=True)
    history = factory.SubFactory(HistoryFactory)
    recurrence = factory.SubFactory(RecurrenceFactory)


class MaleUTIPatientFactory(PatientStateFactory):
    age = 45
    sex = Sex.male
    pregnancy_status = PregnancyStatus.not_applicable
    renal_function_summary = RenalFunction.normal
    symptoms = factory.SubFactory(
        SymptomsFactory, dysuria=True, urgency=True, suprapubic_pain=True,
    )
    red_flags = factory.SubFactory(RedFlagsFactory)
    history = factory.SubFactory(HistoryFactory)
    recurrence = factory.SubFactory(RecurrenceFactory)


class RecurrentUTIPatientFactory(PatientStateFactory):
    age = 30
    sex = Sex.female
    pregnancy_status = PregnancyStatus.not_pregnant
    renal_function_summary = RenalFunction.normal  # Fix to avoid complication
    symptoms = factory.SubFactory(
        SymptomsFactory, dysuria=True, urgency=True, frequency=True,
    )
    red_flags = factory.SubFactory(RedFlagsFactory)  # All False by default
    history = factory.SubFactory(HistoryFactory)  # All False by default
    recurrence = factory.SubFactory(RecurrenceFactory, recurrent_6m=True)


class ElderlyUTIPatientFactory(PatientStateFactory):
    age = 75
    sex = Sex.female
    pregnancy_status = PregnancyStatus.not_applicable
    renal_function_summary = RenalFunction.impaired
    egfr_ml_min = 25.0
    symptoms = factory.SubFactory(
        SymptomsFactory, dysuria=True, urgency=True, frequency=True,
    )
    history = factory.SubFactory(
        HistoryFactory, meds=["lisinopril", "hydrochlorothiazide"], ACEI_ARB_use=True,
    )


class PatientWithAllergiesFactory(PatientStateFactory):
    age = 28
    sex = Sex.female
    pregnancy_status = PregnancyStatus.not_pregnant
    symptoms = factory.SubFactory(
        SymptomsFactory, dysuria=True, frequency=True, suprapubic_pain=True,
    )
    history = factory.SubFactory(
        HistoryFactory, allergies=["nitrofurantoin", "trimethoprim"],
    )


class AsymptomaticBacteruriaPatientFactory(PatientStateFactory):
    age = 65
    sex = Sex.female
    pregnancy_status = PregnancyStatus.not_applicable
    symptoms = factory.SubFactory(
        SymptomsFactory,
        dysuria=False,
        urgency=False,
        frequency=False,
        suprapubic_pain=False,
        hematuria=False,
    )
    asymptomatic_bacteriuria = True


class InsufficientSymptomsPatientFactory(PatientStateFactory):
    age = 30
    sex = Sex.female
    pregnancy_status = PregnancyStatus.not_pregnant
    symptoms = factory.SubFactory(
        SymptomsFactory,
        dysuria=False,
        urgency=True,
        frequency=False,
        suprapubic_pain=False,
        hematuria=False,
    )


class PregnantPatientFactory(PatientStateFactory):
    age = 28
    sex = Sex.female
    pregnancy_status = PregnancyStatus.pregnant
    symptoms = factory.SubFactory(
        SymptomsFactory, dysuria=True, urgency=True, frequency=True,
    )


class PediatricPatientFactory(PatientStateFactory):
    age = 10
    sex = Sex.female
    pregnancy_status = PregnancyStatus.not_applicable
    symptoms = factory.SubFactory(SymptomsFactory, dysuria=True, urgency=True)


def create_patient_dict(patient: PatientState) -> dict[str, Any]:
    """Convert PatientState to dictionary format expected by services"""
    return {
        "age": patient.age,
        "sex": patient.sex.value,
        "pregnancy_status": patient.pregnancy_status.value,
        "renal_function_summary": patient.renal_function_summary.value,
        "egfr_ml_min": patient.egfr_ml_min,
        "symptoms": {
            "dysuria": patient.symptoms.dysuria,
            "urgency": patient.symptoms.urgency,
            "frequency": patient.symptoms.frequency,
            "suprapubic_pain": patient.symptoms.suprapubic_pain,
            "hematuria": patient.symptoms.hematuria,
            "gross_hematuria": patient.symptoms.gross_hematuria,
            "confusion": patient.symptoms.confusion,
            "delirium": patient.symptoms.delirium,
        },
        "red_flags": {
            "fever": patient.red_flags.fever,
            "rigors": patient.red_flags.rigors,
            "flank_pain": patient.red_flags.flank_pain,
            "back_pain": patient.red_flags.back_pain,
            "nausea_vomiting": patient.red_flags.nausea_vomiting,
            "systemic": patient.red_flags.systemic,
        },
        "history": {
            "antibiotics_last_90d": patient.history.antibiotics_last_90d,
            "allergies": patient.history.allergies,
            "meds": patient.history.meds,
            "ACEI_ARB_use": patient.history.ACEI_ARB_use,
            "catheter": patient.history.catheter,
            "stones": patient.history.stones,
            "immunocompromised": patient.history.immunocompromised,
            "neurogenic_bladder": patient.history.neurogenic_bladder,
        },
        "recurrence": {
            "relapse_within_4w": patient.recurrence.relapse_within_4w,
            "recurrent_6m": patient.recurrence.recurrent_6m,
            "recurrent_12m": patient.recurrence.recurrent_12m,
        },
        "locale_code": patient.locale_code,
        "asymptomatic_bacteriuria": patient.asymptomatic_bacteriuria,
    }
