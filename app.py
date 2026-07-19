from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection
import json
import requests

app = Flask(__name__)

app.secret_key = "movie_recommendation_secret_key"
TMDB_API_KEY = "dd2e4579550b341158b2ee75ee32c5a9"

import requests

def get_movie_poster(movie_id):

    url = f"https://api.themoviedb.org/3/movie/{movie_id}"

    params = {
        "api_key": TMDB_API_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:

            data = response.json()

            poster_path = data.get("poster_path")

            if poster_path:
                return "https://image.tmdb.org/t/p/w500" + poster_path

    except requests.exceptions.RequestException as e:
        print("TMDB Error:", e)

    return None

# -------------------- Home Page -------------------- #

@app.route("/")
def home():

    search = request.args.get("search")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if search:

        query = """
        SELECT id, title, release_date, vote_average, overview
        FROM tmdb_5000_movies
        WHERE title LIKE %s
        ORDER BY title;
        """

        cursor.execute(query, ("%" + search + "%",))

    else:

        query = """
        SELECT id, title, release_date, vote_average, overview
        FROM tmdb_5000_movies
        ORDER BY id DESC
        LIMIT 12;
        """

        cursor.execute(query)

    movies = cursor.fetchall()
    for movie in movies:
        movie["poster"] = get_movie_poster(movie["id"])

    cursor.close()
    conn.close()

    return render_template("home.html", movies=movies)


# -------------------- Genre Filter -------------------- #

@app.route("/genre/<genre_name>")
def genre_movies(genre_name):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT id, title, release_date, vote_average, overview
    FROM tmdb_5000_movies
    WHERE genres LIKE %s
    ORDER BY title;
    """

    cursor.execute(query, ("%" + genre_name + "%",))

    movies = cursor.fetchall()

    for movie in movies:
        movie["poster"] = get_movie_poster(movie["id"])

    cursor.close()
    conn.close()

    return render_template("home.html", movies=movies)


# -------------------- Movie Details -------------------- #
@app.route("/movie/<int:movie_id>")
def movie_details(movie_id):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT
        id,
        title,
        genres,
        overview,
        release_date,
        vote_average,
        vote_count,
        popularity,
        tagline,
        homepage
    FROM tmdb_5000_movies
    WHERE id=%s;
    """

    cursor.execute(query, (movie_id,))

    movie = cursor.fetchone()

    if movie:

        # Get movie poster
        movie["poster"] = get_movie_poster(movie["id"])

        # Convert genres JSON to text
        genres = json.loads(movie["genres"])
        movie["genres"] = ", ".join(
            genre["name"] for genre in genres
        )

        # First genre for recommendations
        first_genre = genres[0]["name"]

        query = """
        SELECT
            id,
            title,
            vote_average
        FROM tmdb_5000_movies
        WHERE genres LIKE %s
        AND id != %s
        LIMIT 6;
        """

        cursor.execute(
            query,
            ("%" + first_genre + "%", movie_id)
        )

        recommended_movies = cursor.fetchall()

        # Add posters to recommended movies
        for rec in recommended_movies:
            rec["poster"] = get_movie_poster(rec["id"])

        # Get average user rating
        cursor.execute("""
            SELECT ROUND(AVG(rating),1) AS user_rating
            FROM rating_table
            WHERE movie_id=%s
        """, (movie_id,))

        rating = cursor.fetchone()

        if rating:
            movie["user_rating"] = rating["user_rating"]

    else:

        recommended_movies = []

    cursor.close()
    conn.close()

    return render_template(
        "movie_details.html",
        movie=movie,
        recommended_movies=recommended_movies
    )

# -------------------- Add Movie -------------------- #

@app.route("/add_movie")
def add_movie():

    if "user_id" not in session:
        flash("Please login first.", "danger")
        return redirect("/login")

    if session["role"] != "admin":
        flash("Access denied. Admin only.", "danger")
        return redirect("/dashboard")

    return render_template("add_movie.html")


# -------------------- Edit Movie -------------------- #

@app.route("/edit_movie/<int:movie_id>")
def edit_movie(movie_id):

    if "user_id" not in session:
        flash("Please login first.", "danger")
        return redirect("/login")

    if session["role"] != "admin":
        flash("Access denied. Admin only.", "danger")
        return redirect("/dashboard")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT
        id,
        title,
        genres,
        overview,
        release_date,
        vote_average
    FROM tmdb_5000_movies
    WHERE id=%s;
    """

    cursor.execute(query, (movie_id,))

    movie = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("edit_movie.html", movie=movie)


# -------------------- Delete Movie -------------------- #

@app.route("/delete_movie/<int:movie_id>")
def delete_movie(movie_id):

    if "user_id" not in session:
        flash("Please login first.", "danger")
        return redirect("/login")

    if session["role"] != "admin":
        flash("Access denied. Admin only.", "danger")
        return redirect("/dashboard")

    conn = get_connection()
    cursor = conn.cursor()

    query = """
    DELETE FROM tmdb_5000_movies
    WHERE id=%s;
    """

    cursor.execute(query, (movie_id,))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect("/admin")

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        # Check Password
        if password != confirm_password:

            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Check Email
        query = """
        SELECT *
        FROM `user table`
        WHERE email=%s;
        """

        cursor.execute(query, (email,))
        user = cursor.fetchone()

        if user:

            cursor.close()
            conn.close()

            flash("Email already registered.", "danger")
            return render_template("register.html")

        # Hash Password
        hashed_password = generate_password_hash(password)

        # Insert User
        query = """
        INSERT INTO `user table`
        (username, email, password)
        VALUES
        (%s, %s, %s);
        """

        cursor.execute(query, (username, email, hashed_password))

        conn.commit()

        cursor.close()
        conn.close()

        flash("Registration Successful. Please Login.", "success")

        return redirect("/login")

    return render_template("register.html")

# -------------------- Login -------------------- #

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT *
        FROM `user table`
        WHERE email=%s;
        """

        cursor.execute(query, (email,))

        user = cursor.fetchone()

        cursor.close()
        conn.close()

        # Check user and password
        if user and check_password_hash(user["password"], password):

            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            flash("Login Successful.", "success")

            return redirect("/dashboard")

        else:

            flash("Invalid Email or Password.", "danger")

            return render_template("login.html")

    return render_template("login.html")


# -------------------- Dashboard -------------------- #

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        flash("Please login first.", "danger")
        return redirect("/login")

    return render_template("dashboard.html")


# -------------------- Logout -------------------- #

@app.route("/logout")
def logout():

    session.clear()

    flash("Logged out successfully.", "success")

    return redirect("/login")

@app.route("/rate_movie/<int:movie_id>", methods=["POST"])
def rate_movie(movie_id):

    if "user_id" not in session:
        flash("Please login first.", "danger")
        return redirect("/login")

    user_id = session["user_id"]
    rating = request.form["rating"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM rating_table
        WHERE user_id=%s AND movie_id=%s
    """, (user_id, movie_id))

    existing = cursor.fetchone()

    if existing:

        cursor.execute("""
            UPDATE rating_table
            SET rating=%s
            WHERE user_id=%s AND movie_id=%s
        """, (rating, user_id, movie_id))

        flash("Rating Updated Successfully.", "success")

    else:

        cursor.execute("""
            INSERT INTO rating_table(user_id,movie_id,rating)
            VALUES(%s,%s,%s)
        """, (user_id, movie_id, rating))

        flash("Rating Submitted Successfully.", "success")

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(f"/movie/{movie_id}")

@app.route("/admin")
def admin():

    if "user_id" not in session:
        flash("Please login first.", "danger")
        return redirect("/login")

    if session.get("role") != "admin":
        flash("Access denied. Admin only.", "danger")
        return redirect("/dashboard")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT
        id,
        title,
        genres,
        release_date,
        vote_average
    FROM tmdb_5000_movies
    ORDER BY id DESC;
    """

    cursor.execute(query)

    movies = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin.html", movies=movies)
# -------------------- Run Flask -------------------- #

if __name__ == "__main__":
    app.run(debug=True)