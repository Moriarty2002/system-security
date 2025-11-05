import os
import time
from flask import Flask, jsonify
import psycopg2

app = Flask(__name__)

# --- Database Connection Function ---
def get_db_connection():
    """Connects to the PostgreSQL database."""
    conn = None
    retries = 5
    while retries > 0:
        try:
            conn = psycopg2.connect(
                host="db",  # This is the service name from docker-compose.yml
                database=os.environ.get("POSTGRES_DB"),
                user=os.environ.get("POSTGRES_USER"),
                password=os.environ.get("POSTGRES_PASSWORD")
            )
            return conn
        except psycopg2.OperationalError:
            retries -= 1
            print("Database connection failed, retrying...")
            time.sleep(5)
    
    # If we exit the loop, it means connection failed permanently
    raise Exception("Could not connect to the database.")

# --- Database Initialization (run once) ---
@app.before_request
def setup_database():
    """
    Initializes the database on the first request.
    This creates the table and inserts sample data.
    """
    # 'g' is a special Flask object to store data for a single request.
    # We use it to ensure this init code runs only once per app startup.
    if not hasattr(app, '_database_initialized'):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Create the table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(80) UNIQUE NOT NULL,
                    role VARCHAR(80) NOT NULL
                );
            """)
            
            # Insert sample data (ignoring if it already exists)
            cur.execute("""
                INSERT INTO users (username, role) 
                VALUES ('admin_user', 'Administrator'), ('normal_user', 'User')
                ON CONFLICT (username) DO NOTHING;
            """)
            
            conn.commit()
            cur.close()
            conn.close()
            app._database_initialized = True
            print("Database initialized successfully.")
        except Exception as e:
            print(f"Error during database initialization: {e}")


# --- API Endpoint ---
@app.route("/api/data")
def get_data():
    """A sample API endpoint to fetch data from the database."""
    try:
        print("Fetching data from database...")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT username, role FROM users;")
        users = cur.fetchall()
        cur.close()
        conn.close()
        
        # Format the data as a list of dictionaries
        user_list = [{"username": row[0], "role": row[1]} for row in users]
        
        return jsonify(user_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

# --- API Endpoint ---
@app.route("/data")
def get_data2():
    """A sample API endpoint to fetch data from the database."""
    try:
        print("Fetching data from database...")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT username, role FROM users;")
        users = cur.fetchall()
        cur.close()
        conn.close()
        
        # Format the data as a list of dictionaries
        user_list = [{"username": row[0], "role": row[1]} for row in users]
        
        return jsonify(user_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)