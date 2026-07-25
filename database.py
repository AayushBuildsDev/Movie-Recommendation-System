import mysql.connector


def get_connection():
    return mysql.connector.connect(
        host="host.docker.internal",
        user="root",
        password="",
        database="movie_recommendation_system"
    )