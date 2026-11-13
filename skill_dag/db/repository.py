import pandas as pd


def fetch_skills(engine):
    return pd.read_sql("SELECT id, topic, sub_topic, skill FROM skills;", engine)


def fetch_prerequisites(engine):
    return pd.read_sql("SELECT skill_id, prerequisite_id, type FROM skill_prerequisites;", engine)
