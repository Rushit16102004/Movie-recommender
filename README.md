# Movie Recommender System

This is a Streamlit-based movie recommendation system that suggests movies to users based on their selections. It includes user authentication and movie search with suggestions.

## Features

-   **User Authentication**: Users can sign up and log in to access the recommender.
-   **Movie Search with Suggestions**: Users can select movies from a dropdown list to get recommendations, preventing spelling mistakes.
-   **Interactive UI**: Built with Streamlit for an intuitive and responsive user interface.

## Setup Instructions

Follow these steps to set up and run the project locally.

### Prerequisites

- Python 3.7+
- pip (Python package installer)

### Installation

1.  **Clone the repository (or download the project files):**
    ```bash
    git clone <your-repository-url>
    cd Movie-recommender-front-end
    ```
    *(Note: If you downloaded the files, navigate to the `Movie-recommender-front-end` directory.)*

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv .venv
    ```

3.  **Activate the virtual environment:**
    -   **Windows:**
        ```bash
        .venv\Scripts\activate
        ```
    -   **macOS/Linux:**
        ```bash
        source .venv/bin/activate
        ```

4.  **Install the required Python packages:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: If `requirements.txt` is not present, you will need to create it. The main dependencies are `streamlit`, `pandas`, `requests`, `scikit-learn` (for `pickle` files), and `sqlite3` (built-in). You can generate one using `pip freeze > requirements.txt` after installing necessary packages.)*

### Data Files

Ensure you have the following data files in the specified locations:

-   `Movie-recommender-front-end/movie_dick.pkl`
-   `Movie-recommender-front-end/similarity.pkl`
-   `Movie-recommender-front-end/user_profiles.db`
-   `data/tmdb_5000_credits.csv`
-   `data/tmdb_5000_movies.csv`

These files are crucial for the recommendation engine. If you don't have them, you might need to generate them using the `movie-recommender.ipynb` notebook or obtain them from the original source.

## Running the Application

1.  **Navigate to the `Movie-recommender-front-end` directory:**
    ```bash
    cd Movie-recommender-front-end
    ```

2.  **Run the Streamlit application:**
    ```bash
    streamlit run app.py
    ```

    This command will open the application in your default web browser. If it doesn't open automatically, Streamlit will provide a local URL (e.g., `http://localhost:8501`) that you can copy and paste into your browser.

## Project Structure
