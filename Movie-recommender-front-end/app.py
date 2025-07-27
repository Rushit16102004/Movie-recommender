import pickle
import pandas as pd
import streamlit as st
import requests
from requests.exceptions import RequestException
import sqlite3
from datetime import datetime
import numpy as np

# --- 1. Database Setup and User Management ---
conn = sqlite3.connect('user_profiles.db')
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   username TEXT UNIQUE,
                   password TEXT,
                   created_at TIMESTAMP)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS user_watchlist
                  (user_id INTEGER,
                   movie_id INTEGER,
                   movie_title TEXT,
                   PRIMARY KEY (user_id, movie_id),
                   FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS movie_ratings
                  (user_id INTEGER,
                   movie_id INTEGER,
                   rating INTEGER, -- 1 to 5 stars
                   timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                   PRIMARY KEY (user_id, movie_id),
                   FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS movie_reviews
                  (review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   user_id INTEGER,
                   movie_id INTEGER,
                   review_text TEXT,
                   timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                   FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS movie_comments
                  (comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   user_id INTEGER,
                   movie_id INTEGER,
                   comment_text TEXT,
                   timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                   FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE)''')

conn.commit()


def create_user(username, password):
    try:
        cursor.execute("INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
                       (username, password, datetime.now()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def verify_user(username, password):
    cursor.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
    return cursor.fetchone()


def get_username_by_id(user_id):
    cursor.execute("SELECT username FROM users WHERE id=?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else "Guest"


# --- Watchlist Functions ---
def add_to_watchlist(user_id, movie_id, movie_title):
    try:
        movie_id = int(movie_id)
        cursor.execute("INSERT INTO user_watchlist (user_id, movie_id, movie_title) VALUES (?, ?, ?)",
                       (user_id, movie_id, movie_title))
        conn.commit()
        st.toast(f"'{movie_title}' added to watchlist!")
        return True
    except sqlite3.IntegrityError:
        st.toast(f"'{movie_title}' is already in your watchlist.")
        return False
    except sqlite3.Error as e:
        st.error(f"Database error adding to watchlist: {e}")
        conn.rollback()
        return False


def remove_from_watchlist(user_id, movie_id):
    try:
        movie_id = int(movie_id)
        cursor.execute("DELETE FROM user_watchlist WHERE user_id=? AND movie_id=?", (user_id, movie_id))
        conn.commit()
        st.toast("Removed from watchlist.")
    except sqlite3.Error as e:
        st.error(f"Database error removing from watchlist: {e}")
        conn.rollback()


def is_movie_in_watchlist(user_id, movie_id):
    try:
        movie_id = int(movie_id)
        cursor.execute("SELECT 1 FROM user_watchlist WHERE user_id=? AND movie_id=?", (user_id, movie_id))
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        st.error(f"Database error checking watchlist: {e}")
        return False


def get_watchlist_movies(user_id):
    try:
        cursor.execute("SELECT movie_id, movie_title FROM user_watchlist WHERE user_id=?", (user_id,))
        return [(int(row[0]), row[1]) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        st.error(f"Database error getting watchlist: {e}")
        return []
    except Exception as e:
        st.error(f"An unexpected error occurred while processing watchlist movies: {e}")
        return []


# --- Rating Functions ---
def add_movie_rating(user_id, movie_id, rating):
    try:
        movie_id = int(movie_id)
        cursor.execute("INSERT OR REPLACE INTO movie_ratings (user_id, movie_id, rating) VALUES (?, ?, ?)",
                       (user_id, movie_id, rating))
        conn.commit()
        st.toast(f"Your rating ({rating} stars) saved!")
    except sqlite3.Error as e:
        st.error(f"Database error saving rating: {e}")
        conn.rollback()

def get_user_movie_rating(user_id, movie_id):
    try:
        movie_id = int(movie_id)
        cursor.execute("SELECT rating FROM movie_ratings WHERE user_id=? AND movie_id=?", (user_id, movie_id))
        result = cursor.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        st.error(f"Database error getting user rating: {e}")
        return None

def get_average_movie_rating(movie_id):
    try:
        movie_id = int(movie_id)
        cursor.execute("SELECT AVG(rating), COUNT(rating) FROM movie_ratings WHERE movie_id=?", (movie_id,))
        result = cursor.fetchone()
        avg_rating = round(result[0], 1) if result[0] else None
        num_ratings = result[1] if result[1] else 0
        return avg_rating, num_ratings
    except sqlite3.Error as e:
        st.error(f"Database error calculating average rating: {e}")
        return None, 0


# --- Review Functions ---
def add_movie_review(user_id, movie_id, review_text):
    try:
        movie_id = int(movie_id)
        cursor.execute("INSERT INTO movie_reviews (user_id, movie_id, review_text) VALUES (?, ?, ?)",
                       (user_id, movie_id, review_text))
        conn.commit()
        st.toast("Your review has been submitted!")
    except sqlite3.Error as e:
        st.error(f"Database error submitting review: {e}")
        conn.rollback()

def get_movie_reviews(movie_id):
    try:
        movie_id = int(movie_id)
        cursor.execute("""
            SELECT mr.review_text, u.username, mr.timestamp
            FROM movie_reviews mr
            JOIN users u ON mr.user_id = u.id
            WHERE mr.movie_id = ?
            ORDER BY mr.timestamp DESC
        """, (movie_id,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        st.error(f"Database error getting reviews: {e}")
        return []


# --- Comment Functions ---
def add_movie_comment(user_id, movie_id, comment_text):
    try:
        movie_id = int(movie_id)
        cursor.execute("INSERT INTO movie_comments (user_id, movie_id, comment_text) VALUES (?, ?, ?)",
                       (user_id, movie_id, comment_text))
        conn.commit()
        st.toast("Your comment has been posted!")
    except sqlite3.Error as e:
        st.error(f"Database error posting comment: {e}")
        conn.rollback()

def get_movie_comments(movie_id):
    try:
        movie_id = int(movie_id)
        cursor.execute("""
            SELECT mc.comment_text, u.username, mc.timestamp
            FROM movie_comments mc
            JOIN users u ON mc.user_id = u.id
            WHERE mc.movie_id = ?
            ORDER BY mc.timestamp DESC
        """, (movie_id,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        st.error(f"Database error getting comments: {e}")
        return []


# --- 2. API and Recommendation Logic ---
@st.cache_data
def fetch_poster(movie_id):
    try:
        movie_id = int(movie_id)
        response = requests.get(
            f'https://api.themoviedb.org/3/movie/{movie_id}?api_key=5a0f912e8b0ae43f239e2346fda7634f&language=en-us',
            timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get('poster_path'):
            return "https://image.tmdb.org/t/p/w500" + data['poster_path']
        return "https://via.placeholder.com/150?text=No+Poster"
    except RequestException:
        return "https://via.placeholder.com/150?text=Error"
    except ValueError:
        return "https://via.placeholder.com/150?text=Invalid+ID"


@st.cache_data
def recommend(movie_title):
    if movie_title not in movies['title'].values:
        st.error(f"Error: Movie '{movie_title}' not found in the dataset for recommendation.")
        return [], [], []

    try:
        movie_index = movies[movies['title'] == movie_title].index[0]
        if movie_index >= similarity.shape[0] or movie_index >= similarity.shape[1]:
            st.error(f"Error: Similarity data malformed for index {movie_index}. Cannot recommend.")
            return [], [], []

        distances = similarity[movie_index]
        similar_movies = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:7]

        recommended_names = []
        recommended_posters = []
        recommended_ids = []

        for idx, _ in similar_movies:
            if idx < len(movies):
                rec_movie = movies.iloc[idx]
                recommended_names.append(rec_movie.title)
                recommended_posters.append(fetch_poster(int(rec_movie.id)))
                recommended_ids.append(int(rec_movie.id))
            else:
                st.warning(f"Warning: Recommended movie index {idx} out of bounds.")

        return recommended_names, recommended_posters, recommended_ids
    except IndexError:
        st.error(f"Internal Error: Movie '{movie_title}' index not found. Data inconsistency.")
        return [], [], []
    except Exception as e:
        st.error(f"An unexpected error occurred during recommendation: {str(e)}")
        return [], [], []


# --- 3. Data Loading ---
try:
    movies_data = pickle.load(open("movie_dick.pkl", 'rb'))
    movies = pd.DataFrame(movies_data)
    similarity = pickle.load(open("similarity.pkl", 'rb'))

    if not isinstance(movies, pd.DataFrame) or 'title' not in movies.columns or 'id' not in movies.columns:
        st.error("Error: 'movie_dick.pkl' is not a valid DataFrame or missing required columns.")
        st.stop()
    if not isinstance(similarity, (list, tuple, np.ndarray)):
        st.error("Error: 'similarity.pkl' is not in an expected array/list/numpy array format.")
        st.stop()

    if 'genres' not in movies.columns:
        movies['genres'] = [[] for _ in range(len(movies))]
    else:
        def parse_genres_string(genre_string):
            if isinstance(genre_string, list): return genre_string
            if isinstance(genre_string, str):
                try: return eval(genre_string)
                except (SyntaxError, TypeError):
                    return [g.strip() for g in genre_string.split('|')] if '|' in genre_string else [genre_string.strip()]
            return []

        movies['genres'] = movies['genres'].apply(parse_genres_string)
        movies['genres'] = movies['genres'].apply(lambda x: [str(g) for g in x] if isinstance(x, list) else [])

except (FileNotFoundError, pickle.PickleError) as e:
    st.error(f"Failed to load essential data files. Please ensure 'movie_dick.pkl' and 'similarity.pkl' are in the same directory. Error: {e}")
    st.stop()
except Exception as e:
    st.error(f"An unexpected error occurred during data loading: {e}")
    st.stop()


# --- 4. Streamlit App Configuration and Styling ---
st.set_page_config(layout="wide", page_title="Movie Recommender")

st.markdown("""
<style>
/* Consistent sizing and styling for movie posters in browse/recommendation views */
.stImage > img {
    height: 250px;
    object-fit: cover;
    border-radius: 5px;
    margin-bottom: 8px;
    width: 100%;
}

/* Styling for movie title to ensure consistent height and text overflow handling */
.movie-title-display {
    font-weight: bold;
    line-height: 1.2;
    height: 2.4em; /* Allows for two lines of text */
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2; /* Limits text to two lines */
    -webkit-box-orient: vertical;
}

/* Specific font size and margin for movie titles in the watchlist for better readability */
div.st-emotion-cache-1r6dm7f > div > div > div > div:nth-child(2) > p.movie-title-display {
    font-size: 1.2em;
    margin-top: 10px;
}

/* Compact styling for all action buttons (add/remove/get recs) across the app */
.stButton > button[key^="add_to_watchlist_"],
.stButton > button[key^="rec_watchlist_"],
.stButton > button[key^="remove_from_watchlist_display_"],
.stButton > button[key^="get_rec_from_watchlist_"],
.stButton > button[key^="rate_movie_"], /* New styling for rating buttons */
.stButton > button[key^="write_review_"],
.stButton > button[key^="view_reviews_"],
.stButton > button[key^="add_comment_"],
.stButton > button[key^="expand_rec_details_"], /* Styling for the view/rate/review button */
.stButton > button[key^="expand_browse_details_"],
.stButton > button[key^="expand_watchlist_details_"] {
    font-size: 0.7em;
    padding: 0.2em 0.4em !important;
    margin-top: 5px;
    display: block;
    width: 100%;
}

/* Style for star rating container */
.st-emotion-cache-1r6dm7f div[data-testid="stSlider"] {
    margin-top: -10px; /* Adjust if needed */
    margin-bottom: -10px; /* Adjust if needed */
}

/* Star styling for average rating display */
.star-rating-display {
    color: gold;
    font-size: 1.2em;
}
.avg-rating-text {
    font-size: 0.9em;
    color: #666;
    margin-left: 5px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center; color: #FF6347;'>🎬 Movie Recommender System</h1>", unsafe_allow_html=True)
st.markdown("---")


# --- 5. Session State Management ---
if 'user_id' not in st.session_state: st.session_state.user_id = None
if 'current_view' not in st.session_state: st.session_state.current_view = 'browse'
if 'last_recommended_movie' not in st.session_state: st.session_state.last_recommended_movie = None
if 'current_page' not in st.session_state: st.session_state.current_page = 1
if 'search_query' not in st.session_state: st.session_state.search_query = ""
if 'search_triggered' not in st.session_state: st.session_state.search_triggered = False
if 'expanded_movie_id' not in st.session_state: st.session_state.expanded_movie_id = None


# --- NEW: Function to display movie details (ratings, reviews, comments) ---
def display_movie_details(movie_id, movie_title, user_id, key_suffix=""):
    """
    Displays the rating, review, and comment sections for a given movie.
    Args:
        movie_id: The ID of the movie.
        movie_title: The title of the movie.
        user_id: The ID of the current logged-in user.
        key_suffix: A suffix to make widget keys unique across different calls.
    """
    with st.expander(f"Details for {movie_title}", expanded=True):
        st.subheader("Rate this Movie:")
        user_rating = get_user_movie_rating(user_id, movie_id)
        # Ensure the default value for the slider is within 1 and 5
        slider_value = user_rating if user_rating is not None else 3
        new_rating = st.slider(f"Your rating for {movie_title}", 1, 5, value=slider_value, key=f"rate_movie_{movie_id}_{key_suffix}")
        if st.button("Submit Rating", key=f"submit_rating_{movie_id}_{key_suffix}", type="primary"):
            add_movie_rating(user_id, movie_id, new_rating)
            st.session_state.expanded_movie_id = movie_id # Keep expanded
            st.rerun()

        st.subheader("Write a Review:")
        review_text = st.text_area(f"Your review for {movie_title}", key=f"review_text_{movie_id}_{key_suffix}")
        if st.button("Submit Review", key=f"submit_review_{movie_id}_{key_suffix}", type="primary"):
            if review_text:
                add_movie_review(user_id, movie_id, review_text)
                st.session_state.expanded_movie_id = movie_id # Keep expanded
                st.rerun()
            else: st.warning("Please write something for your review.")

        st.subheader("Community Comments:")
        comment_text = st.text_area(f"Add your comment for {movie_title}", key=f"comment_text_{movie_id}_{key_suffix}")
        if st.button("Post Comment", key=f"post_comment_{movie_id}_{key_suffix}", type="primary"):
            if comment_text:
                add_movie_comment(user_id, movie_id, comment_text)
                st.session_state.expanded_movie_id = movie_id # Keep expanded
                st.rerun()
            else: st.warning("Please write something for your comment.")

        st.markdown("---")
        st.subheader("All Reviews:")
        reviews = get_movie_reviews(movie_id)
        if reviews:
            for review_text, reviewer_username, timestamp in reviews:
                st.markdown(f"**{reviewer_username}** ({datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M')}): *{review_text}*")
        else: st.info("No reviews yet. Be the first!")

        st.markdown("---")
        st.subheader("All Comments:")
        comments = get_movie_comments(movie_id)
        if comments:
            for comment_text, commenter_username, timestamp in comments:
                st.markdown(f"**{commenter_username}** ({datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M')})"
                            f"<br>{comment_text}", unsafe_allow_html=True)
        else: st.info("No comments yet. Be the first!")


# --- 6. User Authentication Flow ---
if st.session_state.user_id is None:
    st.info("Welcome! Please **Login** or **Sign Up** to use the Movie Recommender and its community features.")

    login_col, signup_col = st.columns(2)

    with login_col:
        st.subheader("Login")
        with st.form("Login_Form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            if st.form_submit_button("Login"):
                if username and password:
                    user = verify_user(username, password)
                    if user:
                        st.session_state.user_id = user[0]
                        st.success("Logged in successfully!")
                        st.session_state.current_view = 'browse'
                        st.session_state.current_page = 1
                        st.session_state.last_recommended_movie = None
                        st.session_state.search_query = ""
                        st.session_state.search_triggered = False
                        st.session_state.expanded_movie_id = None
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
                else:
                    st.warning("Please enter both username and password to login.")

    with signup_col:
        st.subheader("Sign Up")
        with st.form("Sign_Up_Form"):
            new_username = st.text_input("New Username", key="signup_username")
            new_password = st.text_input("New Password", type="password", key="signup_password")
            if st.form_submit_button("Create Account"):
                if new_username and new_password:
                    if create_user(new_username, new_password):
                        st.success("Account created successfully! Please login.")
                    else:
                        st.error("Username already exists. Please choose a different one.")
                else:
                    st.warning("Please enter both a username and password to sign up.")
else:
    # --- 7. Main Application Layout (for logged-in users) ---
    logged_in_username = get_username_by_id(st.session_state.user_id)
    st.sidebar.success(f"Logged in as **{logged_in_username}**")

    with st.sidebar:
        st.markdown("---")
        st.subheader("Navigation")
        if st.button("Browse All Movies", key="nav_browse",
                     type="primary" if st.session_state.current_view == 'browse' else "secondary"):
            st.session_state.current_view = 'browse'
            st.session_state.current_page = 1
            st.session_state.search_query = ""
            st.session_state.search_triggered = False
            st.session_state.expanded_movie_id = None
            st.rerun()
        if st.button("Get Recommendations", key="nav_reco",
                     type="primary" if st.session_state.current_view == 'recommendations' else "secondary"):
            st.session_state.current_view = 'recommendations'
            st.session_state.current_page = 1
            st.session_state.search_query = ""
            st.session_state.search_triggered = False
            st.session_state.expanded_movie_id = None
            st.rerun()
        if st.button("My Watchlist", key="nav_watchlist",
                     type="primary" if st.session_state.current_view == 'watchlist' else "secondary"):
            st.session_state.current_view = 'watchlist'
            st.session_state.current_page = 1
            st.session_state.search_query = ""
            st.session_state.search_triggered = False
            st.session_state.expanded_movie_id = None
            st.rerun()

        st.markdown("---")
        if st.button("Logout", help="Click to log out of your account."):
            st.session_state.user_id = None
            st.session_state.current_view = 'browse'
            st.session_state.current_page = 1
            st.session_state.last_recommended_movie = None
            st.session_state.search_query = ""
            st.session_state.search_triggered = False
            st.session_state.expanded_movie_id = None
            st.info("You have been logged out.")
            st.rerun()

    if st.session_state.current_view == 'recommendations':
        st.header("Find Your Next Movie")
        st.markdown("""
            Select a movie from the dropdown to discover **6 similar movie recommendations**!
        """)
        st.markdown("---")

        with st.form("recommendation_form"):
            selected_movie_name = st.selectbox(
                'Choose a movie from our extensive list:',
                movies['title'].values,
                index=0,
                key="selected_movie_input",
                help="Start typing or scroll to find your desired movie."
            )

            submitted = st.form_submit_button('Get Recommendations', type="primary")

            if submitted:
                st.session_state.last_recommended_movie = selected_movie_name
                st.session_state.expanded_movie_id = None
                st.rerun()

        if st.session_state.last_recommended_movie:
            with st.spinner(f'🚀 Finding awesome recommendations for "{st.session_state.last_recommended_movie}"...'):
                names, posters, ids = recommend(st.session_state.last_recommended_movie)

                if names and posters and ids:
                    st.subheader(f"Because you watched: **{st.session_state.last_recommended_movie}**")
                    st.markdown("Here are some movies you might enjoy:")

                    cols = st.columns(len(names))

                    for i in range(len(names)):
                        with cols[i]:
                            st.image(posters[i], caption=names[i], use_container_width=True)

                            movie_id = ids[i]
                            movie_title = names[i]
                            user_id = st.session_state.user_id

                            avg_rating, num_ratings = get_average_movie_rating(movie_id)
                            if avg_rating is not None:
                                st.markdown(f"<p class='avg-rating-text'>Average: <span class='star-rating-display'>{'★' * int(round(avg_rating))}</span> ({avg_rating:.1f}/5 from {num_ratings} users)</p>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<p class='avg-rating-text'>No ratings yet.</p>", unsafe_allow_html=True)


                            on_watchlist = is_movie_in_watchlist(user_id, movie_id)
                            watchlist_button_label = "Remove from Watchlist" if on_watchlist else "Add to Watchlist"
                            watchlist_button_type = "secondary" if on_watchlist else "secondary"

                            if st.button(watchlist_button_label, key=f"rec_watchlist_{movie_id}", type=watchlist_button_type):
                                if on_watchlist: remove_from_watchlist(user_id, movie_id)
                                else: add_to_watchlist(user_id, movie_id, movie_title)
                                st.rerun()

                            expand_key = f"expand_rec_details_{movie_id}"
                            is_expanded = (st.session_state.expanded_movie_id == movie_id)
                            button_label = "Hide Details" if is_expanded else "View/Rate/Review"
                            button_type = "primary" if is_expanded else "secondary"

                            if st.button(button_label, key=expand_key, type=button_type):
                                if is_expanded:
                                    st.session_state.expanded_movie_id = None
                                else:
                                    st.session_state.expanded_movie_id = movie_id
                                st.rerun()

                            if is_expanded:
                                display_movie_details(movie_id, movie_title, user_id, key_suffix="rec")
                else:
                    st.warning("Could not find recommendations for this movie. Please try another.")
            st.markdown("---")

    elif st.session_state.current_view == 'browse':
        st.subheader("Explore All Movies")
        st.markdown("Browse our entire collection: **Click 'Get Recs' below a movie to get recommendations!**")

        with st.form("browse_search_form"):
            search_col, button_col = st.columns([0.8, 0.2])
            with search_col:
                current_search_input = st.text_input(
                    "Search movies by title:",
                    value=st.session_state.search_query,
                    key="browse_search_input_form",
                    placeholder="e.g., Inception, The Dark Knight"
                )
            with button_col:
                st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
                submitted_search = st.form_submit_button("Search", type="primary")

            if submitted_search:
                st.session_state.search_query = current_search_input.strip()
                st.session_state.search_triggered = True
                st.session_state.current_page = 1
                st.session_state.expanded_movie_id = None
                st.rerun()

        if st.session_state.search_triggered or st.session_state.search_query:
            if st.button("Clear Search", key="browse_clear_search_button", type="secondary"):
                st.session_state.search_query = ""
                st.session_state.search_triggered = False
                st.session_state.current_page = 1
                st.session_state.expanded_movie_id = None
                st.rerun()

        movies_to_display_filtered = movies.copy()

        if st.session_state.search_triggered and st.session_state.search_query:
            search_term_lower = st.session_state.search_query.lower()
            movies_to_display_filtered = movies_to_display_filtered[
                movies_to_display_filtered['title'].str.lower().str.contains(search_term_lower, na=False)
            ].copy()
            if movies_to_display_filtered.empty:
                st.warning(f"No movies found matching '{st.session_state.search_query}'.")

        total_movies = len(movies_to_display_filtered)
        movies_per_page = 15
        total_pages = (total_movies + movies_per_page - 1) // movies_per_page
        if total_pages == 0: total_pages = 1

        start_idx = (st.session_state.current_page - 1) * movies_per_page
        end_idx = start_idx + movies_per_page

        current_page_movies = movies_to_display_filtered.iloc[start_idx:end_idx]

        cols_per_row = 5
        rows = (len(current_page_movies) + cols_per_row - 1) // cols_per_row

        for i in range(rows):
            current_row_cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                idx = i * cols_per_row + j
                if idx < len(current_page_movies):
                    movie_row = current_page_movies.iloc[idx]
                    movie_id = movie_row.id
                    movie_title = movie_row.title

                    with current_row_cols[j]:
                        st.image(fetch_poster(movie_id), use_container_width=True)
                        st.markdown(f"<p class='movie-title-display'>{movie_title}</p>", unsafe_allow_html=True)

                        avg_rating, num_ratings = get_average_movie_rating(movie_id)
                        if avg_rating is not None:
                            st.markdown(f"<p class='avg-rating-text'>Average: <span class='star-rating-display'>{'★' * int(round(avg_rating))}</span> ({avg_rating:.1f}/5 from {num_ratings} users)</p>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<p class='avg-rating-text'>No ratings yet.</p>", unsafe_allow_html=True)

                        if st.button(
                                "Get Recs",
                                key=f"get_rec_from_browse_{movie_id}",
                                type="primary"
                        ):
                            st.session_state.current_view = 'recommendations'
                            st.session_state.last_recommended_movie = movie_title
                            st.session_state.current_page = 1
                            st.session_state.search_query = ""
                            st.session_state.search_triggered = False
                            st.session_state.expanded_movie_id = None
                            st.rerun()

                        on_watchlist = is_movie_in_watchlist(st.session_state.user_id, movie_id)
                        watchlist_button_label = "Remove from Watchlist" if on_watchlist else "Add to Watchlist"
                        watchlist_button_type = "secondary" if on_watchlist else "secondary"

                        if st.button(
                                watchlist_button_label,
                                key=f"add_to_watchlist_{movie_id}",
                                type=watchlist_button_type
                        ):
                            if on_watchlist:
                                remove_from_watchlist(st.session_state.user_id, movie_id)
                            else:
                                add_to_watchlist(st.session_state.user_id, movie_id, movie_title)
                            st.rerun()

                        expand_key = f"expand_browse_details_{movie_id}"
                        is_expanded = (st.session_state.expanded_movie_id == movie_id)
                        button_label = "Hide Details" if is_expanded else "View/Rate/Review"
                        button_type = "primary" if is_expanded else "secondary"

                        if st.button(button_label, key=expand_key, type=button_type):
                            if is_expanded:
                                st.session_state.expanded_movie_id = None
                            else:
                                st.session_state.expanded_movie_id = movie_id
                            st.rerun()

                        if is_expanded:
                            display_movie_details(movie_id, movie_title, st.session_state.user_id, key_suffix="browse")


        st.markdown("---")
        if total_movies > 0:
            max_visible_initial_pages = 6
            display_page_labels = []

            for i in range(1, min(total_pages + 1, max_visible_initial_pages + 1)):
                display_page_labels.append(str(i))

            if total_pages > max_visible_initial_pages:
                if str(total_pages) not in display_page_labels:
                    if total_pages > max_visible_initial_pages + 1:
                        display_page_labels.append("...")
                    display_page_labels.append(str(total_pages))

            num_total_pagination_cols = len(display_page_labels) + 2
            pagination_cols = st.columns(num_total_pagination_cols)

            col_index = 0
            with pagination_cols[col_index]:
                if st.button("Previous", disabled=(st.session_state.current_page == 1), key="prev_button_pag"):
                    st.session_state.current_page -= 1
                    st.rerun()
            col_index += 1

            for label in display_page_labels:
                with pagination_cols[col_index]:
                    if label == "...":
                        st.write("...")
                    else:
                        page_num = int(label)
                        button_type = "primary" if st.session_state.current_page == page_num else "secondary"
                        if st.button(label, type=button_type, key=f"page_button_{page_num}_pag"):
                            st.session_state.current_page = page_num
                            st.rerun()
                col_index += 1

            with pagination_cols[col_index]:
                if st.button("Next", disabled=(st.session_state.current_page == total_pages), key="next_button_pag"):
                    st.session_state.current_page += 1
                    st.rerun()

            st.info(f"Showing movies on page {st.session_state.current_page} of {total_pages}")


    elif st.session_state.current_view == 'watchlist':
        st.subheader("My Watchlist")
        user_id = st.session_state.user_id
        watchlist_movies = get_watchlist_movies(user_id)

        if not watchlist_movies:
            st.info("Your watchlist is empty. Add movies from the 'Explore All Movies' section!")
        else:
            cols_per_row_watchlist = 5
            num_movies_in_watchlist = len(watchlist_movies)
            rows_watchlist = (num_movies_in_watchlist + cols_per_row_watchlist - 1) // cols_per_row_watchlist

            for i in range(rows_watchlist):
                current_row_cols_watchlist = st.columns(cols_per_row_watchlist)
                for j in range(cols_per_row_watchlist):
                    idx = i * cols_per_row_watchlist + j
                    if idx < num_movies_in_watchlist:
                        movie_id, movie_title = watchlist_movies[idx]

                        with current_row_cols_watchlist[j]:
                            st.image(fetch_poster(movie_id), use_container_width=True)
                            st.markdown(f"<p class='movie-title-display'>{movie_title}</p>", unsafe_allow_html=True)

                            avg_rating, num_ratings = get_average_movie_rating(movie_id)
                            if avg_rating is not None:
                                st.markdown(f"<p class='avg-rating-text'>Average: <span class='star-rating-display'>{'★' * int(round(avg_rating))}</span> ({avg_rating:.1f}/5 from {num_ratings} users)</p>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<p class='avg-rating-text'>No ratings yet.</p>", unsafe_allow_html=True)


                            if st.button(
                                    "Remove",
                                    key=f"remove_from_watchlist_display_{movie_id}",
                                    type="secondary"
                            ):
                                remove_from_watchlist(user_id, movie_id)
                                st.rerun()
                            if st.button(
                                    "Get Recs",
                                    key=f"get_rec_from_watchlist_{movie_id}",
                                    type="primary"
                            ):
                                st.session_state.current_view = 'recommendations'
                                st.session_state.last_recommended_movie = movie_title
                                st.session_state.current_page = 1
                                st.session_state.expanded_movie_id = None
                                st.rerun()

                            expand_key = f"expand_watchlist_details_{movie_id}"
                            is_expanded = (st.session_state.expanded_movie_id == movie_id)
                            button_label = "Hide Details" if is_expanded else "View/Rate/Review"
                            button_type = "primary" if is_expanded else "secondary"

                            if st.button(button_label, key=expand_key, type=button_type):
                                if is_expanded:
                                    st.session_state.expanded_movie_id = None
                                else:
                                    st.session_state.expanded_movie_id = movie_id
                                st.rerun()

                            if is_expanded:
                                display_movie_details(movie_id, movie_title, user_id, key_suffix="watchlist")


    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; font-size: small; color: grey;'>
            *Powered by The Movie Database (TMDB) API*
        </div>
    """, unsafe_allow_html=True)