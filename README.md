# 📊 S-Curve Dashboard — JK7 Sumaraja

A web-based project monitoring dashboard built with **Streamlit** and **Google Sheets** to visualize construction progress through S-Curve analysis. The application enables real-time tracking of planned versus actual progress, allowing project teams to monitor performance, identify schedule deviations, and update daily progress collaboratively.

---

# 📂 Project Structure

```text
scurve_streamlit/
├── app.py                          # Main Streamlit application
├── requirements.txt                # Project dependencies
├── JK7-Sumaraja-Scurve.csv         # Initial dataset (Plan & Actual up to July 14, 2026)
├── .gitignore
└── .streamlit/
    └── secrets.toml.example        # Example secrets configuration (Do NOT commit real credentials)
```

---

# 🚀 Getting Started

## Step 1 — Create a Google Spreadsheet

1. Go to **https://sheets.google.com** and create a new spreadsheet.
2. Rename the first worksheet to **`Sheet1`** (must match the `WORKSHEET_NAME` variable in `app.py`).
3. Import the provided dataset:
   - **File → Import → Upload**
   - Select `initial_data_for_gsheet.csv`
   - Choose **Replace current sheet**
4. Ensure the first row contains the following headers exactly:

```
Date
PlanZoning
ActualZoning
Remarks
```

5. Copy the **Spreadsheet ID** from the URL.

Example:

```
https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
```

---

# Step 2 — Create a Google Service Account

1. Open **https://console.cloud.google.com**.
2. Create a new Google Cloud project (or use an existing one).
3. Enable the following APIs:
   - Google Sheets API
   - Google Drive API
4. Navigate to:

```
IAM & Admin
→ Service Accounts
→ Create Service Account
```

5. Enter any service account name (e.g., `scurve-dashboard-bot`).
6. Skip role assignment and click **Done**.
7. Open the newly created Service Account.
8. Navigate to:

```
Keys
→ Add Key
→ Create New Key
→ JSON
```

9. Download the generated JSON credential file.
10. Locate the **client_email** value inside the JSON file.
11. Open your Google Spreadsheet.
12. Click **Share** and grant **Editor** access to the Service Account email.

> **Important:**  
> If the spreadsheet is not shared with the Service Account, the application will return a **403 Permission Denied** error.

---

# Step 3 — Configure Streamlit Secrets

1. Copy

```
.streamlit/secrets.toml.example
```

to

```
.streamlit/secrets.toml
```

2. Open the downloaded JSON credential file.
3. Copy each credential into the corresponding field inside `secrets.toml`.

Example fields include:

- project_id
- private_key_id
- private_key
- client_email
- client_id
- etc.

4. Set the `sheet_id` value using the Spreadsheet ID copied in Step 1.

> **Important:**  
> The `private_key` contains literal `\n` characters. Copy it exactly as provided in the JSON file without converting them into actual line breaks.

---

# Step 4 — Run the Application Locally

```bash
cd scurve_streamlit

python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt

streamlit run app.py
```

After launching:

- Verify that the Planned vs Actual S-Curve chart is displayed.
- Submit a new daily progress entry for a date after **July 14, 2026**.
- Confirm that the corresponding row has been added or updated in Google Sheets.

---

# Step 5 — Push to GitHub

Initialize the repository:

```bash
git init

git add app.py requirements.txt README.md .gitignore initial_data_for_gsheet.csv .streamlit/secrets.toml.example

git status
```

Ensure that **`.streamlit/secrets.toml`** is **NOT** included.

Commit your project:

```bash
git commit -m "Initial commit: S-Curve Dashboard"
```

Create a new repository on GitHub and push:

```bash
git remote add origin https://github.com/USERNAME/REPOSITORY.git

git branch -M main

git push -u origin main
```

---

# Step 6 — Deploy to Streamlit Community Cloud

1. Visit **https://share.streamlit.io**.
2. Sign in with your GitHub account.
3. Click **New App**.
4. Select:
   - Repository
   - Branch: `main`
   - Main file: `app.py`
5. Before deploying, open:

```
Advanced Settings
→ Secrets
```

6. Paste the entire contents of your local `secrets.toml`.
7. Click **Deploy**.

Once deployment is complete, your dashboard will be available at:

```
https://your-app-name.streamlit.app
```

---

# 👥 Multi-User Support

This application supports multiple users simultaneously because all project data is stored in a shared Google Spreadsheet.

Any authorized user accessing the Streamlit application can:

- Submit daily progress updates
- View the latest dashboard
- Share the same centralized dataset

No additional configuration is required.

> **Note:**  
> If multiple users update the same record at the exact same time, the most recent submission will overwrite the previous one.

---

# 🛠 Troubleshooting

| Issue | Possible Cause |
|--------|----------------|
| PermissionError / HTTP 403 | Spreadsheet has not been shared with the Service Account email |
| WorksheetNotFound | Worksheet name is not `Sheet1`; update either the sheet name or `WORKSHEET_NAME` in `app.py` |
| Dashboard data does not refresh | Streamlit cache (TTL = 30 seconds). Wait briefly or manually refresh the page |
| Invalid private_key format | The `\n` characters in the private key were modified. Copy the value exactly as it appears in the JSON credential |

---

# 🛠 Built With

- Streamlit
- Google Sheets API
- Google Drive API
- gspread
- pandas
- Plotly

---

# ✨ Features

- Interactive S-Curve visualization
- Planned vs Actual progress comparison
- Automatic cumulative progress calculation
- Daily progress submission
- Google Sheets integration
- Real-time dashboard updates
- Collaborative multi-user access
- Responsive web interface

---

# 👩‍💻 Author

**Geralda Livia Nugraha**

Bachelor of Engineering (Mechatronics & Artificial Intelligence)

Project Engineering • Dashboard Development • Data Analytics • Network Engineering

---

> **Disclaimer**
>
> This repository is intended to showcase dashboard development and spreadsheet automation techniques. Any confidential project information has been removed or anonymized before publication.
