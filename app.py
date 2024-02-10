from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import plotly.graph_objs as go
import pandas as pd
from flask import send_file
from config import db_config

app = Flask(__name__)

app.secret_key = "super secret key"


# Function to create a MySQL connection
def create_connection():
    return mysql.connector.connect(**db_config)


# Function to check if the user is an admin
def is_admin():
    if 'username' in session:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT role FROM users WHERE username = %s', (session['username'],))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user and user[0] == 'admin':
            return True
    return False


# Function to generate plot of most used services
def generate_plot():
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT services.name, COUNT(clients.id) AS client_count FROM services LEFT JOIN clients ON services.id = clients.service_id GROUP BY services.id')
        service_data = cursor.fetchall()
        cursor.close()
        conn.close()

        # Extract service names and counts from query result
        services = [row[0] for row in service_data]
        counts = [row[1] for row in service_data]

        # Create a Plotly bar chart
        fig = go.Figure(data=[go.Bar(x=services, y=counts)])
        fig.update_layout(title='Most Used Services', xaxis_title='Service', yaxis_title='Number of Clients')

        # Convert the Plotly figure to HTML
        plot_div = fig.to_html(full_html=False)

        return plot_div
    except Exception as e:
        print("Error generating plot:", e)
        return ""


@app.route('/')
def index():
    if 'username' in session:
        # Generate the Plotly plot
        plot_div = generate_plot()

        # Fetch services data
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM services')
        services = cursor.fetchall()
        cursor.close()
        conn.close()

        # Render the template with services data and plot_div
        return render_template('dashboard.html', services=services, plot_div=plot_div)
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
            session['username'] = username
            print(session)  # Debug: Print session data
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        query = request.args.get('query')
        conn = create_connection()
        cursor = conn.cursor()
        if query:
            cursor.execute('SELECT clients.id, clients.name, clients.email, services.name AS service_name FROM clients LEFT JOIN services ON clients.service_id = services.id WHERE clients.name LIKE %s', ('%' + query + '%',))
        else:
            cursor.execute('SELECT clients.id, clients.name, clients.email, services.name AS service_name FROM clients LEFT JOIN services ON clients.service_id = services.id')
        clients = cursor.fetchall()  # Fetch all rows as tuples
        cursor.close()
        conn.close()

        # Structure data correctly as dictionaries
        clients = [{'id': row[0], 'name': row[1], 'email': row[2], 'service_name': row[3]} for row in clients]

        if is_admin():
            return render_template('dashboard.html', clients=clients, plot_url=generate_plot(), is_admin=is_admin)
        else:
            return render_template('user_page.html', clients=clients, is_admin=is_admin)
    return redirect(url_for('login'))


# CRUD operations for clients
@app.route('/clients/add', methods=['GET', 'POST'])
def add_client():
    if is_admin():
        if request.method == 'POST':
            name = request.form['name']
            email = request.form['email']
            service_id = request.form['service'] if request.form['service'] else None  # Ensure service_id is None if empty
            conn = create_connection()
            cursor = conn.cursor()
            # Execute SQL query to insert client data into the database
            cursor.execute('INSERT INTO clients (name, email, service_id) VALUES (%s, %s, %s)', (name, email, service_id))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Client added successfully', 'success')
            return redirect(url_for('dashboard'))

        # Fetch services data
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM services')
        services = cursor.fetchall()
        cursor.close()
        conn.close() 

        return render_template('add_client.html', services=services)
    else:
        flash('You are not authorized to access this page.', 'error')
        return redirect(url_for('dashboard'))


@app.route('/clients/edit/<int:id>', methods=['GET', 'POST'])
def edit_client(id):
    if is_admin():
        if request.method == 'GET':
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM clients WHERE id = %s', (id,))
            client_data = cursor.fetchone()
            cursor.execute('SELECT * FROM services')
            services = cursor.fetchall()
            cursor.close()
            conn.close()
            if client_data:
                client = {
                    'id': client_data[0],
                    'name': client_data[1],
                    'email': client_data[2]
                }
                return render_template('edit_client.html', client=client, services=services)
            else:
                flash('Client not found', 'error')
                return redirect(url_for('dashboard'))
        elif request.method == 'POST':
            name = request.form['name']
            email = request.form['email']
            service_id = request.form['service']
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE clients SET name = %s, email = %s, service_id = %s WHERE id = %s', (name, email, service_id, id))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Client updated successfully', 'success')
            return redirect(url_for('dashboard'))
    else:
        flash('You are not authorized to access this page.', 'error')
        return redirect(url_for('dashboard'))


@app.route('/clients/delete/<int:id>')
def delete_client(id):
    if is_admin():
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM clients WHERE id = %s', (id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Client deleted successfully', 'success')
    else:
        flash('You are not authorized to access this page.', 'error')
    return redirect(url_for('dashboard'))


# CRUD operations for services
@app.route('/services/add', methods=['GET', 'POST'])
def add_service():
    if is_admin():
        if request.method == 'POST':
            name = request.form['name']
            description = request.form['description']
            conn = create_connection()
            cursor = conn.cursor()
            # Execute SQL query to insert service data into the database
            cursor.execute('INSERT INTO services (name, description) VALUES (%s, %s)', (name, description))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Service added successfully', 'success')
            return redirect(url_for('dashboard'))
        return render_template('add_service.html')
    else:
        flash('You are not authorized to access this page.', 'error')
        return redirect(url_for('dashboard'))


@app.route('/services/edit/<int:id>', methods=['GET', 'POST'])
def edit_service(id):
    if is_admin():
        if request.method == 'GET':
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM services WHERE id = %s', (id,))
            service = cursor.fetchone()
            cursor.close()
            conn.close()
            if service:
                service_dict = {
                    'id': service[0],
                    'name': service[1],
                    'description': service[2]
                }
                return render_template('edit_service.html', service=service_dict)
            else:
                flash('Service not found', 'error')
                return redirect(url_for('dashboard'))
        elif request.method == 'POST':
            name = request.form['name']
            description = request.form['description']
            # Update service in the database
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE services SET name = %s, description = %s WHERE id = %s', (name, description, id))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Service updated successfully', 'success')
            return redirect(url_for('dashboard'))
    else:
        flash('You are not authorized to access this page.', 'error')
        return redirect(url_for('dashboard'))


@app.route('/services/delete/<int:id>')
def delete_service(id):
    if is_admin():
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM services WHERE id = %s', (id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Service deleted successfully', 'success')
    else:
        flash('You are not authorized to access this page.', 'error')
    return redirect(url_for('dashboard'))


@app.route('/export')
def export_to_excel():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clients')
    clients = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convert the client data to a DataFrame
    df = pd.DataFrame(clients, columns=['ID', 'Name', 'Email', 'Service'])

    # Export the DataFrame to an Excel file
    excel_file_path = 'clients_data.xlsx'
    df.to_excel(excel_file_path, index=False)

    # Send the Excel file as a downloadable attachment
    return send_file(excel_file_path, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)
