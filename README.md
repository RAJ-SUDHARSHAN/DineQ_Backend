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


#### **Access Instructions for DineQ**
**App platform:** Android
##### <u>User-Side Application</u>

1. **Download and Install**: Download the user-side DineQ application by clicking [here](https://drive.google.com/file/d/1qS1O014vUBZECEdzcn1NuPgiaHLz1qFN/view). Install the application on your device. If any permissions are requested during installation, please allow them for the full functionality of the application.

2. **Create an Account**: Open the application and proceed to create an account. After account creation, log into your account.

3. **Navigation and Functionality**: The application is designed to show only the restaurants registered with DineQ. We've hardcoded four restaurant geolocations for this demonstration. Once logged in, you can join a virtual queue if seats are not readily available at your preferred restaurant. Upon joining the queue, you'll receive a notification with your queue position.

> - If you've already joined a queue, you'll see a notification about the same.
> - If seats are available, you'll receive a notification prompting you to head to the restaurant directly.
> - Once at the restaurant, you can browse the menu and add items to your cart. After verifying the total bill, you can place an order. Please note that it may take up to 5 seconds to place an order, so kindly wait for this duration before proceeding.
> - Proceed to the "View Tab" which displays the invoice containing all ordered items with respective prices and quantities, and the total amount due. Here, you'll also find a unique 6-digit code for making payment. Note this code down for future reference.

##### <u>Restaurant-Side Application</u>

1. **Download and Install**: Download the user-side DineQ application by clicking [here](https://drive.google.com/file/d/175erRkID43iZGUvqUMwsfH264PongSKd/view?usp=sharing). Install the application on your device. If any permissions are requested during installation, please allow them for the full functionality of the application.

2. **Menu Management**: The staff at the restaurant can use this application to see the menu, add new items, and modify inventory counts.

3. **Seat Management**: Staff can release seats if a user arrives but hasn't placed an order yet. If a user has made a payment, the seats are automatically released, and the next user in the queue can be seated.

4. **Payment Processing**: Staff can navigate to the "Terminal Checkout" section of the app where they can enter the unique order identifier to complete the payment and order. Please note that these operations are executed in a sandbox environment. According to Square's rules, the test order should be less than 25$ for the payment status to be completed.

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