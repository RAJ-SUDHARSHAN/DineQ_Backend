# DineQ_Backend

This repository contains the backend code for the DineQ application, revolutionizing the dining experience with a virtual queue, seamless payment using unique order IDs, and end-to-end dining experience. The application was created as part of the submission to [Devpost Square Developer Hackathon 2023](https://square2023.devpost.com/).

The backend is built using **Django Rest Framework**. It leverages various APIs, including **geofencing**, **Google Maps**, and **Square APIs**, to achieve the desired functionalities.

## Features 🌟

- **Restaurant Discovery:** Users can explore nearby restaurants using geofencing technology (courtesy of Square API) and view relevant details such as cuisine types, ratings, and distance.
- **Queue Management:** Customers can join virtual queues for their preferred restaurants, receive estimated wait times, and receive notifications when their turn is approaching.
- **Seating and Order Management:** Once seated, users can place orders directly through the app, eliminating the need for traditional menus and enhancing efficiency for both customers and restaurant staff.
- **Digital Tab:** The app enables customers to maintain a digital tab, keeping track of their orders, total bill, and payment history, providing a convenient and transparent dining experience.
- **Seamless Payment:** Once done with the meal, users can pay from the app and complete their tab, all from within the app. The experience here is truly seamless and streamlined.

## API Endpoints
The backend for DineQ primarily consists of multiple API endpoints created with the help of square APIs:

1. **Place Order (`orders.create_order`):** Used to create a new order.
2. **Retrieve Order (`orders.retrieve_order`):** Used to fetch details of a specific order.
3. **Invoices (`invoices.create_invoice`, `invoices.get_invoice`):** Used to create a new invoice and retrieve an existing invoice.
4. **Terminal Checkout (`terminal.create_terminal_checkout`):** Used to create a new terminal checkout.
5. **Create and Update Menu (`catalog.upsert_catalog_object`):** Used to add or update a menu item in the catalog.
6. **Update Inventory (`inventory.batch_change_inventory`):** Used to update inventory quantities in bulk.
7. **Adjust Inventory (`inventory.batch_retrieve_inventory_counts`):** Used to retrieve inventory counts for catalog items in bulk.
8. **Nearby Restaurants:** Used to display nearby restaurants registered with DineQ.
9. **Get Menu:** Used to display all the menu items of restaurants.
10. **Available Seats:** Used to display available seats of a restaurant.
11. **Join Queue:** Used to join the virtual queue for restaurants.
12. **Queue Size:** Used to display the current queue size of the restaurants.
13. **Release Seats:** Used to release occupied seats so that the next in queue can come in.

## Setup Instructions for macOS 📋

### Clone the Repository

```bash
git clone https://github.com/RAJ-SUDHARSHAN/DineQ_Backend.git
cd DineQ_Backend/
```

### Setup Virtual Environment and Install Dependencies
```bash
pip install virtualenv
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Install PostgreSQL and PostGIS
To install and setup PostgreSQL and PostGIS, you can follow the instructions from this [Real Python tutorial](https://realpython.com/location-based-app-with-geodjango-tutorial/).

### Setup PostgreSQL Database and PostGIS Extension
Start PostgreSQL service:
```bash
brew services start postgresql
```

Create a new database:
```bash
createdb <your_db_name>
```

Create a PostGIS extension on your database:
```bash
psql -d <your_db_name> -c "CREATE EXTENSION postgis;"
```

### Export GDAL and GEOS Library Paths
You need to export the library paths for GDAL and GEOS. Replace the paths in the commands below with the actual paths on your system:
```bash
export GDAL_LIBRARY_PATH='/opt/homebrew/Cellar/gdal/3.6.4_4/lib/libgdal.dylib'
export GEOS_LIBRARY_PATH='/opt/homebrew/Cellar//geos/3.11.2/lib/libgeos_c.dylib'
```

### Export Environmental variables
```bash 
export DEBUG=<debug_value>
export DJANGO_SECRET_KEY=<your_django_secret_key>
export DB_NAME=<your_db_name>
export DB_USER=<your_db_user>
export DB_PASSWORD=<your_db_password>
export DB_HOST=<your_db_host>
export DB_PORT=<your_db_port>
export GOOGLE_MAPS_API_KEY=<your_google_maps_api_key>
export ALLOWED_HOSTS=<your_allowed_hosts>
export SANDBOX_APPLICATION_ID=<your_sandbox_application_id>
export SQUARE_SANDBOX_ACCESS_TOKEN=<your_square_sandbox_access_token>
export SQUARE_PRODUCTION_ACCESS_TOKEN=<your_square_production_access_token>
```

### Run the Application
After setting up the environment and installing all the requirements, you can start the server using:
```bash
python manage.py runserver
```