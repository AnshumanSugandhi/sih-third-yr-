# Real-Time Crypto Fraud Wallet Tracer (SIH Problem Statement 26183)

Automated Blockchain Analytics Engine & VASP Identification System built for Ministry of Home Affairs (MHA) / Indian Cyber Crime Coordination Centre (I4C).

## 🚀 Quick Start (Local Browser)

The web dashboard is running live on your local machine at:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

To run it anytime manually from terminal:
```bash
python app.py
```

---

## 🌐 How to Host it Online for FREE

Here are the **top 3 free hosting platforms** to publish your live working web dashboard for judges:

### Method 1: Render.com (Recommended - Free Web Service)
1. Push this folder to a public or private GitHub repository.
2. Sign up at [Render.com](https://render.com).
3. Click **New +** -> **Web Service** and select your GitHub repository.
4. Fill in:
   - **Name**: `crypto-fraud-tracer`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Click **Create Web Service**. Render will build and publish your app live at `https://crypto-fraud-tracer.onrender.com`.

### Method 2: Hugging Face Spaces (Free Instant Docker Hosting)
1. Sign up at [Hugging Face](https://huggingface.co/spaces).
2. Click **Create new Space**. Choose **Docker** template.
3. Upload these project files (`app.py`, `templates/`, `requirements.txt`, `Procfile`).
4. Hugging Face will host your app on a free public link.

### Method 3: PythonAnywhere (Free Python Hosting)
1. Sign up at [PythonAnywhere.com](https://www.pythonanywhere.com).
2. Upload the project files under your Dashboard.
3. In the **Web** tab, configure a Flask Web App pointing WSGI to `app.py`.
