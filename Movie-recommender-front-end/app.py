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


# --- 2. API and Recommendation Logic ---
TMDB_API_KEY = '5a0f912e8b0ae43f239e2346fda7634f' # Your TMDB API Key
OMDB_API_KEY = 'caf997f4' # Replace with your OMDb API key

@st.cache_data
def fetch_movie_details_from_tmdb(movie_id):
    """Fetches comprehensive movie details from TMDB."""
    details = {}
    try:
        movie_id = int(movie_id)
        base_url = "https://api.themoviedb.org/3/movie/"

        # Fetch main details
        response_main = requests.get(
            f'{base_url}{movie_id}?api_key={TMDB_API_KEY}&language=en-us', timeout=5
        )
        response_main.raise_for_status()
        main_data = response_main.json()

        details['poster_path'] = "https://image.tmdb.org/t/p/w500" + main_data.get('poster_path', '') if main_data.get('poster_path') else "https://via.placeholder.com/150?text=No+Poster"
        details['overview'] = main_data.get('overview', 'No overview available.')
        details['release_date'] = main_data.get('release_date', 'N/A')
        details['runtime'] = main_data.get('runtime', 'N/A')
        details['imdb_id'] = main_data.get('imdb_id', None) # To fetch OMDb data
        details['genres'] = [genre['name'] for genre in main_data.get('genres', [])]


        # Fetch credits (cast and crew)
        response_credits = requests.get(
            f'{base_url}{movie_id}/credits?api_key={TMDB_API_KEY}', timeout=5
        )
        response_credits.raise_for_status()
        credits_data = response_credits.json()
        details['cast'] = [c['name'] for c in credits_data.get('cast', [])[:5]] # Top 5 cast
        details['director'] = next((crew['name'] for crew in credits_data.get('crew', []) if crew['job'] == 'Director'), 'N/A')

        # Fetch videos (trailers/teasers)
        response_videos = requests.get(
            f'{base_url}{movie_id}/videos?api_key={TMDB_API_KEY}', timeout=5
        )
        response_videos.raise_for_status()
        videos_data = response_videos.json()
        trailer_key = None
        for video in videos_data.get('results', []):
            if video.get('site') == 'YouTube' and 'Trailer' in video.get('type', ''):
                trailer_key = video['key']
                break
            elif video.get('site') == 'YouTube' and 'Teaser' in video.get('type', ''):
                trailer_key = video['key']
        details['youtube_trailer_key'] = trailer_key

    except RequestException as e:
        st.error(f"Error fetching movie details from TMDB for ID {movie_id}: {e}")
        details['poster_path'] = "https://via.placeholder.com/150?text=Error"
    except ValueError:
        st.error(f"Invalid movie ID: {movie_id}")
        details['poster_path'] = "https://via.placeholder.com/150?text=Invalid+ID"
    return details


@st.cache_data
def fetch_omdb_data(imdb_id):
    """Fetches IMDb and Rotten Tomatoes ratings from OMDb API."""
    if not imdb_id or OMDB_API_KEY == 'YOUR_OMDB_API_KEY':
        return None, None # Return None if no IMDb ID or API key not set
    try:
        response = requests.get(
            f'http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}', timeout=5
        )
        response.raise_for_status()
        data = response.json()
        if data.get('Response') == 'True':
            imdb_rating = data.get('imdbRating', 'N/A')
            rotten_tomatoes_rating = 'N/A'
            for rating_source in data.get('Ratings', []):
                if rating_source.get('Source') == 'Rotten Tomatoes':
                    rotten_tomatoes_rating = rating_source.get('Value', 'N/A')
                    break
            return imdb_rating, rotten_tomatoes_rating
        return 'N/A', 'N/A'
    except RequestException as e:
        # st.warning(f"Could not fetch OMDb data for {imdb_id}: {e}. Ensure your OMDb API key is correct.")
        return 'N/A', 'N/A'
    except Exception as e:
        # st.warning(f"An unexpected error occurred while fetching OMDb data for {imdb_id}: {e}")
        return 'N/A', 'N/A'


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
                # Use fetch_movie_details_from_tmdb to get poster for recommendations
                details = fetch_movie_details_from_tmdb(int(rec_movie.id))
                recommended_posters.append(details['poster_path'])
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
# Initialize pagination states for reviews per movie details
if 'reviews_page_dict' not in st.session_state: st.session_state.reviews_page_dict = {}


# --- NEW: Function to display movie details (ratings, reviews, and extended info) ---
def display_movie_details(movie_id, movie_title, user_id, key_suffix=""):
    """
    Displays the rating, review, and comment sections for a given movie,
    along with extended movie details from TMDB and OMDb.
    Args:
        movie_id: The ID of the movie.
        movie_title: The title of the movie.
        user_id: The ID of the current logged-in user.
        key_suffix: A suffix to make widget keys unique across different calls.
    """
    # Ensure pagination states are initialized for this specific movie
    if movie_id not in st.session_state.reviews_page_dict:
        st.session_state.reviews_page_dict[movie_id] = 1

    with st.expander(f"Details for {movie_title}", expanded=True):
        details = fetch_movie_details_from_tmdb(movie_id)
        # Removed the call to fetch_omdb_data as External Ratings section is removed
        # imdb_rating, rt_rating = fetch_omdb_data(details.get('imdb_id'))

        # --- Movie Overview and Key Info ---
        st.subheader("Overview")
        st.write(details.get('overview', 'No overview available.'))

        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.markdown(f"**Release Date:** {details.get('release_date')}")
            st.markdown(f"**Runtime:** {details.get('runtime')} minutes" if details.get('runtime') != 'N/A' else "**Runtime:** N/A")
            st.markdown(f"**Genres:** {', '.join(details.get('genres', [])) if details.get('genres') else 'N/A'}")
        with info_col2:
            st.markdown(f"**Director:** {details.get('director')}")
            st.markdown(f"**Top Cast:** {', '.join(details.get('cast', [])) if details.get('cast') else 'N/A'}")

        # Removed the External Ratings section
        # if imdb_rating != 'N/A' or rt_rating != 'N/A':
        #     st.markdown("---")
        #     st.subheader("External Ratings")
        #     rating_col1, rating_col2 = st.columns(2)
        #     with rating_col1:
        #         if imdb_rating != 'N/A': st.markdown(f"**IMDb Rating:** {imdb_rating}")
        #     with rating_col2:
        #         if rt_rating != 'N/A': st.markdown(f"**Rotten Tomatoes:** {rt_rating}")

        if details.get('youtube_trailer_key'):
            st.markdown("---")
            st.subheader("Trailer")
            st.video(f"https://www.youtube.com/watch?v={details['youtube_trailer_key']}")

        st.markdown("---")
        st.subheader("Rate this Movie:")
        user_rating = get_user_movie_rating(user_id, movie_id)
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

        st.markdown("---")
        st.subheader("All Reviews:")
        all_reviews = get_movie_reviews(movie_id)
        reviews_per_page = 5
        current_reviews_page = st.session_state.reviews_page_dict[movie_id]
        total_reviews_pages = (len(all_reviews) + reviews_per_page - 1) // reviews_per_page
        if total_reviews_pages == 0: total_reviews_pages = 1 # At least 1 page even if no reviews

        st.markdown(f"<p style='text-align: center; font-size: 0.9em; color: #666;'>Showing {min(reviews_per_page, len(all_reviews))} of {len(all_reviews)} reviews</p>", unsafe_allow_html=True)

        if all_reviews:
            start_review_idx = (current_reviews_page - 1) * reviews_per_page
            end_review_idx = start_review_idx + reviews_per_page
            current_page_reviews = all_reviews[start_review_idx:end_review_idx]

            for review_text, reviewer_username, timestamp in current_page_reviews:
                st.markdown(f"**{reviewer_username}** ({datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M')}): *{review_text}*")

            # Review Pagination
            if total_reviews_pages > 1:
                review_nav_cols = st.columns([1, 1, 1])
                with review_nav_cols[0]:
                    if current_reviews_page > 1:
                        if st.button("⬅️ Prev Review Page", key=f"prev_review_page_{movie_id}_{key_suffix}"):
                            st.session_state.reviews_page_dict[movie_id] -= 1
                            st.session_state.expanded_movie_id = movie_id # Keep expanded
                            st.rerun()
                with review_nav_cols[1]:
                    st.markdown(f"<p style='text-align: center; margin-top: 10px; font-size: 0.8em;'>Page {current_reviews_page} of {total_reviews_pages}</p>", unsafe_allow_html=True)
                with review_nav_cols[2]:
                    if current_reviews_page < total_reviews_pages:
                        if st.button("Next Review Page ➡️", key=f"next_review_page_{movie_id}_{key_suffix}"):
                            st.session_state.reviews_page_dict[movie_id] += 1
                            st.session_state.expanded_movie_id = movie_id # Keep expanded
                            st.rerun()
        else: st.info("No reviews yet. Be the first!")


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
                        st.session_state.reviews_page_dict = {} # Reset pagination dicts on login
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
            st.session_state.reviews_page_dict = {} # Reset pagination dicts on navigation
            st.rerun()
        if st.button("Get Recommendations", key="nav_reco",
                     type="primary" if st.session_state.current_view == 'recommendations' else "secondary"):
            st.session_state.current_view = 'recommendations'
            st.session_state.current_page = 1
            st.session_state.search_query = ""
            st.session_state.search_triggered = False
            st.session_state.expanded_movie_id = None
            st.session_state.reviews_page_dict = {} # Reset pagination dicts on navigation
            st.rerun()
        if st.button("My Watchlist", key="nav_watchlist",
                     type="primary" if st.session_state.current_view == 'watchlist' else "secondary"):
            st.session_state.current_view = 'watchlist'
            st.session_state.current_page = 1
            st.session_state.search_query = ""
            st.session_state.search_triggered = False
            st.session_state.expanded_movie_id = None
            st.session_state.reviews_page_dict = {} # Reset pagination dicts on navigation
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
            st.session_state.reviews_page_dict = {} # Reset pagination dicts on logout
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
                st.session_state.reviews_page_dict = {} # Reset pagination dicts for new recommendations
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
                            # Use fetch_movie_details_from_tmdb to get a consistent poster
                            movie_details_summary = fetch_movie_details_from_tmdb(ids[i])
                            st.image(movie_details_summary['poster_path'], caption=names[i], use_container_width=True)

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
                                # Reset review pagination for this specific movie when expanding
                                st.session_state.reviews_page_dict[movie_id] = 1
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
                st.session_state.reviews_page_dict = {} # Reset pagination dicts for new search
                st.rerun()

        if st.session_state.search_triggered or st.session_state.search_query:
            if st.button("Clear Search", key="browse_clear_search_button", type="secondary"):
                st.session_state.search_query = ""
                st.session_state.search_triggered = False
                st.session_state.current_page = 1
                st.session_state.expanded_movie_id = None
                st.session_state.reviews_page_dict = {} # Reset pagination dicts on clear search
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
                        # Use fetch_movie_details_from_tmdb to get the poster
                        movie_details_summary = fetch_movie_details_from_tmdb(movie_id)
                        st.image(movie_details_summary['poster_path'], use_container_width=True)
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
                            st.session_state.reviews_page_dict = {} # Reset pagination dicts for new recommendation
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
                            # Reset review pagination for this specific movie when expanding
                            st.session_state.reviews_page_dict[movie_id] = 1
                            st.rerun()

                        if is_expanded:
                            display_movie_details(movie_id, movie_title, st.session_state.user_id, key_suffix="browse")


        # Pagination for Browse All Movies
        st.markdown("---")
        pagination_cols = st.columns([1, 1, 1])
        with pagination_cols[0]:
            if st.session_state.current_page > 1:
                if st.button("⬅️ Previous Page", key="prev_page_browse", type="secondary"):
                    st.session_state.current_page -= 1
                    st.session_state.expanded_movie_id = None
                    st.session_state.reviews_page_dict = {} # Reset pagination dicts on page change
                    st.rerun()
        with pagination_cols[1]:
            st.markdown(f"<p style='text-align: center; margin-top: 10px;'>Page {st.session_state.current_page} of {total_pages}</p>", unsafe_allow_html=True)
        with pagination_cols[2]:
            if st.session_state.current_page < total_pages:
                if st.button("Next Page ➡️", key="next_page_browse", type="secondary"):
                    st.session_state.current_page += 1
                    st.session_state.expanded_movie_id = None
                    st.session_state.reviews_page_dict = {} # Reset pagination dicts on page change
                    st.rerun()

    elif st.session_state.current_view == 'watchlist':
        st.subheader("My Watchlist")
        st.markdown("Movies you've added to your watchlist:")
        st.markdown("---")

        watchlist_movies = get_watchlist_movies(st.session_state.user_id)

        if not watchlist_movies:
            st.info("Your watchlist is empty. Add movies from 'Browse All Movies' or 'Get Recommendations'!")
        else:
            cols_per_row = 5
            num_movies = len(watchlist_movies)
            rows = (num_movies + cols_per_row - 1) // cols_per_row

            for i in range(rows):
                current_row_cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    idx = i * cols_per_row + j
                    if idx < num_movies:
                        movie_id, movie_title = watchlist_movies[idx]

                        with current_row_cols[j]:
                            # Use fetch_movie_details_from_tmdb to get the poster
                            movie_details_summary = fetch_movie_details_from_tmdb(movie_id)
                            st.image(movie_details_summary['poster_path'], use_container_width=True)
                            st.markdown(f"<p class='movie-title-display'>{movie_title}</p>", unsafe_allow_html=True)

                            avg_rating, num_ratings = get_average_movie_rating(movie_id)
                            if avg_rating is not None:
                                st.markdown(f"<p class='avg-rating-text'>Average: <span class='star-rating-display'>{'★' * int(round(avg_rating))}</span> ({avg_rating:.1f}/5 from {num_ratings} users)</p>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<p class='avg-rating-text'>No ratings yet.</p>", unsafe_allow_html=True)

                            if st.button("Remove from Watchlist", key=f"remove_from_watchlist_display_{movie_id}", type="secondary"):
                                remove_from_watchlist(st.session_state.user_id, movie_id)
                                st.rerun()

                            if st.button(
                                    "Get Recs",
                                    key=f"get_rec_from_watchlist_{movie_id}",
                                    type="primary"
                            ):
                                st.session_state.current_view = 'recommendations'
                                st.session_state.last_recommended_movie = movie_title
                                st.session_state.current_page = 1
                                st.session_state.search_query = ""
                                st.session_state.search_triggered = False
                                st.session_state.expanded_movie_id = None
                                st.session_state.reviews_page_dict = {} # Reset pagination dicts for new recommendation
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
                                # Reset review pagination for this specific movie when expanding
                                st.session_state.reviews_page_dict[movie_id] = 1
                                st.rerun()

                            if is_expanded:
                                display_movie_details(movie_id, movie_title, st.session_state.user_id, key_suffix="watchlist")