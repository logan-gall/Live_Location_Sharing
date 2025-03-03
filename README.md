# Cloud-Driven Live Location Sharing

## Project Overview
A live location sharing web application was developed that allows users to share their real-time location with friends or colleagues. The platform is designed to be lightweight, requiring no additional app downloads, and enables users to input their location manually or by clicking on the map. The system also provides dynamic route calculations to shared locations and real-time updates. Built using Google Cloud infrastructure, the application leverages Flask, Docker, Cloud SQL, and automated deployments to ensure a seamless and scalable experience.

## Key Features
- **Live Location Sharing:** Users can enter their name, latitude, and longitude, or select a point on the map to share their location in real time.
- **Interactive Web Map:** Built on an OpenStreetMap basemap, the interface allows users to visualize shared locations with clickable markers.
- **Route Calculation:** The app dynamically finds and displays the quickest route from a central location (e.g., Blegen Hall at the University of Minnesota) to any shared point.
- **Cloud-Based Infrastructure:** Utilizes Google Cloud SQL for storing locations, Flask for backend processing, and Docker for scalable deployment via Cloud Build & Run.
- **Real-Time Updates:** Includes a proof-of-concept feature that allows users to ping their device to update their location automatically via the Pushover and Tasker apps.
- **Privacy-Focused:** Users can share their location temporarily without requiring third-party apps that store personal data.
- **Potential Applications:** Ideal for friends, event organizers, or companies needing a lightweight, temporary location-sharing tool for meetups, conferences, or team coordination.
