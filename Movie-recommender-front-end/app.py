import pickle
import pandas as pd
import streamlit as st
import requests
from requests.exceptions import RequestException
import sqlite3
from datetime import datetime

# --- Database Initialization and Functions --- #
conn = sqlite3.connect('user_profiles.db')
c = conn.cursor()

# Create tables if they don't exist
c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
             username TEXT UNIQUE,
             password TEXT,
             created_at TIMESTAMP)''')

# Removed favorites and history table creation statements

conn.commit()

def create_user(username, password):
    try:
        c.execute("INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
                (username, password, datetime.now()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def verify_user(username, password):
    c.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
    return c.fetchone()

# Removed add_favorite, get_favorites, add_to_history, get_history functions

# --- API and Recommendation Functions --- #
def fetch_poster(movie_id):
    try:
        response = requests.get(f'https://api.themoviedb.org/3/movie/{movie_id}?api_key=5a0f912e8b0ae43f239e2346fda7634f&language=en-us', timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        if data.get('poster_path'):
            return "https://image.tmdb.org/t/p/original" + data['poster_path']
        return "https://via.placeholder.com/150?text=No+Poster" # Placeholder if no poster path
    except RequestException as e:
        st.error(f"Failed to fetch poster: {str(e)}")
        return "https://via.placeholder.com/150?text=Error+Loading" # Error placeholder

def recommend(movie):
    try:
        movie_index = movies[movies['title'] == movie].index[0]
        distances = similarity[movie_index]
        movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:6]

        recommended_movie_names = []
        recommended_movie_posters = []
        for i in movies_list:
            movie_id = movies.iloc[i[0]].id
            recommended_movie_names.append(movies.iloc[i[0]].title)
            recommended_movie_posters.append(fetch_poster(movie_id))
        
        return recommended_movie_names, recommended_movie_posters
    except Exception as e:
        st.error(f"Recommendation failed: {str(e)}")
        return [], [] # Return empty lists on failure

# --- Load Data --- #
try:
    movies_dick = pickle.load(open("movie_dick.pkl", 'rb'))
    movies = pd.DataFrame(movies_dick)
    similarity = pickle.load(open("similarity.pkl", 'rb'))
except (FileNotFoundError, pickle.PickleError) as e:
    st.error(f"Failed to load data files: {str(e)}")
    st.stop() # Stop the app if data files are not loaded

# --- Streamlit App Layout --- #
st.set_page_config(layout="wide", page_title="Movie Recommender")
st.title("🎬 Movie Recommender System")

# --- Authentication Section --- #
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

if st.session_state.user_id is None:
    st.markdown("""
        Welcome! Please Login or Sign Up to use the Movie Recommender.
    """)
    auth_option = st.sidebar.radio("Account", ["Login", "Sign Up"])

    if auth_option == "Login":
        with st.sidebar.form("Login_Form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                user = verify_user(username, password)
                if user:
                    st.session_state.user_id = user[0]
                    st.sidebar.success("Logged in successfully!")
                    st.rerun() # Rerun to show main content
                else:
                    st.sidebar.error("Invalid credentials")
    else: # Sign Up
        with st.sidebar.form("Sign_Up_Form"):
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type="password")
            if st.form_submit_button("Create Account"):
                if create_user(new_username, new_password):
                    st.sidebar.success("Account created! Please login.")
                else:
                    st.sidebar.error("Username already exists")
else:
    # --- Main Application Content (after login) ---
    if st.sidebar.button("Logout"):
        st.session_state.user_id = None
        st.rerun()

    tab1, = st.tabs(["Movie Recommender"])
    
    with tab1:
        st.header("Find Your Next Movie")
        st.markdown("""
            Select a movie title from the dropdown to get personalized recommendations.
        """)

        # Changed from st.text_input to st.selectbox for suggestions
        selected_movie_name = st.selectbox(
            'Select a movie:',
            movies['title'].values # Populate with all movie titles
        )

        if st.button('Get Recommendations'):
            if selected_movie_name:
                # Display a spinner while recommendations are being fetched
                with st.spinner('Finding recommendations...'):
                    # Check if the entered movie exists in the dataset
                    if selected_movie_name in movies['title'].values:
                        names, posters = recommend(selected_movie_name)
                        
                        if names and posters: # Ensure recommendations were returned
                            st.success('Here are your recommendations!')
                            st.toast('Recommendations loaded!', icon='🎉')

                            # Create 5 columns to display movie posters and names
                            col1, col2, col3, col4, col5 = st.columns(5)

                            # Display each recommended movie in its respective column
                            for i in range(len(names)):
                                movie_id = movies[movies['title'] == names[i]].iloc[0].id
                                # Removed add_to_history call

                            with col1:
                                st.text(names[0])
                                st.image(posters[0])
                                # Removed favorite button
                            with col2:
                                st.text(names[1])
                                st.image(posters[1])
                                # Removed favorite button
                            with col3:
                                st.text(names[2])
                                st.image(posters[2])
                                # Removed favorite button
                            with col4:
                                st.text(names[3])
                                st.image(posters[3])
                                # Removed favorite button
                            with col5:
                                st.text(names[4])
                                st.image(posters[4])
                                # Removed favorite button
                        else:
                            st.error("Could not retrieve recommendations. Please try again.")
                    else:
                        st.warning(f"Movie '{selected_movie_name}' not found in our database. Please try another title.")
            else:
                st.warning("Please enter a movie title to get recommendations.")

    # Removed with tab2 and with tab3 blocks

    # Optional: Add a footer for attribution
    st.markdown("""
        ---
        *Powered by TMDB API*
    """)