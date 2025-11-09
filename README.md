# Water-Quality-Tracker
A water quality tracker system which can help track the service of coolers around the campus, both for technicians and students.

## Files

- `server.py`: The server updates the data and stores it in json files.
- `index.html`: It is the page for technicians where they can add the before and after images of tank cleaning and verify their work and also rectify the issues reported by the students. After the images have been verified by the AI, It updates the records.
- `complaint.html`: For students to view real time status of water coolers/report and view any issues related to them.

## Use
To run the code, create a venv with a .env file containing your GOOGLE_API_KEY, activate the server and get the sites running.
