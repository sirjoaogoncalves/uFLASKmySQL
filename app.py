from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import plotly.graph_objs as go
import pandas as pd
from flask import send_file
from config import db_config
import requests
from bs4 import BeautifulSoup
import wikipedia 



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



def generate_plot():
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT services.name, COUNT(clients.id) AS client_count FROM services LEFT JOIN clients ON services.id = clients.service_id GROUP BY services.id')
        service_data = cursor.fetchall()
        cursor.close()
        conn.close()

       
        services = [row[0] for row in service_data]
        counts = [row[1] for row in service_data]

       
        fig = go.Figure(data=[go.Bar(x=services, y=counts)])
        fig.update_layout(xaxis_title='Serviços', yaxis_title='Numero de Clientes')

        # Convert the Plotly figure to HTML
        plot_div = fig.to_html(full_html=False)

        return plot_div
    except Exception as e:
        print("Error generating plot:", e)
        return ""

def scrape_news():
    # Fetch the HTML content from the website
    response = requests.get('https://www.cmjornal.pt/cm-ao-minuto')
    content = response.content

    # Parse the HTML content
    site = BeautifulSoup(content, 'html.parser')

    # Find the main news section
    noticias = site.find_all('div', attrs={'class': 'aominutoMain'})

    # Create a list to store the news items
    news_list = []

    # Iterate over each news item and extract the title, publication date, and link
    for noticia in noticias:
        titulo = noticia.find('span', attrs={'class': 'lead'})
        h2_tag = noticia.find('h2')  # Find the <h2> tag

        # Extract the date and link from within the <h2> tag
        date = h2_tag.text.strip() if h2_tag else ''
        link = h2_tag.find('a', href=True)  # Find the <a> tag within the <h2> tag
        news_link = link['href'] if link else ''

        # Check if the title exists
        title = titulo.text.strip() if titulo else ''

        # Add the news item to the list
        news_list.append({'title': title, 'date': date, 'link': news_link})

    # Return the last five news items
    return news_list[-5:]

       

@app.route('/search', methods=['GET', 'POST'])
def search_wikipedia():
    # Return the last fi
    query = request.form['query']
    language = request.form.get('language', 'en')  
    try: 
        wikipedia.set_lang(language)
        result = wikipedia.summary(query, sentences=2)
        return render_template('search_results.html', result=result)
    except wikipedia.exceptions.DisambiguationError as e:
        return render_template('search_results.html', result=str(e))
    except wikipedia.exceptions.PageError as e:
        return render_template('search_results.html', result=str(e))



@app.route('/')
def index():
    if 'username' in session:
        query = request.args.get('query')
       
        # Fetch services data
        conn = create_connection()
        cursor = conn.cursor()
        if query:
            cursor.execute('SELECT clients.id, clients.name, clients.email, services.name AS service_name FROM clients LEFT JOIN services ON clients.service_id = services.id WHERE clients.name LIKE %s', ('%' + query + '%',))
        else:
            cursor.execute('SELECT clients.id, clients.name, clients.email, services.name AS service_name FROM clients LEFT JOIN services ON clients.service_id = services.id')
        clients = cursor.fetchall()  # Fetch all rows as tuples
        cursor.close()
        conn.close()
        
        clients = [{'id': row[0], 'name': row[1], 'email': row[2], 'service_name': row[3]} for row in clients]

        if is_admin():
            return render_template('dashboard.html', clients=clients, plot_url=generate_plot(), is_admin=is_admin)
        else:
            return render_template('user_page.html', clients=clients, plot_url=generate_plot() ,is_admin=is_admin)
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
            return render_template('user_page.html', clients=clients, plot_url=generate_plot(), news = scrape_news() ,is_admin=is_admin)
    return redirect(url_for('login'))

@app.route('/noticias')
def noticias_page():
    news = scrape_news()
    news = news[-5:]
    if is_admin():
        return render_template('noticias.html', plot_url=generate_plot(), is_admin=is_admin)
    else:
        return render_template('noticias.html', plot_url=generate_plot(), news = news ,is_admin=is_admin)

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


@app.route('/services/edit', methods=['GET', 'POST'])
def edit_services():
    if is_admin():
        if request.method == 'GET':
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM services')
            services = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if services:
                services_list = []
                for service in services:
                    service_dict = {
                        'id': service[0],
                        'name': service[1]}
                    services_list.append(service_dict)
                
                return render_template('edit_services.html', services=services_list)
            else:
                flash('No services found', 'info')
                return redirect(url_for('dashboard'))
        elif request.method == 'POST':
            service_id = request.form['serviceSelect'] 
            description = request.form['description']
            
           
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE services SET description = %s WHERE id = %s', (description, service_id))
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


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, password) VALUES (%s, %s)', (username, password))
        conn.commit()
        cursor.close()
        conn.close()

        flash('Registo efetuado com sucesso', 'success')
        return redirect(url_for('login'))  # Redirect to login page after successful registration

    return render_template('registo.html')  # Render the registration page



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
